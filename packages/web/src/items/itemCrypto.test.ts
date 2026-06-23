import { describe, it, expect } from 'vitest';
import { deriveKeys, encryptFileWithDek } from '@cortex/encryption';
import { decryptDownloadedBlob } from './itemCrypto';
import { encodeItemBlob } from './itemBlob';
import type { FileMetadata } from './metadata';

const keys = (() => {
  const k = deriveKeys(new Uint8Array(32).fill(5));
  return { kek: k.keyEncryptionKey, metadataKey: k.metadataEncryptionKey };
})();

// Build a legacy (Slice 2) blob from the envelope primitives — the format
// decryptDownloadedBlob consumes for pre-2.5c objects.
async function legacyBlob(bytes: Uint8Array, contentId: string): Promise<Uint8Array> {
  const { encryptedContent, wrappedDek } = await encryptFileWithDek(bytes, keys.kek, contentId);
  return encodeItemBlob(wrappedDek, encryptedContent);
}

describe('item crypto (legacy download path)', () => {
  it('decrypts a legacy blob end-to-end', async () => {
    const bytes = new TextEncoder().encode('the secret photo bytes');
    const meta: FileMetadata = { name: 'photo.jpg', contentType: 'image/jpeg', size: bytes.length, contentId: crypto.randomUUID() };
    const blob = await legacyBlob(bytes, meta.contentId);

    const out = decryptDownloadedBlob(blob, meta, keys.kek);
    // Array.from both sides: under jsdom, the crypto lib's Uint8Array (Node realm)
    // and the test's TextEncoder Uint8Array (jsdom realm) are byte-identical but
    // cross-realm, so toEqual on the raw arrays fails. Plain arrays are realm-agnostic.
    expect(Array.from(out)).toEqual(Array.from(bytes));
  });

  it('fails the HMAC binding if contentId is tampered', async () => {
    const bytes = new TextEncoder().encode('x');
    const contentId = crypto.randomUUID();
    const blob = await legacyBlob(bytes, contentId);
    const tampered: FileMetadata = { name: 'a', contentType: 'text/plain', size: 1, contentId: 'different-content-id' };
    expect(() => decryptDownloadedBlob(blob, tampered, keys.kek)).toThrow();
  });
});
