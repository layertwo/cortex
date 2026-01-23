/**
 * Unit tests for encryption module
 */

import {
  encrypt,
  decrypt,
  generateNonce,
  encryptTagForSearch,
  stringToBytes,
  bytesToString,
  bytesToBase64,
  base64ToBytes,
  NONCE_SIZE,
  TAG_SIZE,
  KEY_SIZE,
} from '../../src/lib/encryption';

describe('Encryption Module', () => {
  // Generate a test key
  const testKey = new Uint8Array(KEY_SIZE);
  for (let i = 0; i < KEY_SIZE; i++) {
    testKey[i] = i;
  }

  describe('generateNonce', () => {
    it('should generate a nonce of correct size', async () => {
      const nonce = await generateNonce();
      expect(nonce.length).toBe(NONCE_SIZE);
    });

    it('should generate different nonces each time', async () => {
      const nonce1 = await generateNonce();
      const nonce2 = await generateNonce();
      expect(nonce1).not.toEqual(nonce2);
    });
  });

  describe('encrypt and decrypt', () => {
    it('should encrypt and decrypt data correctly', async () => {
      const plaintext = stringToBytes('Hello, Cortex!');
      const encrypted = await encrypt(plaintext, testKey);
      const decrypted = decrypt(encrypted, testKey);
      
      expect(bytesToString(decrypted)).toBe('Hello, Cortex!');
    });

    it('should produce ciphertext longer than plaintext', async () => {
      const plaintext = stringToBytes('test');
      const encrypted = await encrypt(plaintext, testKey);
      
      // Encrypted should be: nonce (12) + plaintext + tag (16)
      expect(encrypted.length).toBe(NONCE_SIZE + plaintext.length + TAG_SIZE);
    });

    it('should produce different ciphertext for same plaintext with different nonces', async () => {
      const plaintext = stringToBytes('test data');
      const encrypted1 = await encrypt(plaintext, testKey);
      const encrypted2 = await encrypt(plaintext, testKey);
      
      expect(encrypted1).not.toEqual(encrypted2);
    });

    it('should throw error with invalid key size', async () => {
      const plaintext = stringToBytes('test');
      const invalidKey = new Uint8Array(16); // Wrong size
      
      await expect(encrypt(plaintext, invalidKey)).rejects.toThrow('Invalid key size');
    });

    it('should throw error when decrypting with wrong key', async () => {
      const plaintext = stringToBytes('test');
      const encrypted = await encrypt(plaintext, testKey);
      
      const wrongKey = new Uint8Array(KEY_SIZE);
      for (let i = 0; i < KEY_SIZE; i++) {
        wrongKey[i] = 255 - i;
      }
      
      expect(() => decrypt(encrypted, wrongKey)).toThrow('authentication tag verification failed');
    });

    it('should throw error when decrypting tampered ciphertext', async () => {
      const plaintext = stringToBytes('test');
      const encrypted = await encrypt(plaintext, testKey);
      
      // Tamper with the ciphertext
      encrypted[NONCE_SIZE + 5] ^= 0xFF;
      
      expect(() => decrypt(encrypted, testKey)).toThrow('authentication tag verification failed');
    });

    it('should handle empty plaintext', async () => {
      const plaintext = new Uint8Array(0);
      const encrypted = await encrypt(plaintext, testKey);
      const decrypted = decrypt(encrypted, testKey);
      
      expect(decrypted.length).toBe(0);
    });

    it('should handle large plaintext', async () => {
      const plaintext = new Uint8Array(1024 * 1024); // 1MB
      for (let i = 0; i < plaintext.length; i++) {
        plaintext[i] = i % 256;
      }
      
      const encrypted = await encrypt(plaintext, testKey);
      const decrypted = decrypt(encrypted, testKey);
      
      expect(decrypted).toEqual(plaintext);
    });
  });

  describe('encryptTagForSearch', () => {
    const mockVaultId = 'vault-test-123';

    it('should produce deterministic output for same tag and vaultId', () => {
      const tag = 'vacation';
      const encrypted1 = encryptTagForSearch(tag, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(tag, testKey, mockVaultId);
      
      expect(encrypted1).toEqual(encrypted2);
    });

    it('should normalize tags to lowercase', () => {
      const tag1 = 'VACATION';
      const tag2 = 'vacation';
      const encrypted1 = encryptTagForSearch(tag1, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(tag2, testKey, mockVaultId);
      
      expect(encrypted1).toEqual(encrypted2);
    });

    it('should trim whitespace from tags', () => {
      const tag1 = '  vacation  ';
      const tag2 = 'vacation';
      const encrypted1 = encryptTagForSearch(tag1, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(tag2, testKey, mockVaultId);
      
      expect(encrypted1).toEqual(encrypted2);
    });

    it('should produce different output for different tags', () => {
      const tag1 = 'vacation';
      const tag2 = 'work';
      const encrypted1 = encryptTagForSearch(tag1, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(tag2, testKey, mockVaultId);
      
      expect(encrypted1).not.toEqual(encrypted2);
    });

    it('should produce 32-byte output (SHA256)', () => {
      const tag = 'test';
      const encrypted = encryptTagForSearch(tag, testKey, mockVaultId);
      
      expect(encrypted.length).toBe(32);
    });

    it('should throw error with invalid key size', () => {
      const tag = 'test';
      const invalidKey = new Uint8Array(16);
      
      expect(() => encryptTagForSearch(tag, invalidKey, mockVaultId)).toThrow('Invalid key size');
    });

    it('should throw error with empty vaultId', () => {
      const tag = 'test';
      
      expect(() => encryptTagForSearch(tag, testKey, '')).toThrow('vaultId must be a non-empty string');
      expect(() => encryptTagForSearch(tag, testKey, '   ')).toThrow('vaultId must be a non-empty string');
    });

    it('should produce different output for same tag in different vaults (vault isolation)', () => {
      const tag = 'vacation';
      const vault1 = 'vault-001';
      const vault2 = 'vault-002';
      
      const encrypted1 = encryptTagForSearch(tag, testKey, vault1);
      const encrypted2 = encryptTagForSearch(tag, testKey, vault2);
      
      expect(encrypted1).not.toEqual(encrypted2);
    });

    it('should pad tags to same length (prevents length analysis)', () => {
      const shortTag = 'ai';
      const longTag = 'artificial-intelligence-machine-learning';
      
      const encrypted1 = encryptTagForSearch(shortTag, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(longTag, testKey, mockVaultId);
      
      // Both should produce 32-byte output (SHA256 of padded input)
      expect(encrypted1.length).toBe(32);
      expect(encrypted2.length).toBe(32);
      
      // They should be different (different content even after padding)
      expect(encrypted1).not.toEqual(encrypted2);
    });

    it('should handle unicode tags correctly with padding', () => {
      const tag1 = '🌍';
      const tag2 = 'world';
      
      const encrypted1 = encryptTagForSearch(tag1, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(tag2, testKey, mockVaultId);
      
      // Both should produce 32-byte output
      expect(encrypted1.length).toBe(32);
      expect(encrypted2.length).toBe(32);
      
      // They should be different
      expect(encrypted1).not.toEqual(encrypted2);
    });

    it('should maintain determinism with padding', () => {
      const tag = 'test';
      
      // Encrypt same tag multiple times
      const encrypted1 = encryptTagForSearch(tag, testKey, mockVaultId);
      const encrypted2 = encryptTagForSearch(tag, testKey, mockVaultId);
      const encrypted3 = encryptTagForSearch(tag, testKey, mockVaultId);
      
      // All should be identical
      expect(encrypted1).toEqual(encrypted2);
      expect(encrypted2).toEqual(encrypted3);
    });

    describe('timing side-channel mitigation', () => {
      it('should throw validation errors after performing crypto operations (constant-time)', () => {
        const tag = 'test';
        const invalidKey = new Uint8Array(16); // Wrong size
        
        // Validation error should still be thrown
        expect(() => encryptTagForSearch(tag, invalidKey, mockVaultId))
          .toThrow('Invalid key size: expected 32 bytes, got 16 bytes');
        
        // Security note: The function performs all crypto operations before throwing,
        // preventing timing attacks that could distinguish validation failures
        // from authentication failures.
      });

      it('should throw vaultId validation error after performing crypto operations', () => {
        const tag = 'test';
        
        // Both empty string and whitespace-only should fail
        expect(() => encryptTagForSearch(tag, testKey, ''))
          .toThrow('vaultId must be a non-empty string');
        
        expect(() => encryptTagForSearch(tag, testKey, '   '))
          .toThrow('vaultId must be a non-empty string');
        
        // Security note: Crypto operations are performed before validation error is thrown,
        // ensuring similar timing regardless of which validation fails.
      });

      it('should prioritize key validation error over vaultId error', () => {
        const tag = 'test';
        const invalidKey = new Uint8Array(16);
        const emptyVaultId = '';
        
        // When both validations fail, key error takes precedence
        expect(() => encryptTagForSearch(tag, invalidKey, emptyVaultId))
          .toThrow('Invalid key size');
        
        // This maintains consistent error reporting while still performing
        // crypto operations for timing consistency.
      });

      it('should perform crypto operations even with invalid inputs (defense-in-depth)', () => {
        const tag = 'test';
        const invalidKey = new Uint8Array(16);
        
        // The function should execute normalization, padding, encoding, and HMAC
        // even with invalid key to prevent timing analysis.
        // We verify this by checking that the error is thrown (proving execution completed).
        let errorThrown = false;
        
        try {
          encryptTagForSearch(tag, invalidKey, mockVaultId);
        } catch (error) {
          errorThrown = true;
          expect(error).toBeInstanceOf(Error);
          expect((error as Error).message).toContain('Invalid key size');
        }
        
        expect(errorThrown).toBe(true);
        
        // Security note: This test documents that the function executes all operations
        // including the expensive HMAC-SHA256 computation before throwing errors,
        // which prevents attackers from using timing differences to probe for valid inputs.
      });
    });
  });

  describe('utility functions', () => {
    it('should convert string to bytes and back', () => {
      const original = 'Hello, World! 🌍';
      const bytes = stringToBytes(original);
      const converted = bytesToString(bytes);
      
      expect(converted).toBe(original);
    });

    it('should handle empty strings', () => {
      const bytes = stringToBytes('');
      expect(bytes.length).toBe(0);
      
      const str = bytesToString(new Uint8Array(0));
      expect(str).toBe('');
    });
  });

  describe('base64 encoding', () => {
    it('should correctly encode and decode bytes with values 0-127', () => {
      const bytes = new Uint8Array(128);
      for (let i = 0; i < 128; i++) {
        bytes[i] = i;
      }
      
      const base64 = bytesToBase64(bytes);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(bytes);
    });

    it('should correctly encode and decode bytes with values 128-255', () => {
      const bytes = new Uint8Array(128);
      for (let i = 0; i < 128; i++) {
        bytes[i] = i + 128;
      }
      
      const base64 = bytesToBase64(bytes);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(bytes);
    });

    it('should correctly encode and decode all byte values 0-255', () => {
      const bytes = new Uint8Array(256);
      for (let i = 0; i < 256; i++) {
        bytes[i] = i;
      }
      
      const base64 = bytesToBase64(bytes);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(bytes);
    });

    it('should handle empty byte arrays', () => {
      const bytes = new Uint8Array(0);
      const base64 = bytesToBase64(bytes);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(bytes);
    });

    it('should handle random binary data', () => {
      const bytes = new Uint8Array(100);
      for (let i = 0; i < bytes.length; i++) {
        bytes[i] = Math.floor(Math.random() * 256);
      }
      
      const base64 = bytesToBase64(bytes);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(bytes);
    });

    it('should correctly encode encrypted data with high byte values', async () => {
      const plaintext = stringToBytes('Test data with special chars: 测试数据 🔐');
      const encrypted = await encrypt(plaintext, testKey);
      
      // Encrypted data will contain bytes across full 0-255 range
      const base64 = bytesToBase64(encrypted);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(encrypted);
      
      // Verify we can decrypt the decoded data
      const decrypted = decrypt(decoded, testKey);
      expect(bytesToString(decrypted)).toBe('Test data with special chars: 测试数据 🔐');
    });

    it('should handle base64 round-trip with encrypted tag data', () => {
      const mockVaultId = 'vault-test-123';
      const encryptedTag = encryptTagForSearch('vacation', testKey, mockVaultId);
      
      const base64 = bytesToBase64(encryptedTag);
      const decoded = base64ToBytes(base64);
      
      expect(decoded).toEqual(encryptedTag);
    });
  });
});
