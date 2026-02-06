/**
 * Envelope Encryption for Media Files
 *
 * Each media file gets a unique Data Encryption Key (DEK). The DEK encrypts
 * the file content, then the DEK itself is wrapped (encrypted) with the vault's
 * Key Encryption Key (KEK). Key rotation only requires re-wrapping DEKs —
 * not re-encrypting every file.
 *
 * Binary format for wrapped DEK (65 bytes without HMAC, 97 bytes with):
 *   [version(1)][timestamp(4)][nonce(12)][encryptedDEK(32)][authTag(16)]
 *   Optional: [HMAC-SHA256(DEK, fileId)(32)]
 *
 * Requirements: 28.1–28.5, 29.2, 29.3
 */

import { chacha20poly1305 } from '@noble/ciphers/chacha';
import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';

const WRAPPED_DEK_SIZE = 65;
const WRAPPED_DEK_WITH_HMAC_SIZE = 97;
const VERSION = 0x01;
const DEK_SIZE = 32;
const NONCE_SIZE = 12;
const TIMESTAMP_SIZE = 4;
const AUTH_TAG_SIZE = 16;

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

// --- Error types ---

export type DekUnwrapErrorCode =
  | 'CORRUPTED_DEK'
  | 'WRONG_KEK_VERSION'
  | 'AUTHENTICATION_FAILED';

export class DekUnwrapError extends Error {
  constructor(
    public readonly code: DekUnwrapErrorCode,
    message: string
  ) {
    super(message);
    this.name = 'DekUnwrapError';
  }
}

// --- Core functions ---

/**
 * Generate a random 32-byte Data Encryption Key via CSPRNG.
 */
export async function generateDek(): Promise<Uint8Array> {
  return await getRandomBytes(DEK_SIZE);
}

/**
 * Wrap (encrypt) a DEK with a KEK using ChaCha20-Poly1305.
 *
 * Returns a 65-byte buffer (no fileId) or 97-byte buffer (with fileId).
 *
 * **Key commitment note:** ChaCha20-Poly1305 does not provide key commitment —
 * an attacker could theoretically find two DEKs that both decrypt to valid
 * plaintexts. Risk is low in Cortex because an attacker must replace both the
 * ciphertext AND the wrapped DEK. HMAC binding (when `fileId` provided) adds
 * defense-in-depth against key substitution.
 *
 * **Caller responsibility:** The caller must zero the DEK after use.
 * This function does not zero the DEK because the caller may need it
 * for further operations (e.g., encrypting file content).
 *
 * @param dek - The 32-byte Data Encryption Key to wrap
 * @param kek - The 32-byte Key Encryption Key
 * @param fileId - Optional file ID for HMAC binding
 * @returns Wrapped DEK in binary format
 */
export async function wrapDek(
  dek: Uint8Array,
  kek: Uint8Array,
  fileId?: string
): Promise<Uint8Array> {
  if (dek.length !== DEK_SIZE) {
    throw new Error(`Invalid DEK size: expected ${DEK_SIZE} bytes, got ${dek.length} bytes`);
  }
  if (kek.length !== DEK_SIZE) {
    throw new Error(`Invalid KEK size: expected ${DEK_SIZE} bytes, got ${kek.length} bytes`);
  }

  const nonce = await getRandomBytes(NONCE_SIZE);
  const timestamp = Math.floor(Date.now() / 1000);

  const cipher = chacha20poly1305(kek, nonce);
  const encrypted = cipher.encrypt(dek);
  // encrypted = encryptedDEK(32) + authTag(16) = 48 bytes

  const hasHmac = fileId !== undefined && fileId !== null;
  const totalSize = hasHmac ? WRAPPED_DEK_WITH_HMAC_SIZE : WRAPPED_DEK_SIZE;
  const result = new Uint8Array(totalSize);

  let offset = 0;

  // Version byte
  result[offset] = VERSION;
  offset += 1;

  // Timestamp (uint32_be)
  result[offset] = (timestamp >>> 24) & 0xff;
  result[offset + 1] = (timestamp >>> 16) & 0xff;
  result[offset + 2] = (timestamp >>> 8) & 0xff;
  result[offset + 3] = timestamp & 0xff;
  offset += TIMESTAMP_SIZE;

  // Nonce
  result.set(nonce, offset);
  offset += NONCE_SIZE;

  // Encrypted DEK + auth tag
  result.set(encrypted, offset);
  offset += encrypted.length; // 32 + 16 = 48

  // HMAC binding
  if (hasHmac) {
    const fileIdBytes = new TextEncoder().encode(fileId);
    const hmacValue = hmac(sha256, dek, fileIdBytes);
    result.set(hmacValue, offset);
  }

  return result;
}

