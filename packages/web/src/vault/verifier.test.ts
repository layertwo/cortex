import { describe, it, expect } from 'vitest';
import { deriveKeys } from '@cortex/encryption';
import { createVerifier, checkVerifier } from './verifier';

function keysFrom(seed: number) {
  return deriveKeys(new Uint8Array(32).fill(seed));
}

describe('vault verifier', () => {
  it('verifies with the correct metadata key', async () => {
    const keys = keysFrom(1);
    const blob = await createVerifier(keys.metadataEncryptionKey);
    expect(checkVerifier(blob, keys.metadataEncryptionKey)).toBe(true);
  });

  it('rejects a wrong metadata key', async () => {
    const right = keysFrom(1);
    const wrong = keysFrom(2);
    const blob = await createVerifier(right.metadataEncryptionKey);
    expect(checkVerifier(blob, wrong.metadataEncryptionKey)).toBe(false);
  });

  it('rejects a corrupted blob without throwing', () => {
    const keys = keysFrom(1);
    expect(checkVerifier('not-base64-or-valid', keys.metadataEncryptionKey)).toBe(false);
  });
});
