/**
 * Property-Based Tests for Envelope Encryption Module
 *
 * These tests verify universal properties that should hold for all inputs.
 */

import fc from 'fast-check';
import {
  generateDek,
  wrapDek,
  unwrapDek,
  encryptFileWithDek,
  decryptFileWithDek,
  DekUnwrapError,
} from '../../src/lib/envelope-encryption';

describe('Envelope Encryption Property Tests', () => {
  /**
   * Feature: cortex-backup, Property 32: Envelope encryption round-trip
   *
   * Validates: Requirements 28.1, 28.2, 28.3, 29.2, 29.3
   *
   * For random content, random KEK, and optional fileId:
   * - encryptFileWithDek then decryptFileWithDek returns original content
   * - Encrypted content differs from plaintext
   * - Wrapped DEK is 65 bytes (no fileId) or 97 bytes (with fileId)
   * - Version byte is 0x01
   */
  test('Property 32: Envelope encryption round-trip (without fileId)', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 0, maxLength: 10000 }), // file content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),    // KEK
        async (content, kek) => {
          const { encryptedContent, wrappedDek } = await encryptFileWithDek(content, kek);

          // Wrapped DEK is 65 bytes without fileId
          expect(wrappedDek.length).toBe(65);

          // Version byte is 0x01
          expect(wrappedDek[0]).toBe(0x01);

          // Encrypted content differs from plaintext (for non-empty content)
          if (content.length > 0) {
            expect(encryptedContent).not.toEqual(content);
          }

          // Round-trip returns original content
          const decrypted = decryptFileWithDek(encryptedContent, wrappedDek, kek);
          expect(decrypted).toEqual(content);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('Property 32: Envelope encryption round-trip (with fileId)', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 0, maxLength: 10000 }), // file content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),    // KEK
        fc.string({ minLength: 1, maxLength: 50 }),         // fileId
        async (content, kek, fileId) => {
          const { encryptedContent, wrappedDek } = await encryptFileWithDek(content, kek, fileId);

          // Wrapped DEK is 97 bytes with fileId
          expect(wrappedDek.length).toBe(97);

          // Version byte is 0x01
          expect(wrappedDek[0]).toBe(0x01);

          // Encrypted content differs from plaintext (for non-empty content)
          if (content.length > 0) {
            expect(encryptedContent).not.toEqual(content);
          }

          // Round-trip returns original content
          const decrypted = decryptFileWithDek(encryptedContent, wrappedDek, kek, fileId);
          expect(decrypted).toEqual(content);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('Property 32: wrapDek/unwrapDek round-trip preserves DEK', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // DEK
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // KEK
        async (dek, kek) => {
          const wrapped = await wrapDek(dek, kek);
          const unwrapped = unwrapDek(wrapped, kek);
          expect(unwrapped).toEqual(dek);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('Property 32: wrapDek/unwrapDek round-trip with HMAC binding', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // DEK
        fc.uint8Array({ minLength: 32, maxLength: 32 }), // KEK
        fc.string({ minLength: 1, maxLength: 50 }),       // fileId
        async (dek, kek, fileId) => {
          const wrapped = await wrapDek(dek, kek, fileId);
          const unwrapped = unwrapDek(wrapped, kek, fileId);
          expect(unwrapped).toEqual(dek);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('Property 32: Wrong KEK fails decryption', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),   // correct KEK
        fc.uint8Array({ minLength: 32, maxLength: 32 }),   // wrong KEK
        async (content, correctKek, wrongKek) => {
          if (Buffer.from(correctKek).equals(Buffer.from(wrongKek))) {
            return true;
          }

          const { encryptedContent, wrappedDek } = await encryptFileWithDek(content, correctKek);

          expect(() => decryptFileWithDek(encryptedContent, wrappedDek, wrongKek)).toThrow(DekUnwrapError);
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  test('Property 32: Wrong fileId fails HMAC verification', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),   // KEK
        fc.string({ minLength: 1, maxLength: 50 }),        // correct fileId
        fc.string({ minLength: 1, maxLength: 50 }),        // wrong fileId
        async (content, kek, correctFileId, wrongFileId) => {
          if (correctFileId === wrongFileId) {
            return true;
          }

          const { encryptedContent, wrappedDek } = await encryptFileWithDek(content, kek, correctFileId);

          expect(() => decryptFileWithDek(encryptedContent, wrappedDek, kek, wrongFileId)).toThrow(DekUnwrapError);
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: cortex-backup, Property 33: DEK uniqueness
   *
   * Validates: Requirements 28.4, 28.5
   *
   * - 100 calls to generateDek() produce 100 unique 32-byte keys
   * - Two files encrypted with the same KEK produce different wrapped DEKs
   */
  test('Property 33: generateDek produces unique 32-byte keys', async () => {
    const deks: Uint8Array[] = [];
    for (let i = 0; i < 100; i++) {
      deks.push(await generateDek());
    }

    // All should be 32 bytes
    for (const dek of deks) {
      expect(dek.length).toBe(32);
    }

    // All should be unique
    const dekStrings = new Set(deks.map(d => Buffer.from(d).toString('hex')));
    expect(dekStrings.size).toBe(100);
  });

  test('Property 33: Two files encrypted with same KEK produce different wrapped DEKs', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // content1
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // content2
        fc.uint8Array({ minLength: 32, maxLength: 32 }),   // shared KEK
        async (content1, content2, kek) => {
          const result1 = await encryptFileWithDek(content1, kek);
          const result2 = await encryptFileWithDek(content2, kek);

          // Wrapped DEKs must be different (different random DEKs + nonces)
          expect(result1.wrappedDek).not.toEqual(result2.wrappedDek);

          // Encrypted content must be different
          expect(result1.encryptedContent).not.toEqual(result2.encryptedContent);
        }
      ),
      { numRuns: 100 }
    );
  });

  test('Property 33: Same content encrypted twice produces different outputs', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 1000 }), // same content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),   // same KEK
        async (content, kek) => {
          const result1 = await encryptFileWithDek(content, kek);
          const result2 = await encryptFileWithDek(content, kek);

          // Even with identical inputs, outputs differ (unique DEKs + nonces)
          expect(result1.wrappedDek).not.toEqual(result2.wrappedDek);
          expect(result1.encryptedContent).not.toEqual(result2.encryptedContent);

          // But both decrypt to the same content
          const decrypted1 = decryptFileWithDek(result1.encryptedContent, result1.wrappedDek, kek);
          const decrypted2 = decryptFileWithDek(result2.encryptedContent, result2.wrappedDek, kek);
          expect(decrypted1).toEqual(content);
          expect(decrypted2).toEqual(content);
        }
      ),
      { numRuns: 100 }
    );
  });
});
