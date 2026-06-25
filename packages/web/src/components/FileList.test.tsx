import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
  listItems: vi.fn(async () => [{ itemId: 'i1', encryptedMetadata: new Uint8Array([1]), createdAt: new Date(1000) }]),
  getDownloadUrl: vi.fn(async () => 'https://s3/get'),
  deleteItem: vi.fn(async () => {}),
  decryptMetadata: vi.fn(() => ({ name: 'cat.png', contentType: 'image/png', size: 1234, contentId: 'c1' })),
  decryptDownloadedBlob: vi.fn(() => new Uint8Array([1, 2, 3])),
  pickSink: vi.fn(async () => ({ write: vi.fn(), close: vi.fn(), abort: vi.fn() })),
  downloadFileStreaming: vi.fn(async () => {}),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../api/items', () => ({ listItems: h.listItems, getDownloadUrl: h.getDownloadUrl, deleteItem: h.deleteItem }));
vi.mock('../items/metadata', () => ({ decryptMetadata: h.decryptMetadata }));
vi.mock('../items/itemCrypto', () => ({ decryptDownloadedBlob: h.decryptDownloadedBlob }));
vi.mock('../items/streamingDownload', () => ({ pickSink: h.pickSink, downloadFileStreaming: h.downloadFileStreaming }));

import FileList from './FileList';

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(new Uint8Array([9]).buffer)));
  // jsdom lacks these; stub so the download path doesn't crash.
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() });
});

describe('FileList', () => {
  it('renders a decrypted row', async () => {
    render(<FileList refreshKey={0} />);
    expect(await screen.findByText('cat.png')).toBeInTheDocument();
  });

  it('legacy download (no streamVersion) fetches the url, decrypts whole-buffer, saves', async () => {
    render(<FileList refreshKey={0} />);
    await screen.findByText('cat.png');
    await userEvent.click(screen.getByRole('button', { name: /download/i }));
    await waitFor(() => expect(h.getDownloadUrl).toHaveBeenCalledWith('i1'));
    expect(h.decryptDownloadedBlob).toHaveBeenCalled();
    expect(h.downloadFileStreaming).not.toHaveBeenCalled();
  });

  it('chunked download (streamVersion present) picks a sink and streams', async () => {
    // Once only — clearAllMocks doesn't restore an overridden implementation, so a
    // persistent mockReturnValue would leak streamVersion into later tests.
    h.decryptMetadata.mockReturnValueOnce({
      name: 'big.bin', contentType: 'application/octet-stream', size: 999, contentId: 'c2', streamVersion: 1,
    });
    render(<FileList refreshKey={0} />);
    await screen.findByText('big.bin');
    await userEvent.click(screen.getByRole('button', { name: /download/i }));
    await waitFor(() => expect(h.pickSink).toHaveBeenCalledWith('big.bin', 'application/octet-stream'));
    expect(h.downloadFileStreaming).toHaveBeenCalledWith(
      'i1',
      expect.objectContaining({ streamVersion: 1 }),
      expect.any(Uint8Array),
      expect.anything(),
    );
    expect(h.decryptDownloadedBlob).not.toHaveBeenCalled();
  });

  it('delete calls the API then reloads the list', async () => {
    render(<FileList refreshKey={0} />);
    await screen.findByText('cat.png');
    await userEvent.click(screen.getByRole('button', { name: /delete/i }));
    await waitFor(() => expect(h.deleteItem).toHaveBeenCalledWith('i1'));
    expect(h.listItems).toHaveBeenCalledTimes(2); // initial + after delete
  });
});
