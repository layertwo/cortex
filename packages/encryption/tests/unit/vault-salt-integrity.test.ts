import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';
import { computeSaltHmac, verifySaltHmac } from '../../src/lib/vault-salt-integrity';

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

describe('verifySaltHmac', () => {
  const saltHmacKey = new Uint8Array(32).fill(0xab);
  const salt = new Uint8Array(16).fill(0xcd);

  it('returns true for an HMAC computed over the same salt with the same key', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    expect(verifySaltHmac(saltHmacKey, salt, mac)).toBe(true);
  });

  it('returns false for a tampered HMAC (single bit flipped)', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    const tampered = new Uint8Array(mac);
    tampered[0] ^= 0x01;
    expect(verifySaltHmac(saltHmacKey, salt, tampered)).toBe(false);
  });

  it('returns false when the salt has been replaced', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    const replacedSalt = new Uint8Array(16).fill(0xee);
    expect(verifySaltHmac(saltHmacKey, replacedSalt, mac)).toBe(false);
  });

  it('returns false when the stored HMAC is the wrong length', () => {
    expect(verifySaltHmac(saltHmacKey, salt, new Uint8Array(31))).toBe(false);
  });
});