/**
 * Unwrap (decrypt) a wrapped DEK using a KEK.
 *
 * Validation order:
 * 1. Structural validation (length, version) — before any crypto
 * 2. ChaCha20-Poly1305 decryption — auth tag failure
 * 3. HMAC verification (if binding present) — requires fileId
 *
 * @param wrappedDek - The wrapped DEK in binary format (65 or 97 bytes)
 * @param kek - The 32-byte Key Encryption Key
 * @param fileId - Optional file ID for HMAC verification
 * @returns The unwrapped 32-byte DEK
 * @throws DekUnwrapError on failure
 */
export function unwrapDek(
  wrappedDek: Uint8Array,
  kek: Uint8Array,
  fileId?: string
): Uint8Array {
  // 0. Key size validation
  if (kek.length !== DEK_SIZE) {
    throw new Error(`Invalid KEK size: expected ${DEK_SIZE} bytes, got ${kek.length} bytes`);
  }

  // 1. Structural validation
  if (wrappedDek.length !== WRAPPED_DEK_SIZE && wrappedDek.length !== WRAPPED_DEK_WITH_HMAC_SIZE) {
    console.warn(`[envelope-encryption] CORRUPTED_DEK: invalid length ${wrappedDek.length} at ${new Date().toISOString()}`);
    throw new DekUnwrapError('CORRUPTED_DEK', `Invalid wrapped DEK length: expected ${WRAPPED_DEK_SIZE} or ${WRAPPED_DEK_WITH_HMAC_SIZE} bytes, got ${wrappedDek.length}`);
  }

  if (wrappedDek[0] !== VERSION) {
    console.warn(`[envelope-encryption] WRONG_KEK_VERSION: version ${wrappedDek[0]} at ${new Date().toISOString()}`);
    throw new DekUnwrapError('WRONG_KEK_VERSION', `Unsupported wrapped DEK version: ${wrappedDek[0]}`);
  }

  // 2. ChaCha20-Poly1305 decryption
  let offset = 1 + TIMESTAMP_SIZE; // skip version + timestamp
  const nonce = wrappedDek.slice(offset, offset + NONCE_SIZE);
  offset += NONCE_SIZE;
  const encryptedWithTag = wrappedDek.slice(offset, offset + DEK_SIZE + AUTH_TAG_SIZE);

  let dek: Uint8Array;
  try {
    const cipher = chacha20poly1305(kek, nonce);
    dek = cipher.decrypt(encryptedWithTag);
  } catch {
    console.warn(`[envelope-encryption] AUTHENTICATION_FAILED at ${new Date().toISOString()}`);
    throw new DekUnwrapError('AUTHENTICATION_FAILED', 'ChaCha20-Poly1305 authentication failed');
  }

  // 3. HMAC verification (if binding present)
  const hasHmac = wrappedDek.length === WRAPPED_DEK_WITH_HMAC_SIZE;
  if (hasHmac) {
    if (fileId === undefined || fileId === null) {
      dek.fill(0);
      console.warn(`[envelope-encryption] CORRUPTED_DEK: HMAC binding present but no fileId at ${new Date().toISOString()}`);
      throw new DekUnwrapError('CORRUPTED_DEK', 'Wrapped DEK has HMAC binding but no fileId was provided');
    }

    const storedHmac = wrappedDek.slice(WRAPPED_DEK_SIZE);
    const fileIdBytes = new TextEncoder().encode(fileId);
    // HMAC argument order: key=DEK (secret), message=fileId (identity being bound)
    const computedHmac = hmac(sha256, dek, fileIdBytes);

    // Constant-time comparison with defensive length check
    if (storedHmac.length !== computedHmac.length) {
      dek.fill(0);
      console.warn(`[envelope-encryption] CORRUPTED_DEK: HMAC length mismatch at ${new Date().toISOString()}`);
      throw new DekUnwrapError('CORRUPTED_DEK', 'HMAC binding verification failed');
    }
    let diff = 0;
    for (let i = 0; i < computedHmac.length; i++) {
      diff |= computedHmac[i] ^ storedHmac[i];
    }

    if (diff !== 0) {
      dek.fill(0);
      console.warn(`[envelope-encryption] CORRUPTED_DEK: HMAC mismatch at ${new Date().toISOString()}`);
      throw new DekUnwrapError('CORRUPTED_DEK', 'HMAC binding verification failed');
    }
  }

  return dek;
}

