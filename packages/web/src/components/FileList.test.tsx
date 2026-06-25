import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { FileMetadata } from '../items/metadata';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
  listItems: vi.fn(async () => [{ itemId: 'i1', encryptedMetadata: new Uint8Array([1]), createdAt: new Date(1000) }]),
  getDownloadUrl: vi.fn(async () => 'https://s3/get'),
  deleteItem: vi.fn(async () => {}),
  searchByTag: vi.fn(async () => [{ itemId: 'i1', encryptedMetadata: new Uint8Array([1]), createdAt: new Date(1000) }]),
  getCollection: vi.fn(async () => [{ itemId: 'i1', encryptedMetadata: new Uint8Array([1]), createdAt: new Date(1000) }]),
  listCollections: vi.fn(async () => []),
  addItemToCollection: vi.fn(async () => {}),
  decryptMetadata: vi.fn((): FileMetadata => ({ name: 'cat.png', contentType: 'image/png', size: 1234, contentId: 'c1' })),
  decryptDownloadedBlob: vi.fn(() => new Uint8Array([1, 2, 3])),
  decryptCollectionName: vi.fn(() => 'Trip'),
  pickSink: vi.fn(async () => ({ write: vi.fn(), close: vi.fn(), abort: vi.fn() })),
  downloadFileStreaming: vi.fn(async () => {}),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../api/items', () => ({
  listItems: h.listItems,
  getDownloadUrl: h.getDownloadUrl,
  deleteItem: h.deleteItem,
  searchByTag: h.searchByTag,
}));
vi.mock('../api/collections', () => ({
  getCollection: h.getCollection,
  listCollections: h.listCollections,
  addItemToCollection: h.addItemToCollection,
}));
vi.mock('../items/metadata', () => ({ decryptMetadata: h.decryptMetadata }));
vi.mock('../items/itemCrypto', () => ({ decryptDownloadedBlob: h.decryptDownloadedBlob }));
vi.mock('../items/collectionMetadata', () => ({ decryptCollectionName: h.decryptCollectionName }));
vi.mock('../items/streamingDownload', () => ({ pickSink: h.pickSink, downloadFileStreaming: h.downloadFileStreaming }));

import FileList from './FileList';

const ALL = { kind: 'all' as const };

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', vi.fn(async () => new Response(new Uint8Array([9]).buffer)));
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() });
});

describe('FileList', () => {
  it('renders a decrypted row', async () => {
    render(<FileList view={ALL} refreshKey={0} />);
    expect(await screen.findByText('cat.png')).toBeInTheDocument();
  });

  it('renders tag chips from decrypted metadata', async () => {
    h.decryptMetadata.mockReturnValueOnce({ name: 'cat.png', contentType: 'image/png', size: 1, contentId: 'c1', tags: ['beach', 'trip'] });
    render(<FileList view={ALL} refreshKey={0} />);
    expect(await screen.findByText(/beach/)).toBeInTheDocument();
    expect(screen.getByText(/trip/)).toBeInTheDocument();
  });

  it('a collection view loads via getCollection, not listItems', async () => {
    render(<FileList view={{ kind: 'collection', id: 'c1', name: 'Trip' }} refreshKey={0} />);
    await waitFor(() => expect(h.getCollection).toHaveBeenCalledWith('c1'));
    expect(h.listItems).not.toHaveBeenCalled();
  });

  it('a tag view loads via searchByTag', async () => {
    render(<FileList view={{ kind: 'tag', encryptedTag: 'YWJj', label: 'beach' }} refreshKey={0} />);
    await waitFor(() => expect(h.searchByTag).toHaveBeenCalledWith('v1', 'YWJj'));
  });

  it('legacy download (no streamVersion) fetches the url, decrypts whole-buffer, saves', async () => {
    render(<FileList view={ALL} refreshKey={0} />);
    await screen.findByText('cat.png');
    await userEvent.click(screen.getByRole('button', { name: /^download$/i }));
    await waitFor(() => expect(h.getDownloadUrl).toHaveBeenCalledWith('i1'));
    expect(h.decryptDownloadedBlob).toHaveBeenCalled();
    expect(h.downloadFileStreaming).not.toHaveBeenCalled();
  });

  it('chunked download (streamVersion present) picks a sink and streams', async () => {
    h.decryptMetadata.mockReturnValueOnce({ name: 'big.bin', contentType: 'application/octet-stream', size: 999, contentId: 'c2', streamVersion: 1 });
    render(<FileList view={ALL} refreshKey={0} />);
    await screen.findByText('big.bin');
    await userEvent.click(screen.getByRole('button', { name: /^download$/i }));
    await waitFor(() => expect(h.pickSink).toHaveBeenCalledWith('big.bin', 'application/octet-stream'));
    expect(h.downloadFileStreaming).toHaveBeenCalledWith('i1', expect.objectContaining({ streamVersion: 1 }), expect.any(Uint8Array), expect.anything());
    expect(h.decryptDownloadedBlob).not.toHaveBeenCalled();
  });

  it('add-to-collection lists collections then adds the item', async () => {
    h.listCollections.mockResolvedValueOnce([
      { collectionId: 'c9', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), itemCount: 0, createdAt: new Date(0), updatedAt: new Date(0) },
    ]);
    render(<FileList view={ALL} refreshKey={0} />);
    await screen.findByText('cat.png');
    await userEvent.click(screen.getByRole('button', { name: /add to collection/i }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Trip' }));
    await waitFor(() => expect(h.addItemToCollection).toHaveBeenCalledWith('c9', 'v1', 'i1'));
  });

  it('delete calls the API then reloads the list', async () => {
    render(<FileList view={ALL} refreshKey={0} />);
    await screen.findByText('cat.png');
    await userEvent.click(screen.getByRole('button', { name: /delete/i }));
    await waitFor(() => expect(h.deleteItem).toHaveBeenCalledWith('i1'));
    expect(h.listItems).toHaveBeenCalledTimes(2); // initial + after delete
  });
});
