/**
 * Unit tests for key management functions
 * 
 * Note: Tests for deriveVaultMasterKey are skipped in Node.js environment
 * because argon2-browser requires WebAssembly which is browser-specific.
 * These functions should be tested in a browser environment or with integration tests.
 */

import {
  deriveVaultMasterKey,
  deriveKeys,
  generateRecoveryKey,
  validateRecoveryKey,
} from '../../src/lib/key-management';

describe('Key Management', () => {
  // Create a mock master key for testing (32 bytes)
  const createMockMasterKey = (): Uint8Array => {
    const key = new Uint8Array(32);
    crypto.getRandomValues(key);
    return key;
  };

  describe('deriveKeys', () => {
    it('should derive all required keys from master key', () => {
      const masterKey = createMockMasterKey();

      const keys = deriveKeys(masterKey);

      expect(keys.keyEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.keyEncryptionKey.length).toBe(32);
      expect(keys.metadataEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.metadataEncryptionKey.length).toBe(32);
      expect(keys.shareKeyDerivationKey).toBeInstanceOf(Uint8Array);
      expect(keys.shareKeyDerivationKey.length).toBe(32);
      expect(keys.notesEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.notesEncryptionKey.length).toBe(32);
      expect(keys.tasksEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.tasksEncryptionKey.length).toBe(32);
      expect(keys.eventsEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.eventsEncryptionKey.length).toBe(32);
      expect(keys.notificationEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.notificationEncryptionKey.length).toBe(32);
      expect(keys.dateBucketEncryptionKey).toBeInstanceOf(Uint8Array);
      expect(keys.dateBucketEncryptionKey.length).toBe(32);
    });

    it('should derive different keys for each purpose', () => {
      const masterKey = createMockMasterKey();

      const keys = deriveKeys(masterKey);

      // All keys should be different from each other
      const keyArray = [
        keys.keyEncryptionKey,
        keys.metadataEncryptionKey,
        keys.shareKeyDerivationKey,
        keys.notesEncryptionKey,
        keys.tasksEncryptionKey,
        keys.eventsEncryptionKey,
        keys.notificationEncryptionKey,
        keys.dateBucketEncryptionKey,
      ];

      for (let i = 0; i < keyArray.length; i++) {
        for (let j = i + 1; j < keyArray.length; j++) {
          expect(keyArray[i]).not.toEqual(keyArray[j]);
        }
      }
    });

    it('should derive the same keys for the same master key', () => {
      const masterKey = createMockMasterKey();

      const keys1 = deriveKeys(masterKey);
      const keys2 = deriveKeys(masterKey);

      expect(keys1.keyEncryptionKey).toEqual(keys2.keyEncryptionKey);
      expect(keys1.metadataEncryptionKey).toEqual(keys2.metadataEncryptionKey);
      expect(keys1.shareKeyDerivationKey).toEqual(keys2.shareKeyDerivationKey);
      expect(keys1.notesEncryptionKey).toEqual(keys2.notesEncryptionKey);
      expect(keys1.tasksEncryptionKey).toEqual(keys2.tasksEncryptionKey);
      expect(keys1.eventsEncryptionKey).toEqual(keys2.eventsEncryptionKey);
      expect(keys1.notificationEncryptionKey).toEqual(keys2.notificationEncryptionKey);
      expect(keys1.dateBucketEncryptionKey).toEqual(keys2.dateBucketEncryptionKey);
    });

    it('should throw error for invalid master key length', () => {
      const invalidKey = new Uint8Array(16); // Wrong length

      expect(() => deriveKeys(invalidKey)).toThrow('Vault master key must be 32 bytes');
    });

    it('derives a 32-byte saltHmacKey distinct from all other derived keys', async () => {
      const salt = new Uint8Array(16).fill(0x42);
      const masterKey = await deriveVaultMasterKey('correct horse battery staple 12', salt);
      const keys = deriveKeys(masterKey);

      expect(keys.saltHmacKey).toBeInstanceOf(Uint8Array);
      expect(keys.saltHmacKey).toHaveLength(32);

      const others = [
        keys.keyEncryptionKey,
        keys.metadataEncryptionKey,
        keys.shareKeyDerivationKey,
        keys.notesEncryptionKey,
        keys.tasksEncryptionKey,
        keys.eventsEncryptionKey,
        keys.notificationEncryptionKey,
        keys.dateBucketEncryptionKey,
      ];
      for (const other of others) {
        expect(Buffer.from(keys.saltHmacKey).equals(Buffer.from(other))).toBe(false);
      }
    });
  });

  describe('deriveVaultMasterKey', () => {
    const KAT_SALT = new Uint8Array(16).fill(0x42);
    // Argon2id(t=3, m=64MB, p=4, dkLen=32) over UTF-8 "correct horse battery staple 12".
    // Standardized KDF → identical across implementations; pins the swap to @noble/hashes.
    const KAT_HEX = '5c88eecd72d28909ed99588a8f9b9ca80d7a7f65429dcd450a0d832371bf43b3';

    it('matches the Argon2id known-answer vector', async () => {
      const mk = await deriveVaultMasterKey('correct horse battery staple 12', KAT_SALT);
      expect(mk).toBeInstanceOf(Uint8Array);
      expect(mk).toHaveLength(32);
      expect(Buffer.from(mk).toString('hex')).toBe(KAT_HEX);
    });

    it('is deterministic for the same password and salt', async () => {
      const a = await deriveVaultMasterKey('pw-123', KAT_SALT);
      const b = await deriveVaultMasterKey('pw-123', KAT_SALT);
      expect(Buffer.from(a).equals(Buffer.from(b))).toBe(true);
    });

    it('rejects an empty password and a too-short salt', async () => {
      await expect(deriveVaultMasterKey('', KAT_SALT)).rejects.toThrow('Password cannot be empty');
      await expect(deriveVaultMasterKey('pw', new Uint8Array(8))).rejects.toThrow(
        'at least 16 bytes',
      );
    });
  });

  describe('generateRecoveryKey and validateRecoveryKey', () => {
    it('should generate a valid BIP39 mnemonic', () => {
      const masterKey = createMockMasterKey();

      const recoveryKey = generateRecoveryKey(masterKey);

      expect(typeof recoveryKey).toBe('string');
      expect(recoveryKey.split(' ').length).toBe(24); // 24-word mnemonic (256 bits)
    });

    it('should validate and recover full master key from recovery key', () => {
      const masterKey = createMockMasterKey();

      const recoveryKey = generateRecoveryKey(masterKey);
      const recoveredMasterKey = validateRecoveryKey(recoveryKey);

      expect(recoveredMasterKey).toBeInstanceOf(Uint8Array);
      expect(recoveredMasterKey.length).toBe(32); // Full 256-bit master key
      
      // The recovered master key should match the original master key exactly
      expect(recoveredMasterKey).toEqual(masterKey);
    });

    it('should throw error for invalid recovery key format', () => {
      const invalidKey = 'not a valid mnemonic phrase';

      expect(() => validateRecoveryKey(invalidKey)).toThrow('Invalid recovery key format');
    });

    it('should throw error for empty recovery key', () => {
      expect(() => validateRecoveryKey('')).toThrow('Recovery key must be a non-empty string');
    });

    it('should generate different recovery keys for different master keys', () => {
      const masterKey1 = createMockMasterKey();
      const masterKey2 = createMockMasterKey();

      const recoveryKey1 = generateRecoveryKey(masterKey1);
      const recoveryKey2 = generateRecoveryKey(masterKey2);

      expect(recoveryKey1).not.toBe(recoveryKey2);
    });
  });
});
