/**
 * Property-Based Tests for Encryption Module
 * 
 * These tests verify universal properties that should hold for all inputs.
 */

import fc from 'fast-check';
import { encrypt, decrypt, encryptTagForSearch } from '../../src/lib/encryption';

describe('Encryption Property Tests', () => {
  /**
   * Feature: cortex-backup, Property 7: Upload and download round-trip preserves content
   * 
   * Validates: Requirements 4.2
   * 
   * This property ensures that encrypting and then decrypting data returns the original content.
   * For any plaintext data and encryption key, the round-trip operation (encrypt → decrypt)
   * must preserve the original data exactly.
   */
  test('Property 7: Encryption round-trip preserves content', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 0, maxLength: 10000 }), // plaintext data
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // 256-bit encryption key
        async (plaintext, key) => {
          // Encrypt the plaintext
          const encrypted = await encrypt(plaintext, key);
          
          // Decrypt the ciphertext
          const decrypted = decrypt(encrypted, key);
          
          // Verify the decrypted data matches the original plaintext
          expect(decrypted).toEqual(plaintext);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: cortex-backup, Property 13: Encrypted tag search functionality
   * 
   * Validates: Requirements 11.4, 11.5
   * 
   * This property ensures that tag encryption is deterministic and consistent.
   * The same tag encrypted with the same key and vaultId must always produce 
   * the same output, enabling server-side exact match searches without revealing 
   * plaintext tags. Additionally, tag normalization (lowercase) must be applied 
   * consistently.
   */
  test('Property 13: Tag encryption is deterministic and consistent', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 50 }), // tag text
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // 256-bit encryption key
        fc.string({ minLength: 1, maxLength: 50 }), // vaultId
        (tag, key, vaultId) => {
          // Skip if tag or vaultId is empty/whitespace-only after trimming
          if (tag.trim().length === 0 || vaultId.trim().length === 0) {
            return true;
          }
          
          // Encrypt the tag twice with same vaultId
          const encrypted1 = encryptTagForSearch(tag, key, vaultId);
          const encrypted2 = encryptTagForSearch(tag, key, vaultId);
          
          // Verify both encryptions produce identical output (deterministic)
          expect(encrypted1).toEqual(encrypted2);
          
          // Verify case-insensitive consistency (normalization)
          const upperTag = tag.toUpperCase();
          const lowerTag = tag.toLowerCase();
          const encryptedUpper = encryptTagForSearch(upperTag, key, vaultId);
          const encryptedLower = encryptTagForSearch(lowerTag, key, vaultId);
          
          // Both should produce the same encrypted output
          expect(encryptedUpper).toEqual(encryptedLower);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: cortex-backup, Property 14: Vault isolation for encrypted tags
   * 
   * Validates: Requirements 11.4 (security enhancement)
   * 
   * This property ensures that the same tag in different vaults produces
   * different encrypted values. This prevents cross-vault tag correlation
   * and limits frequency analysis to per-vault scope.
   */
  test('Property 14: Vault isolation prevents cross-vault tag correlation', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 50 }), // tag text
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // 256-bit encryption key
        fc.string({ minLength: 1, maxLength: 50 }), // vaultId1
        fc.string({ minLength: 1, maxLength: 50 }), // vaultId2
        (tag, key, vaultId1, vaultId2) => {
          // Skip if tag or vaultIds are empty/whitespace-only after trimming
          if (tag.trim().length === 0 || vaultId1.trim().length === 0 || vaultId2.trim().length === 0) {
            return true;
          }
          
          // Skip if vaultIds are identical
          if (vaultId1 === vaultId2) {
            return true;
          }
          
          // Encrypt same tag in different vaults
          const encrypted1 = encryptTagForSearch(tag, key, vaultId1);
          const encrypted2 = encryptTagForSearch(tag, key, vaultId2);
          
          // Encrypted values must be different
          expect(encrypted1).not.toEqual(encrypted2);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: cortex-backup, Property 15: Tag padding consistency
   * 
   * Validates: Requirements 11.4 (security enhancement)
   * 
   * This property ensures that all encrypted tags have the same output length
   * regardless of input tag length. This prevents length-based frequency analysis
   * and hides information about tag length.
   */
  test('Property 15: Tag padding produces consistent output length', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 100 }), // tag text (varying length)
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // 256-bit encryption key
        fc.string({ minLength: 1, maxLength: 50 }), // vaultId
        (tag, key, vaultId) => {
          // Skip if tag or vaultId is empty/whitespace-only after trimming
          if (tag.trim().length === 0 || vaultId.trim().length === 0) {
            return true;
          }
          
          // Encrypt the tag
          const encrypted = encryptTagForSearch(tag, key, vaultId);
          
          // All encrypted tags should be 32 bytes (SHA256 output)
          expect(encrypted.length).toBe(32);
          
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: cortex-backup, Property 16: Cross-vault uniqueness
   * 
   * Validates: Requirements 11.4 (security enhancement)
   * 
   * This property verifies that encrypted tags are unique across vault boundaries.
   * Even with the same key, different vaults produce different encrypted values
   * for the same tag, ensuring proper vault isolation.
   */
  test('Property 16: Cross-vault uniqueness for all tag combinations', () => {
    fc.assert(
      fc.property(
        fc.array(fc.string({ minLength: 1, maxLength: 50 }), { minLength: 1, maxLength: 10 }), // tags
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // 256-bit encryption key
        fc.array(fc.string({ minLength: 1, maxLength: 50 }), { minLength: 2, maxLength: 5 }), // vaultIds
        (tags, key, vaultIds) => {
          // Filter out whitespace-only tags and vaultIds
          const validTags = tags.filter(tag => tag.trim().length > 0);
          const validVaultIds = vaultIds.filter(vaultId => vaultId.trim().length > 0);
          
          // Deduplicate vaultIds
          const uniqueVaultIds = Array.from(new Set(validVaultIds));
          
          // Skip if we don't have valid inputs
          if (validTags.length === 0 || uniqueVaultIds.length < 2) {
            return true;
          }
          
          // Encrypt all tags in all vaults
          const encryptedMap = new Map<string, Uint8Array>();
          
          for (const tag of validTags) {
            for (const vaultId of uniqueVaultIds) {
              const encrypted = encryptTagForSearch(tag, key, vaultId);
              const mapKey = `${tag}:${vaultId}`;
              
              // Store encrypted value
              encryptedMap.set(mapKey, encrypted);
            }
          }
          
          // Verify that same tag in different vaults has different encrypted values
          for (const tag of validTags) {
            const vaultEncryptions = uniqueVaultIds.map(vaultId => 
              encryptedMap.get(`${tag}:${vaultId}`)!
            );
            
            // Check all pairs are different
            for (let i = 0; i < vaultEncryptions.length; i++) {
              for (let j = i + 1; j < vaultEncryptions.length; j++) {
                expect(vaultEncryptions[i]).not.toEqual(vaultEncryptions[j]);
              }
            }
          }
          
          return true;
        }
      ),
      { numRuns: 50 } // Fewer runs since this is more complex
    );
  });

  /**
   * Additional property: Different keys produce different ciphertexts
   * 
   * This ensures that encryption with different keys produces different outputs,
   * which is essential for security (key separation).
   */
  test('Property: Different keys produce different ciphertexts', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // plaintext data
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // key1
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // key2
        async (plaintext, key1, key2) => {
          // Skip if keys are identical
          if (Buffer.from(key1).equals(Buffer.from(key2))) {
            return true;
          }
          
          // Encrypt with both keys
          const encrypted1 = await encrypt(plaintext, key1);
          const encrypted2 = await encrypt(plaintext, key2);
          
          // Verify ciphertexts are different
          expect(encrypted1).not.toEqual(encrypted2);
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Additional property: Encrypted data is different from plaintext
   * 
   * This ensures that encryption actually transforms the data (except for
   * the trivial case of empty input).
   */
  test('Property: Encrypted data differs from plaintext', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // non-empty plaintext
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // encryption key
        async (plaintext, key) => {
          const encrypted = await encrypt(plaintext, key);
          
          // Encrypted data should be longer (includes nonce and tag)
          expect(encrypted.length).toBeGreaterThan(plaintext.length);
          
          // Encrypted data should not equal plaintext
          expect(encrypted).not.toEqual(plaintext);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Additional property: Decryption with wrong key fails
   * 
   * This ensures that authentication works correctly - decryption should fail
   * if the wrong key is used.
   */
  test('Property: Decryption with wrong key throws error', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // plaintext
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // correct key
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // wrong key
        async (plaintext, correctKey, wrongKey) => {
          // Skip if keys are identical
          if (Buffer.from(correctKey).equals(Buffer.from(wrongKey))) {
            return true;
          }
          
          // Encrypt with correct key
          const encrypted = await encrypt(plaintext, correctKey);
          
          // Attempt to decrypt with wrong key should throw
          expect(() => decrypt(encrypted, wrongKey)).toThrow();
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});
