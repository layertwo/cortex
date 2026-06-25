import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
  uploadFileStreaming: vi.fn(async (..._args: unknown[]) => {}),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../items/streamingUpload', () => ({ uploadFileStreaming: h.uploadFileStreaming }));

import FileUpload, { MAX_FILE_SIZE_BYTES } from './FileUpload';

beforeEach(() => vi.clearAllMocks());

function pick(name: string, bytes: number, type = 'image/png') {
  const file = new File([new Uint8Array(Math.min(bytes, 4))], name, { type });
  // jsdom File.size reflects byte length; override cheaply for the over-cap case.
  Object.defineProperty(file, 'size', { value: bytes });
  return file;
}

describe('FileUpload', () => {
  it('delegates to uploadFileStreaming and calls onUploaded', async () => {
    const onUploaded = vi.fn();
    render(<FileUpload onUploaded={onUploaded} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), pick('a.png', 3));
    await waitFor(() => expect(onUploaded).toHaveBeenCalled());
    expect(h.uploadFileStreaming).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'a.png' }),
      expect.objectContaining({ vaultId: 'v1' }),
      expect.any(Function),
      expect.objectContaining({ tags: expect.any(Array) }),
    );
  });

  it('passes parsed tags from the tags input', async () => {
    render(<FileUpload onUploaded={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/tags/i), 'Trip, beach ,');
    await userEvent.upload(screen.getByLabelText(/upload/i), pick('a.png', 3));
    await waitFor(() => expect(h.uploadFileStreaming).toHaveBeenCalled());
    expect(h.uploadFileStreaming.mock.calls[0][3]).toEqual({ tags: ['Trip', 'beach'] });
  });

  it('rejects files over the 5 GB cap without uploading', async () => {
    render(<FileUpload onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), pick('big.bin', MAX_FILE_SIZE_BYTES + 1));
    expect(await screen.findByRole('alert')).toHaveTextContent(/5 ?GB/i);
    expect(h.uploadFileStreaming).not.toHaveBeenCalled();
  });

  it('surfaces an upload error', async () => {
    h.uploadFileStreaming.mockRejectedValueOnce(new Error('integrity check failed'));
    render(<FileUpload onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), pick('a.png', 3));
    expect(await screen.findByRole('alert')).toHaveTextContent(/integrity check failed/i);
  });
});