// --- File-level convenience functions ---

/**
 * Encrypt file content using envelope encryption.
 *
 * Generates a unique DEK, encrypts content, wraps the DEK with KEK,
 * then zeros the DEK buffer.
 *
 * @param content - The file content to encrypt
 * @param kek - The 32-byte Key Encryption Key
 * @param fileId - Optional file ID for HMAC binding
 * @returns The encrypted content and wrapped DEK
 */
export async function encryptFileWithDek(
  content: Uint8Array,
  kek: Uint8Array,
  fileId?: string
): Promise<{ encryptedContent: Uint8Array; wrappedDek: Uint8Array }> {
  const dek = await generateDek();

  try {
    // Encrypt content with DEK using ChaCha20-Poly1305
    const nonce = await getRandomBytes(NONCE_SIZE);
    const cipher = chacha20poly1305(dek, nonce);
    const ciphertext = cipher.encrypt(content);

    // Format: [nonce][ciphertext with tag]
    const encryptedContent = new Uint8Array(NONCE_SIZE + ciphertext.length);
    encryptedContent.set(nonce, 0);
    encryptedContent.set(ciphertext, NONCE_SIZE);

    // Wrap the DEK with KEK
    const wrappedDek = await wrapDek(dek, kek, fileId);

    return { encryptedContent, wrappedDek };
  } finally {
    dek.fill(0);
  }
}

/**
 * Decrypt file content using envelope encryption.
 *
 * Unwraps the DEK, decrypts content, then zeros the DEK buffer.
 *
 * @param encryptedContent - The encrypted file content
 * @param wrappedDek - The wrapped DEK
 * @param kek - The 32-byte Key Encryption Key
 * @param fileId - Optional file ID for HMAC verification
 * @returns The decrypted file content
 * @throws DekUnwrapError if DEK unwrapping fails
 */
export function decryptFileWithDek(
  encryptedContent: Uint8Array,
  wrappedDek: Uint8Array,
  kek: Uint8Array,
  fileId?: string
): Uint8Array {
  // Validate minimum encrypted content length: nonce + auth tag
  if (encryptedContent.length < NONCE_SIZE + AUTH_TAG_SIZE) {
    throw new Error(
      `Invalid encrypted content size: expected at least ${NONCE_SIZE + AUTH_TAG_SIZE} bytes, got ${encryptedContent.length} bytes`
    );
  }

  const dek = unwrapDek(wrappedDek, kek, fileId);

  try {
    // Extract nonce and ciphertext (format: [nonce(12)][ciphertext + authTag])
    const nonce = encryptedContent.slice(0, NONCE_SIZE);
    const ciphertext = encryptedContent.slice(NONCE_SIZE);

    const cipher = chacha20poly1305(dek, nonce);
    return cipher.decrypt(ciphertext);
  } finally {
    dek.fill(0);
  }
}
