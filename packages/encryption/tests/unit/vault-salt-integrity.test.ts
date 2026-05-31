import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';
import { computeSaltHmac } from '../../src/lib/vault-salt-integrity';

describe('computeSaltHmac', () => {
  it('returns HMAC-SHA256(saltHmacKey, salt) as a 32-byte Uint8Array', () => {
    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);

    const result = computeSaltHmac(saltHmacKey, salt);
    const expected = hmac(sha256, saltHmacKey, salt);

    expect(result).toBeInstanceOf(Uint8Array);
    expect(result).toHaveLength(32);
    expect(Buffer.from(result).equals(Buffer.from(expected))).toBe(true);
  });

  it('rejects a saltHmacKey that is not 32 bytes', () => {
    expect(() => computeSaltHmac(new Uint8Array(16), new Uint8Array(16))).toThrow(
      /saltHmacKey must be 32 bytes/
    );
  });

  it('rejects a salt that is not 16 bytes', () => {
    expect(() => computeSaltHmac(new Uint8Array(32), new Uint8Array(8))).toThrow(
      /salt must be 16 bytes/
    );
  });
});
