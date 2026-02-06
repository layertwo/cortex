/**
 * Property-Based Tests for Share Encryption Module
 *
 * These tests verify that share keys enable file access without vault password,
 * wrong passwords fail, HMACs detect tampering, and blobs round-trip correctly.
 */

import fc from 'fast-check';
import {
  generateDek,
  wrapDek,
  unwrapDek,
  encryptFileWithDek,
  DekUnwrapError,
} from '../../src/lib/envelope-encryption';
import {
  deriveShareKeys,
  computeShareHmac,
  verifyShareHmac,
  encodeShareBlob,
  decodeShareBlob,
} from '../../src/lib/share-encryption';

describe('Share Encryption Property Tests', () => {
  /**
   * Property 20: Share keys enable file access without vault password
   *
   * Validates the full share workflow:
   * 1. Owner encrypts a file with their vault KEK
   * 2. Owner derives share keys from a password and re-wraps the DEK
   * 3. Recipient derives the same share keys from the same password
   * 4. Recipient unwraps the DEK and decrypts the file content
   * 5. Decrypted content matches the original
   */
  test('Property 20: Share keys enable file access without vault password', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 5000 }),   // file content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),     // vault KEK
        fc.string({ minLength: 1, maxLength: 30 }),          // share password
        async (content, vaultKek, sharePassword) => {
          // OWNER: Encrypt file with vault KEK
          const { encryptedContent, wrappedDek } = await encryptFileWithDek(content, vaultKek);

          // OWNER: Derive share keys from password
          const salt = crypto.getRandomValues(new Uint8Array(16));
          const { encryptionKey: shareKey } = await deriveShareKeys(sharePassword, salt);

          // OWNER: Re-wrap the DEK with share key instead of vault KEK
          const dek = unwrapDek(wrappedDek, vaultKek);
          const shareWrappedDek = await wrapDek(dek, shareKey);
          dek.fill(0); // Zero the DEK after use

          // RECIPIENT: Derive share keys from the same password and salt
          const { encryptionKey: recipientKey } = await deriveShareKeys(sharePassword, salt);

          // RECIPIENT: Unwrap DEK using share key
          const recipientDek = unwrapDek(shareWrappedDek, recipientKey);

          // RECIPIENT: Decrypt the file content directly with chacha20poly1305
          const { chacha20poly1305 } = await import('@noble/ciphers/chacha');
          const nonce = encryptedContent.slice(0, 12);
          const ciphertext = encryptedContent.slice(12);
          const cipher = chacha20poly1305(recipientDek, nonce);
          const decrypted = cipher.decrypt(ciphertext);

          recipientDek.fill(0); // Zero the DEK after use

          // VERIFY: Decrypted content matches original
          expect(decrypted).toEqual(content);
        }
      ),
      { numRuns: 50 }
    );
  }, 600000); // 10 minute timeout for Argon2id

  /**
   * Property 20b: Wrong share password cannot unwrap DEK
   *
   * Validates that a different password produces a different key,
   * causing DEK unwrapping to fail with DekUnwrapError.
   */
  test('Property 20b: Wrong share password cannot unwrap DEK', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 30 }),          // correct password
        fc.string({ minLength: 1, maxLength: 30 }),          // wrong password
        async (correctPassword, wrongPassword) => {
          // Skip if passwords happen to be equal
          if (correctPassword === wrongPassword) {
            return true;
          }

          // Create a share with the correct password
          const salt = crypto.getRandomValues(new Uint8Array(16));
          const { encryptionKey: shareKey } = await deriveShareKeys(correctPassword, salt);

          const dek = await generateDek();
          const shareWrappedDek = await wrapDek(dek, shareKey);
          dek.fill(0);

          // Try to unwrap with wrong password's key
          const { encryptionKey: wrongKey } = await deriveShareKeys(wrongPassword, salt);

          expect(() => unwrapDek(shareWrappedDek, wrongKey)).toThrow(DekUnwrapError);
          return true;
        }
      ),
      { numRuns: 50 }
    );
  }, 600000); // 10 minute timeout for Argon2id

  /**
   * Property 20c: HMAC detects metadata tampering
   *
   * Validates that verifyShareHmac returns true for the correct shareId
   * and false when the shareId has been tampered with.
   */
  test('Property 20c: HMAC detects metadata tampering', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 1, maxLength: 30 }),          // password
        fc.string({ minLength: 1, maxLength: 50 }),          // correct shareId
        fc.string({ minLength: 1, maxLength: 50 }),          // tampered shareId
        fc.integer({ min: 1000000000, max: 2000000000 }),    // expiresAt
        async (password, correctShareId, tamperedShareId, expiresAt) => {
          // Skip if shareIds happen to be equal
          if (correctShareId === tamperedShareId) {
            return true;
          }

          const salt = crypto.getRandomValues(new Uint8Array(16));
          const { hmacKey } = await deriveShareKeys(password, salt);

          // Compute HMAC with correct shareId
          const hmacValue = computeShareHmac(hmacKey, correctShareId, expiresAt);

          // Verify with correct shareId should return true
          expect(verifyShareHmac(hmacKey, correctShareId, expiresAt, hmacValue)).toBe(true);

          // Verify with tampered shareId should return false
          expect(verifyShareHmac(hmacKey, tamperedShareId, expiresAt, hmacValue)).toBe(false);

          return true;
        }
      ),
      { numRuns: 50 }
    );
  }, 600000); // 10 minute timeout for Argon2id

  /**
   * Property 20d: Share blob encode/decode round-trip
   *
   * Validates that encoding a share blob and decoding it produces
   * the exact same component fields.
   */
  test('Property 20d: Share blob encode/decode round-trip', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 16, maxLength: 16 }),     // salt
        fc.uint8Array({ minLength: 65, maxLength: 65 }),     // wrappedDek
        fc.uint8Array({ minLength: 32, maxLength: 32 }),     // hmac
        async (salt, wrappedDek, hmacValue) => {
          const version = 0x01;

          // Encode to base64url
          const encoded = encodeShareBlob(version, salt, wrappedDek, hmacValue);

          // Decode back
          const decoded = decodeShareBlob(encoded);

          // Verify all fields match
          expect(decoded.version).toBe(version);
          expect(decoded.salt).toEqual(salt);
          expect(decoded.wrappedDek).toEqual(wrappedDek);
          expect(decoded.hmac).toEqual(hmacValue);
        }
      ),
      { numRuns: 100 }
    );
  });
});
