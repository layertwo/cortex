import { describe, it, expect, vi, beforeEach } from 'vitest';
import { decryptMetadata } from './metadata';

const api = vi.hoisted(() => ({
  initiateUpload: vi.fn(),
  putToS3: vi.fn(),
  createUploadPartUrls: vi.fn(),
  completeUpload: vi.fn(),
  abortUpload: vi.fn(),
}));
vi.mock('../api/items', () => api);

import { uploadFileStreaming } from './streamingUpload';

const keys = { vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) };

// File-like stub: deterministic slice/arrayBuffer, no jsdom Blob dependency.
function fakeFile(bytes: Uint8Array, name = 'f.bin', type = 'image/png'): File {
  return {
    name,
    type,
    size: bytes.length,
    slice: (s: number, e: number) => ({ arrayBuffer: async () => bytes.slice(s, e).buffer }),
  } as unknown as File;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.putToS3.mockResolvedValue('"etag"');
  api.completeUpload.mockResolvedValue(undefined);
  api.abortUpload.mockResolvedValue(undefined);
  api.createUploadPartUrls.mockImplementation(async (_i: string, _u: string, parts: number[]) =>
    parts.map((n) => ({ partNumber: n, url: `https://s3/p${n}` })),
  );
});

describe('uploadFileStreaming', () => {
  it('single-PUT path: assembles one blob, completes with no parts, sets streamVersion', async () => {
    api.initiateUpload.mockResolvedValue({ itemId: 'i1', uploadUrl: 'https://s3/put' }); // no uploadId
    const onProgress = vi.fn();
    await uploadFileStreaming(fakeFile(new Uint8Array([1, 2, 3])), keys, onProgress);

    // sizeBytes = 97 + 13 + 3 + 16 = 129 (1 chunk)
    expect(api.initiateUpload).toHaveBeenCalledWith(
      expect.objectContaining({ vaultId: 'v1', sizeBytes: 129 }),
    );
    const meta = decryptMetadata(api.initiateUpload.mock.calls[0][0].encryptedMetadata, keys.metadataKey);
    expect(meta).toMatchObject({ name: 'f.bin', size: 3, streamVersion: 1 });
    expect(api.putToS3).toHaveBeenCalledTimes(1);
    expect(api.putToS3.mock.calls[0][0]).toBe('https://s3/put');
    expect(api.putToS3.mock.calls[0][1].length).toBe(129);
    expect(api.completeUpload).toHaveBeenCalledWith('i1'); // no opts
    expect(onProgress).toHaveBeenLastCalledWith(1);
  });

  it('multipart path: parts uploaded in order, eTags collected, complete gets ordered parts', async () => {
    api.initiateUpload.mockResolvedValue({ itemId: 'i1', uploadUrl: 'https://s3/put', uploadId: 'mp1' });
    api.putToS3.mockImplementation(async (url: string) => `"e-${url.slice(-2)}"`);
    // 10 bytes, chunkSize 4 → 3 parts (4, 4, 2)
    await uploadFileStreaming(fakeFile(new Uint8Array(10)), keys, undefined, { chunkSize: 4 });

    expect(api.createUploadPartUrls).toHaveBeenCalledWith('i1', 'mp1', [1, 2, 3]);
    const putUrls = api.putToS3.mock.calls.map((c: unknown[]) => c[0]);
    expect(putUrls).toEqual(['https://s3/p1', 'https://s3/p2', 'https://s3/p3']);
    // part 1 body = 97 + 13 + (4 + 16) = 130; part 2 = 20; part 3 = (2 + 16) = 18
    expect(api.putToS3.mock.calls.map((c: { length: number }[]) => c[1].length)).toEqual([130, 20, 18]);
    expect(api.completeUpload).toHaveBeenCalledWith('i1', {
      uploadId: 'mp1',
      parts: [
        { partNumber: 1, eTag: '"e-p1"' },
        { partNumber: 2, eTag: '"e-p2"' },
        { partNumber: 3, eTag: '"e-p3"' },
      ],
    });
    expect(api.abortUpload).not.toHaveBeenCalled();
  });

  it('retries a failing part, then completes without aborting', async () => {
    api.initiateUpload.mockResolvedValue({ itemId: 'i1', uploadUrl: 'x', uploadId: 'mp1' });
    let calls = 0;
    api.putToS3.mockImplementation(async () => {
      calls += 1;
      if (calls === 1) throw new Error('flaky');
      return '"e"';
    });
    await uploadFileStreaming(fakeFile(new Uint8Array(3)), keys, undefined, { chunkSize: 4 });
    expect(calls).toBe(2); // 1 fail + 1 success on the single part
    expect(api.completeUpload).toHaveBeenCalled();
    expect(api.abortUpload).not.toHaveBeenCalled();
  });

  it('aborts the multipart upload and rethrows when a part exhausts its retries', async () => {
    api.initiateUpload.mockResolvedValue({ itemId: 'i1', uploadUrl: 'x', uploadId: 'mp1' });
    api.putToS3.mockRejectedValue(new Error('dead'));
    await expect(
      uploadFileStreaming(fakeFile(new Uint8Array(3)), keys, undefined, { chunkSize: 4 }),
    ).rejects.toThrow('dead');
    expect(api.abortUpload).toHaveBeenCalledWith('i1', 'mp1');
    expect(api.completeUpload).not.toHaveBeenCalled();
  });
});
