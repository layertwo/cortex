import { describe, it, expect } from 'vitest';
import { deriveKeys } from '@cortex/encryption';
import { encryptCollectionName, decryptCollectionName } from './collectionMetadata';

const metadataKey = deriveKeys(new Uint8Array(32).fill(3)).metadataEncryptionKey;

describe('collectionMetadata', () => {
  it('round-trips a collection name', async () => {
    const blob = await encryptCollectionName('Trip 2026 🌍', metadataKey);
    expect(decryptCollectionName(blob, metadataKey)).toBe('Trip 2026 🌍');
  });

  it('produces opaque ciphertext (name not in plaintext)', async () => {
    const blob = await encryptCollectionName('Receipts', metadataKey);
    expect(new TextDecoder().decode(blob)).not.toContain('Receipts');
  });
});
