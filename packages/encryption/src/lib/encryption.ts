/**
 * Cortex Encryption Library
 * 
 * Implements ChaCha20-Poly1305 authenticated encryption for zero-knowledge architecture.
 * All encryption happens client-side before transmission to server.
 * 
 * Encryption format: [nonce (12 bytes)][encrypted data][auth tag (16 bytes)]
 * 
 * Requirements: 1.1, 2.1, 9.1, 11.2, 11.4
 */

import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { hmac } from '@noble/hashes/hmac.js';
import { sha256 } from '@noble/hashes/sha2.js';

// Use Web Crypto API for random bytes generation
const getRandomBytes = async (size: number): Promise<Uint8Array> => {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    return crypto.getRandomValues(new Uint8Array(size));
  }
  try {
    const { randomBytes } = await import('node:crypto');
    return new Uint8Array(randomBytes(size));
  } catch {
    throw new Error('No secure random number generator available');
  }
};

/**
 * Nonce size for ChaCha20-Poly1305 (96 bits / 12 bytes)
 */
export const NONCE_SIZE = 12;

/**
 * Authentication tag size for Poly1305 (128 bits / 16 bytes)
 */
export const TAG_SIZE = 16;

/**
 * Encryption key size (256 bits / 32 bytes)
 */
export const KEY_SIZE = 32;

/**
 * Generate a cryptographically secure random nonce for ChaCha20-Poly1305.
 * Each encryption operation must use a unique nonce.
 * 
 * @returns A 12-byte (96-bit) random nonce
 */
export async function generateNonce(): Promise<Uint8Array> {
  return await getRandomBytes(NONCE_SIZE);
}

/**
 * Encrypt data using ChaCha20-Poly1305 authenticated encryption.
 * 
 * The output format is: [nonce (12 bytes)][encrypted data][auth tag (16 bytes)]
 * 
 * SECURITY: Nonces are generated internally using cryptographically secure random
 * number generation. Never reuse nonces with the same key - this would catastrophically
 * break security.
 * 
 * @param plaintext - The data to encrypt
 * @param key - The 256-bit (32-byte) encryption key
 * @returns Encrypted data with nonce prepended and auth tag appended
 * @throws Error if key size is invalid
 */
export async function encrypt(
  plaintext: Uint8Array,
  key: Uint8Array
): Promise<Uint8Array> {
  // Validate key size
  if (key.length !== KEY_SIZE) {
    throw new Error(`Invalid key size: expected ${KEY_SIZE} bytes, got ${key.length} bytes`);
  }

  // Always generate a fresh random nonce
  const nonce = await generateNonce();

  // Create cipher instance
  const cipher = chacha20poly1305(key, nonce);
  
  // Encrypt and authenticate
  const ciphertext = cipher.encrypt(plaintext);
  
  // Format: [nonce][ciphertext with tag]
  const result = new Uint8Array(NONCE_SIZE + ciphertext.length);
  result.set(nonce, 0);
  result.set(ciphertext, NONCE_SIZE);
  
  return result;
}

/**
 * Decrypt data using ChaCha20-Poly1305 authenticated encryption.
 * 
 * Expects input format: [nonce (12 bytes)][encrypted data][auth tag (16 bytes)]
 * 
 * @param ciphertext - The encrypted data with nonce prepended and auth tag appended
 * @param key - The 256-bit (32-byte) encryption key
 * @returns Decrypted plaintext data
 * @throws Error if key size is invalid, ciphertext is too short, or authentication fails
 */
export function decrypt(
  ciphertext: Uint8Array,
  key: Uint8Array
): Uint8Array {
  // Validate key size
  if (key.length !== KEY_SIZE) {
    throw new Error(`Invalid key size: expected ${KEY_SIZE} bytes, got ${key.length} bytes`);
  }

  // Validate minimum ciphertext size (nonce + tag)
  if (ciphertext.length < NONCE_SIZE + TAG_SIZE) {
    throw new Error(
      `Invalid ciphertext size: expected at least ${NONCE_SIZE + TAG_SIZE} bytes, got ${ciphertext.length} bytes`
    );
  }

  // Extract nonce from the beginning
  const nonce = ciphertext.slice(0, NONCE_SIZE);
  
  // Extract encrypted data with tag
  const encryptedData = ciphertext.slice(NONCE_SIZE);
  
  // Create cipher instance
  const cipher = chacha20poly1305(key, nonce);
  
  // Decrypt and verify authentication tag
  try {
    const plaintext = cipher.decrypt(encryptedData);
    return plaintext;
  } catch (error) {
    throw new Error('Decryption failed: authentication tag verification failed');
  }
}

