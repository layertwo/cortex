import { describe, it, expect } from 'vitest';
import { deriveKeys } from '@cortex/encryption';
import { encryptMetadata, decryptMetadata, type FileMetadata } from './metadata';

const key = (seed: number) => deriveKeys(new Uint8Array(32).fill(seed)).metadataEncryptionKey;
const META: FileMetadata = { name: 'cat.png', contentType: 'image/png', size: 1234, contentId: 'id-1' };

describe('file metadata codec', () => {
  it('round-trips metadata with the correct key', async () => {
    // Adapted for #208: encryptedMetadata is a Blob (Uint8Array) on the contract;
    // the SDK base64s it on the wire, so the codec stays in raw bytes.
    const blob = await encryptMetadata(META, key(1));
    expect(blob).toBeInstanceOf(Uint8Array);
    expect(decryptMetadata(blob, key(1))).toEqual(META);
  });

  it('fails to decrypt with the wrong key', async () => {
    const blob = await encryptMetadata(META, key(1));
    expect(() => decryptMetadata(blob, key(2))).toThrow();
  });
});
