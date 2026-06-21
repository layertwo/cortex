import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const enc = new Uint8Array([7, 7]);
const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
  encryptFileForUpload: vi.fn(async () => ({ blob: new Uint8Array([9, 9]), encryptedMetadata: new Uint8Array([7, 7]), metadata: {} })),
  initiateUpload: vi.fn(async () => ({ itemId: 'i1', uploadUrl: 'https://s3/put' })),
  putToS3: vi.fn(async () => {}),
  completeUpload: vi.fn(async () => {}),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../items/itemCrypto', () => ({ encryptFileForUpload: h.encryptFileForUpload }));
vi.mock('../api/items', () => ({ initiateUpload: h.initiateUpload, putToS3: h.putToS3, completeUpload: h.completeUpload }));

import FileUpload, { MAX_FILE_SIZE_BYTES } from './FileUpload';

beforeEach(() => vi.clearAllMocks());

function pick(name: string, bytes: number, type = 'image/png') {
  const file = new File([new Uint8Array(bytes)], name, { type });
  // jsdom File.size reflects the byte length; override for the over-cap case cheaply:
  Object.defineProperty(file, 'size', { value: bytes });
  file.arrayBuffer = async () => new Uint8Array(Math.min(bytes, 4)).buffer;
  return file;
}

describe('FileUpload', () => {
  it('runs init → PUT → complete in order and calls onUploaded', async () => {
    const onUploaded = vi.fn();
    render(<FileUpload onUploaded={onUploaded} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), pick('a.png', 3));
    await waitFor(() => expect(onUploaded).toHaveBeenCalled());
    expect(h.encryptFileForUpload).toHaveBeenCalled();
    expect(h.initiateUpload).toHaveBeenCalledWith({ vaultId: 'v1', encryptedMetadata: enc, sizeBytes: 2 });
    expect(h.putToS3).toHaveBeenCalledWith('https://s3/put', new Uint8Array([9, 9]));
    expect(h.completeUpload).toHaveBeenCalledWith('i1');
  });

  it('rejects files over the cap without uploading', async () => {
    render(<FileUpload onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/upload/i), pick('big.bin', MAX_FILE_SIZE_BYTES + 1));
    expect(await screen.findByRole('alert')).toHaveTextContent(/100 ?MB/i);
    expect(h.initiateUpload).not.toHaveBeenCalled();
  });
});
