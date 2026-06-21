import { describe, it, expect } from 'vitest';
import { deriveKeys } from '@cortex/encryption';
import { encryptFileForUpload, decryptDownloadedBlob } from './itemCrypto';
import { decryptMetadata } from './metadata';

const keys = (() => {
  const k = deriveKeys(new Uint8Array(32).fill(5));
  return { kek: k.keyEncryptionKey, metadataKey: k.metadataEncryptionKey };
})();

describe('item crypto', () => {
  it('encrypts then decrypts a file end-to-end', async () => {
    const bytes = new TextEncoder().encode('the secret photo bytes');
    const { blob, encryptedMetadata, metadata } = await encryptFileForUpload(
      bytes, 'photo.jpg', 'image/jpeg', keys,
    );
    expect(metadata).toMatchObject({ name: 'photo.jpg', contentType: 'image/jpeg', size: bytes.length });
    expect(metadata.contentId).toMatch(/[0-9a-f-]{36}/);

    const meta = decryptMetadata(encryptedMetadata, keys.metadataKey);
    const out = decryptDownloadedBlob(blob, meta, keys.kek);
    // Array.from both sides: under jsdom, the crypto lib's Uint8Array (Node realm)
    // and the test's TextEncoder Uint8Array (jsdom realm) are byte-identical but
    // cross-realm, so toEqual on the raw arrays fails. Comparing plain arrays is
    // realm-agnostic and still checks every byte.
    expect(Array.from(out)).toEqual(Array.from(bytes));
  });

  it('fails the HMAC binding if contentId is tampered', async () => {
    const bytes = new TextEncoder().encode('x');
    const { blob, metadata } = await encryptFileForUpload(bytes, 'a', 'text/plain', keys);
    const tampered = { ...metadata, contentId: 'different-content-id' };
    expect(() => decryptDownloadedBlob(blob, tampered, keys.kek)).toThrow();
  });
});