/**
 * Padding length for tag normalization (64 bytes)
 * Hides tag length information from frequency analysis
 */
export const TAG_PADDING_LENGTH = 64;

/**
 * Encrypt a tag deterministically using HMAC-SHA256 for searchable encryption.
 * 
 * This enables server-side exact match without revealing plaintext tag values.
 * Tags are normalized to lowercase, padded to fixed length, and salted with vaultId
 * before encryption to provide enhanced security properties.
 * 
 * Security enhancements:
 * - Vault-scoped salting: Same tag in different vaults produces different encrypted values
 * - Length padding: All tags padded to 64 bytes to prevent length-based analysis
 * - Case normalization: Case-insensitive search enabled via lowercase normalization
 * - Constant-time validation: Prevents timing side-channel attacks by always performing
 *   cryptographic operations regardless of validation results
 * 
 * Trade-offs:
 * - Frequency analysis is still possible within a single vault
 * - Dictionary attacks possible if tag space is small
 * - No protection against known-plaintext attacks
 * 
 * @param tag - The tag string to encrypt
 * @param key - The encryption key (typically metadata encryption key)
 * @param vaultId - The vault ID for scoped salting (prevents cross-vault correlation)
 * @returns Deterministic encrypted tag (32 bytes)
 * @throws Error if key size is invalid or vaultId is empty
 * 
 * @example
 * const tag = 'vacation';
 * const key = metadataEncryptionKey; // 32-byte key
 * const vaultId = 'vault-123';
 * const encryptedTag = encryptTagForSearch(tag, key, vaultId);
 * // Store encryptedTag in database for searchable encryption
 */
export function encryptTagForSearch(tag: string, key: Uint8Array, vaultId: string): Uint8Array {
  // Collect validation errors without early return (timing attack mitigation)
  let validationError: Error | null = null;
  
  // Validate key size
  if (key.length !== KEY_SIZE) {
    validationError = new Error(`Invalid key size: expected ${KEY_SIZE} bytes, got ${key.length} bytes`);
  }

  // Validate vaultId
  if (!validationError && (!vaultId || vaultId.trim().length === 0)) {
    validationError = new Error('vaultId must be a non-empty string');
  }

  // Always perform expensive cryptographic operations regardless of validation
  // This prevents timing side-channels from revealing validation failures
  
  // Normalize tag to lowercase for case-insensitive search
  const normalizedTag = tag.toLowerCase().trim();
  
  // Pad tag to fixed length to hide length information
  // This prevents length-based frequency analysis
  const paddedTag = normalizedTag.padEnd(TAG_PADDING_LENGTH, '\0');
  
  // Add vault-scoped salt to prevent cross-vault tag correlation
  // Same tag in different vaults will produce different encrypted values
  const tagWithSalt = `${vaultId}:${paddedTag}`;
  
  // Convert to bytes
  const tagBytes = new TextEncoder().encode(tagWithSalt);
  
  // Use HMAC-SHA256 for deterministic encryption
  // This operation is performed even if validation failed to maintain constant timing
  const encryptedTag = hmac(sha256, key, tagBytes);
  
  // Throw validation error after cryptographic operations complete
  // This ensures all code paths take similar time regardless of input validity
  if (validationError) {
    throw validationError;
  }
  
  return encryptedTag;
}

/**
 * Utility function to convert a string to Uint8Array
 * 
 * @param text - The string to convert
 * @returns Uint8Array representation of the string
 */
export function stringToBytes(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

/**
 * Utility function to convert Uint8Array to string
 * 
 * @param bytes - The bytes to convert
 * @returns String representation of the bytes
 */
export function bytesToString(bytes: Uint8Array): string {
  return new TextDecoder().decode(bytes);
}

/**
 * Utility function to convert Uint8Array to base64 string
 * 
 * @param bytes - The bytes to convert
 * @returns Base64 string representation
 */
export function bytesToBase64(bytes: Uint8Array): string {
  const binString = Array.from(bytes, (byte) => String.fromCharCode(byte)).join('');
  return btoa(binString);
}

/**
 * Utility function to convert base64 string to Uint8Array
 * 
 * @param base64 - The base64 string to convert
 * @returns Uint8Array representation
 */
export function base64ToBytes(base64: string): Uint8Array {
  const binString = atob(base64);
  return Uint8Array.from(binString, (char) => char.charCodeAt(0));
}
