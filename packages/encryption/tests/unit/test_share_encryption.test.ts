/**
 * Unit tests for share encryption module
 *
 * Tests key derivation, HMAC computation/verification, and blob encode/decode
 * for the password-protected file sharing system.
 */

import {
  deriveShareKeys,
  computeShareHmac,
  verifyShareHmac,
  encodeShareBlob,
  decodeShareBlob,
} from '../../src/lib/share-encryption';

describe('Share Encryption Module', () => {
  // Fixed test salt (16 bytes)
  const testSalt = new Uint8Array(16);
  for (let i = 0; i < 16; i++) {
    testSalt[i] = i;
  }

  // Fixed test password
  const testPassword = 'test-share-password-123';

  describe('deriveShareKeys', () => {
    it('should derive encryptionKey and hmacKey of 32 bytes each', async () => {
      const keys = await deriveShareKeys(testPassword, testSalt);

      expect(keys.encryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.encryptionKey.length).toBe(32);
      expect(keys.hmacKey).toBeInstanceOf(Uint8Array);
      expect(keys.hmacKey.length).toBe(32);
    });

    it('should derive different encryptionKey and hmacKey', async () => {
      const keys = await deriveShareKeys(testPassword, testSalt);

      expect(keys.encryptionKey).not.toEqual(keys.hmacKey);
    });

    it('should be deterministic for the same password and salt', async () => {
      const keys1 = await deriveShareKeys(testPassword, testSalt);
      const keys2 = await deriveShareKeys(testPassword, testSalt);

      expect(keys1.encryptionKey).toEqual(keys2.encryptionKey);
      expect(keys1.hmacKey).toEqual(keys2.hmacKey);
    });

    it('should produce different keys for different passwords', async () => {
      const keys1 = await deriveShareKeys('password-one', testSalt);
      const keys2 = await deriveShareKeys('password-two', testSalt);

      expect(keys1.encryptionKey).not.toEqual(keys2.encryptionKey);
      expect(keys1.hmacKey).not.toEqual(keys2.hmacKey);
    });

    it('should produce different keys for different salts', async () => {
      const salt2 = new Uint8Array(16);
      salt2.fill(0xff);

      const keys1 = await deriveShareKeys(testPassword, testSalt);
      const keys2 = await deriveShareKeys(testPassword, salt2);

      expect(keys1.encryptionKey).not.toEqual(keys2.encryptionKey);
      expect(keys1.hmacKey).not.toEqual(keys2.hmacKey);
    });

    it('should throw error for empty password', async () => {
      await expect(deriveShareKeys('', testSalt)).rejects.toThrow(
        'Password cannot be empty'
      );
    });

    it('should throw error for salt shorter than 16 bytes', async () => {
      const shortSalt = new Uint8Array(8);
      await expect(deriveShareKeys(testPassword, shortSalt)).rejects.toThrow(
        'Salt must be at least 16 bytes'
      );
    });
  });

  describe('computeShareHmac', () => {
    // Use a fixed 32-byte hmacKey for testing
    const hmacKey = new Uint8Array(32);
    for (let i = 0; i < 32; i++) {
      hmacKey[i] = i + 100;
    }

    it('should produce a 32-byte HMAC', () => {
      const result = computeShareHmac(hmacKey, 'share-id-123');
      expect(result).toBeInstanceOf(Uint8Array);
      expect(result.length).toBe(32);
    });

    it('should be deterministic', () => {
      const hmac1 = computeShareHmac(hmacKey, 'share-id-123');
      const hmac2 = computeShareHmac(hmacKey, 'share-id-123');
      expect(hmac1).toEqual(hmac2);
    });

    it('should produce different HMACs for different shareIds', () => {
      const hmac1 = computeShareHmac(hmacKey, 'share-id-1');
      const hmac2 = computeShareHmac(hmacKey, 'share-id-2');
      expect(hmac1).not.toEqual(hmac2);
    });

    it('should produce different HMACs for different keys', () => {
      const key2 = new Uint8Array(32);
      key2.fill(0xff);

      const hmac1 = computeShareHmac(hmacKey, 'share-id-123');
      const hmac2 = computeShareHmac(key2, 'share-id-123');
      expect(hmac1).not.toEqual(hmac2);
    });

    it('should include expiresAt in HMAC when provided', () => {
      const expiresAt = 1700000000;
      const hmacWithExpiry = computeShareHmac(hmacKey, 'share-id-123', expiresAt);
      const hmacWithoutExpiry = computeShareHmac(hmacKey, 'share-id-123');
      expect(hmacWithExpiry).not.toEqual(hmacWithoutExpiry);
    });

    it('should produce different HMACs for different expiresAt values', () => {
      const hmac1 = computeShareHmac(hmacKey, 'share-id-123', 1700000000);
      const hmac2 = computeShareHmac(hmacKey, 'share-id-123', 1700000001);
      expect(hmac1).not.toEqual(hmac2);
    });

    it('should throw error for invalid hmacKey length', () => {
      const badKey = new Uint8Array(16);
      expect(() => computeShareHmac(badKey, 'share-id-123')).toThrow(
        'HMAC key must be 32 bytes'
      );
    });

    it('should throw error for empty shareId', () => {
      expect(() => computeShareHmac(hmacKey, '')).toThrow(
        'shareId cannot be empty'
      );
    });
  });

  describe('verifyShareHmac', () => {
    const hmacKey = new Uint8Array(32);
    for (let i = 0; i < 32; i++) {
      hmacKey[i] = i + 100;
    }

    it('should return true for a valid HMAC without expiry', () => {
      const mac = computeShareHmac(hmacKey, 'share-id-123');
      const result = verifyShareHmac(hmacKey, 'share-id-123', undefined, mac);
      expect(result).toBe(true);
    });

    it('should return true for a valid HMAC with expiry', () => {
      const expiresAt = 1700000000;
      const mac = computeShareHmac(hmacKey, 'share-id-123', expiresAt);
      const result = verifyShareHmac(hmacKey, 'share-id-123', expiresAt, mac);
      expect(result).toBe(true);
    });

    it('should return false for a tampered HMAC', () => {
      const mac = computeShareHmac(hmacKey, 'share-id-123');
      const tampered = new Uint8Array(mac);
      tampered[0] ^= 0xff;
      const result = verifyShareHmac(hmacKey, 'share-id-123', undefined, tampered);
      expect(result).toBe(false);
    });

    it('should return false for wrong shareId', () => {
      const mac = computeShareHmac(hmacKey, 'share-id-123');
      const result = verifyShareHmac(hmacKey, 'share-id-wrong', undefined, mac);
      expect(result).toBe(false);
    });

    it('should return false for wrong expiresAt', () => {
      const mac = computeShareHmac(hmacKey, 'share-id-123', 1700000000);
      const result = verifyShareHmac(hmacKey, 'share-id-123', 9999999999, mac);
      expect(result).toBe(false);
    });

    it('should return false for wrong key', () => {
      const mac = computeShareHmac(hmacKey, 'share-id-123');
      const wrongKey = new Uint8Array(32);
      wrongKey.fill(0xff);
      const result = verifyShareHmac(wrongKey, 'share-id-123', undefined, mac);
      expect(result).toBe(false);
    });

    it('should return false for HMAC of wrong length', () => {
      const shortMac = new Uint8Array(16);
      const result = verifyShareHmac(hmacKey, 'share-id-123', undefined, shortMac);
      expect(result).toBe(false);
    });
  });

  describe('encodeShareBlob and decodeShareBlob', () => {
    const version = 0x01;
    const salt = new Uint8Array(16);
    for (let i = 0; i < 16; i++) {
      salt[i] = i;
    }
    const wrappedDek = new Uint8Array(65);
    for (let i = 0; i < 65; i++) {
      wrappedDek[i] = i + 50;
    }
    const hmacValue = new Uint8Array(32);
    for (let i = 0; i < 32; i++) {
      hmacValue[i] = i + 200;
    }

    it('should produce a base64url string', () => {
      const blob = encodeShareBlob(version, salt, wrappedDek, hmacValue);
      expect(typeof blob).toBe('string');
      // base64url: only [A-Za-z0-9_-], no padding
      expect(blob).toMatch(/^[A-Za-z0-9_-]+$/);
    });

    it('should produce a string of approximately 152 characters', () => {
      const blob = encodeShareBlob(version, salt, wrappedDek, hmacValue);
      // 114 bytes -> ceil(114 * 4/3) = 152 base64url chars (no padding)
      expect(blob.length).toBe(152);
    });

    it('should not contain padding characters', () => {
      const blob = encodeShareBlob(version, salt, wrappedDek, hmacValue);
      expect(blob).not.toContain('=');
    });

    it('should round-trip encode and decode correctly', () => {
      const blob = encodeShareBlob(version, salt, wrappedDek, hmacValue);
      const decoded = decodeShareBlob(blob);

      expect(decoded.version).toBe(version);
      expect(decoded.salt).toEqual(salt);
      expect(decoded.wrappedDek).toEqual(wrappedDek);
      expect(decoded.hmac).toEqual(hmacValue);
    });

    it('should preserve all byte values in round-trip', () => {
      // Use bytes with full range of values
      const fullRangeSalt = new Uint8Array(16);
      for (let i = 0; i < 16; i++) fullRangeSalt[i] = i * 16;
      const fullRangeWrappedDek = new Uint8Array(65);
      for (let i = 0; i < 65; i++) fullRangeWrappedDek[i] = (i * 4) % 256;
      const fullRangeHmac = new Uint8Array(32);
      for (let i = 0; i < 32; i++) fullRangeHmac[i] = (255 - i * 8) & 0xff;

      const blob = encodeShareBlob(0x01, fullRangeSalt, fullRangeWrappedDek, fullRangeHmac);
      const decoded = decodeShareBlob(blob);

      expect(decoded.version).toBe(0x01);
      expect(decoded.salt).toEqual(fullRangeSalt);
      expect(decoded.wrappedDek).toEqual(fullRangeWrappedDek);
      expect(decoded.hmac).toEqual(fullRangeHmac);
    });

    it('should throw error for invalid salt length', () => {
      const badSalt = new Uint8Array(8);
      expect(() => encodeShareBlob(version, badSalt, wrappedDek, hmacValue)).toThrow(
        'Salt must be 16 bytes'
      );
    });

    it('should throw error for invalid wrappedDek length', () => {
      const badDek = new Uint8Array(32);
      expect(() => encodeShareBlob(version, salt, badDek, hmacValue)).toThrow(
        'Wrapped DEK must be 65 bytes'
      );
    });

    it('should throw error for invalid HMAC length', () => {
      const badHmac = new Uint8Array(16);
      expect(() => encodeShareBlob(version, salt, wrappedDek, badHmac)).toThrow(
        'HMAC must be 32 bytes'
      );
    });

    it('should throw error for invalid blob string (wrong length)', () => {
      expect(() => decodeShareBlob('abc')).toThrow('Invalid share blob');
    });

    it('should throw error for invalid base64url characters', () => {
      // Create a string of the right length with invalid characters
      const badBlob = '!' + 'A'.repeat(151);
      expect(() => decodeShareBlob(badBlob)).toThrow();
    });

    it('should correctly extract version byte from decoded blob', () => {
      const blobV1 = encodeShareBlob(0x01, salt, wrappedDek, hmacValue);
      const blobV2 = encodeShareBlob(0x02, salt, wrappedDek, hmacValue);

      expect(decodeShareBlob(blobV1).version).toBe(0x01);
      expect(decodeShareBlob(blobV2).version).toBe(0x02);
    });
  });

  describe('integration: deriveShareKeys + computeShareHmac + verifyShareHmac', () => {
    it('should derive keys and verify HMAC end-to-end', async () => {
      const password = 'my-secure-share-password';
      const salt = new Uint8Array(16);
      crypto.getRandomValues(salt);

      const keys = await deriveShareKeys(password, salt);
      const shareId = 'share-abc-123';
      const expiresAt = Math.floor(Date.now() / 1000) + 3600;

      const mac = computeShareHmac(keys.hmacKey, shareId, expiresAt);
      const isValid = verifyShareHmac(keys.hmacKey, shareId, expiresAt, mac);
      expect(isValid).toBe(true);

      // Wrong password should derive different keys -> verification fails
      const wrongKeys = await deriveShareKeys('wrong-password', salt);
      const isInvalid = verifyShareHmac(wrongKeys.hmacKey, shareId, expiresAt, mac);
      expect(isInvalid).toBe(false);
    });
  });

  describe('integration: full blob round-trip with derived keys', () => {
    it('should encode/decode blob with real derived HMAC', async () => {
      const password = 'blob-test-password';
      const salt = new Uint8Array(16);
      crypto.getRandomValues(salt);

      const keys = await deriveShareKeys(password, salt);
      const shareId = 'share-xyz-789';
      const mac = computeShareHmac(keys.hmacKey, shareId);

      // Simulate a wrapped DEK (65 bytes)
      const wrappedDek = new Uint8Array(65);
      crypto.getRandomValues(wrappedDek);

      const blob = encodeShareBlob(0x01, salt, wrappedDek, mac);
      const decoded = decodeShareBlob(blob);

      expect(decoded.version).toBe(0x01);
      expect(decoded.salt).toEqual(salt);
      expect(decoded.wrappedDek).toEqual(wrappedDek);

      // Verify the HMAC extracted from the blob
      const isValid = verifyShareHmac(keys.hmacKey, shareId, undefined, decoded.hmac);
      expect(isValid).toBe(true);
    });
  });
});
