/**
 * Share Encryption Module
 *
 * Implements password-protected file sharing for Cortex's zero-knowledge
 * architecture. A share password is used to derive encryption and HMAC keys
 * via Argon2id + HKDF. The resulting keys protect the shared file's DEK
 * and authenticate share metadata.
 *
 * Key derivation chain:
 *   share_password + salt(16) -> Argon2id(64MB, 3 iter, 4 par) -> master(32)
 *   master -> HKDF-SHA256(salt: "cortex-salt-share-enc-v1",
 *                          info: "cortex-share-key-v1") -> encryptionKey(32)
 *   master -> HKDF-SHA256(salt: "cortex-salt-share-hmac-v1",
 *                          info: "cortex-share-hmac-v1") -> hmacKey(32)
 *
 * Blob binary format:
 *   [version(1)][salt(16)][wrappedDek(65)][hmac(32)] = 114 bytes -> ~152 chars base64url
 */

import { hkdf } from '@noble/hashes/hkdf.js';
import { sha256 } from '@noble/hashes/sha2.js';
import { hmac } from '@noble/hashes/hmac.js';
import { argon2id } from 'hash-wasm';

/**
 * Argon2id parameters for share key derivation (RFC 9106).
 * Matches vault key derivation: 64 MiB memory, 3 iterations, 4 parallelism, 32-byte output.
 *
 * Uses hash-wasm's WASM Argon2id (WASM inlined → browser-bundleable, no plugins/fs).
 */
const ARGON2_PARAMS = { parallelism: 4, iterations: 3, memorySize: 65536, hashLength: 32 } as const;

// --- HKDF salts and contexts for share key derivation ---

const HKDF_SHARE_SALTS = {
  ENCRYPTION: new TextEncoder().encode('cortex-salt-share-enc-v1'),
  HMAC: new TextEncoder().encode('cortex-salt-share-hmac-v1'),
};

const HKDF_SHARE_CONTEXTS = {
  ENCRYPTION: 'cortex-share-key-v1',
  HMAC: 'cortex-share-hmac-v1',
};

// --- Blob format constants ---

const BLOB_VERSION_SIZE = 1;
const BLOB_SALT_SIZE = 16;
const BLOB_WRAPPED_DEK_SIZE = 65;
const BLOB_HMAC_SIZE = 32;
const BLOB_TOTAL_SIZE = BLOB_VERSION_SIZE + BLOB_SALT_SIZE + BLOB_WRAPPED_DEK_SIZE + BLOB_HMAC_SIZE; // 114

// --- Interface for derived share keys ---

export interface ShareKeys {
  encryptionKey: Uint8Array;
  hmacKey: Uint8Array;
}

// --- Interface for decoded share blob ---

export interface ShareBlob {
  version: number;
  salt: Uint8Array;
  wrappedDek: Uint8Array;
  hmac: Uint8Array;
}

// --- base64url helpers (no padding, URL-safe) ---

const BASE64URL_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';

function bytesToBase64url(bytes: Uint8Array): string {
  let result = '';
  const len = bytes.length;

  // Process full 3-byte groups
  let i = 0;
  for (; i + 2 < len; i += 3) {
    const triplet = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    result += BASE64URL_CHARS[(triplet >> 18) & 0x3f];
    result += BASE64URL_CHARS[(triplet >> 12) & 0x3f];
    result += BASE64URL_CHARS[(triplet >> 6) & 0x3f];
    result += BASE64URL_CHARS[triplet & 0x3f];
  }

  // Handle remaining 1 or 2 bytes (no padding characters)
  const remaining = len - i;
  if (remaining === 1) {
    const a = bytes[i];
    result += BASE64URL_CHARS[(a >> 2) & 0x3f];
    result += BASE64URL_CHARS[(a << 4) & 0x3f];
  } else if (remaining === 2) {
    const a = bytes[i];
    const b = bytes[i + 1];
    result += BASE64URL_CHARS[(a >> 2) & 0x3f];
    result += BASE64URL_CHARS[((a << 4) | (b >> 4)) & 0x3f];
    result += BASE64URL_CHARS[(b << 2) & 0x3f];
  }

  return result;
}

function base64urlToBytes(str: string): Uint8Array {
  // Build reverse lookup
  const lookup = new Uint8Array(128);
  lookup.fill(0xff);
  for (let i = 0; i < BASE64URL_CHARS.length; i++) {
    lookup[BASE64URL_CHARS.charCodeAt(i)] = i;
  }

  const len = str.length;
  // Calculate byte length: each group of 4 chars = 3 bytes,
  // leftover 2 chars = 1 byte, leftover 3 chars = 2 bytes
  const remainder = len % 4;
  const fullGroups = Math.floor(len / 4);
  const byteLen = fullGroups * 3 + (remainder === 2 ? 1 : remainder === 3 ? 2 : 0);
  const bytes = new Uint8Array(byteLen);

  let byteIdx = 0;
  let strIdx = 0;

  for (let g = 0; g < fullGroups; g++) {
    const a = lookup[str.charCodeAt(strIdx++)];
    const b = lookup[str.charCodeAt(strIdx++)];
    const c = lookup[str.charCodeAt(strIdx++)];
    const d = lookup[str.charCodeAt(strIdx++)];

    if (a === 0xff || b === 0xff || c === 0xff || d === 0xff) {
      throw new Error('Invalid base64url character');
    }

    const triplet = (a << 18) | (b << 12) | (c << 6) | d;
    bytes[byteIdx++] = (triplet >> 16) & 0xff;
    bytes[byteIdx++] = (triplet >> 8) & 0xff;
    bytes[byteIdx++] = triplet & 0xff;
  }

  if (remainder === 2) {
    const a = lookup[str.charCodeAt(strIdx++)];
    const b = lookup[str.charCodeAt(strIdx++)];
    if (a === 0xff || b === 0xff) {
      throw new Error('Invalid base64url character');
    }
    bytes[byteIdx++] = ((a << 2) | (b >> 4)) & 0xff;
  } else if (remainder === 3) {
    const a = lookup[str.charCodeAt(strIdx++)];
    const b = lookup[str.charCodeAt(strIdx++)];
    const c = lookup[str.charCodeAt(strIdx++)];
    if (a === 0xff || b === 0xff || c === 0xff) {
      throw new Error('Invalid base64url character');
    }
    bytes[byteIdx++] = ((a << 2) | (b >> 4)) & 0xff;
    bytes[byteIdx++] = ((b << 4) | (c >> 2)) & 0xff;
  }

  return bytes;
}

// --- Public API ---

/**
 * Derive share encryption and HMAC keys from a password and salt.
 *
 * Uses Argon2id (64MB, 3 iterations, 4 parallelism) to derive a 32-byte
 * master key, then HKDF-SHA256 to derive separate encryption and HMAC keys.
 * The master key is zeroed after child keys are derived.
 *
 * @param password - The share password
 * @param salt - Random salt (at least 16 bytes)
 * @returns Promise<ShareKeys> containing encryptionKey and hmacKey (32 bytes each)
 */
export async function deriveShareKeys(
  password: string,
  salt: Uint8Array
): Promise<ShareKeys> {
  if (!password || password.length === 0) {
    throw new Error('Password cannot be empty');
  }

  if (!salt || salt.length < 16) {
    throw new Error('Salt must be at least 16 bytes');
  }

  const keyLength = 32;

  try {
    // Argon2id (RFC 9106) via hash-wasm — WASM inlined, browser-bundleable.
    const shareMasterKey = await argon2id({ password, salt, ...ARGON2_PARAMS, outputType: 'binary' });

    try {
      const encryptionKey = hkdf(
        sha256,
        shareMasterKey,
        HKDF_SHARE_SALTS.ENCRYPTION,
        new TextEncoder().encode(HKDF_SHARE_CONTEXTS.ENCRYPTION),
        keyLength
      );

      const hmacKey = hkdf(
        sha256,
        shareMasterKey,
        HKDF_SHARE_SALTS.HMAC,
        new TextEncoder().encode(HKDF_SHARE_CONTEXTS.HMAC),
        keyLength
      );

      return { encryptionKey, hmacKey };
    } finally {
      // Zero the master key after deriving child keys
      shareMasterKey.fill(0);
    }
  } catch (error) {
    if (error instanceof Error && (
      error.message === 'Password cannot be empty' ||
      error.message === 'Salt must be at least 16 bytes'
    )) {
      throw error;
    }
    throw new Error(
      `Failed to derive share keys: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}

/**
 * Compute a 32-byte HMAC-SHA256 over a share ID and optional expiry timestamp.
 *
 * The message is constructed as: shareId (or shareId + ":" + expiresAt if expiry provided).
 *
 * @param hmacKey - The 32-byte HMAC key (from deriveShareKeys)
 * @param shareId - The share identifier
 * @param expiresAt - Optional expiry timestamp (Unix seconds)
 * @returns 32-byte HMAC
 */
export function computeShareHmac(
  hmacKey: Uint8Array,
  shareId: string,
  expiresAt?: number
): Uint8Array {
  if (!hmacKey || hmacKey.length !== 32) {
    throw new Error('HMAC key must be 32 bytes');
  }

  if (!shareId || shareId.length === 0) {
    throw new Error('shareId cannot be empty');
  }

  let message = shareId;
  if (expiresAt !== undefined && expiresAt !== null) {
    message = `${shareId}:${expiresAt}`;
  }

  const messageBytes = new TextEncoder().encode(message);
  return hmac(sha256, hmacKey, messageBytes);
}

/**
 * Verify an HMAC using constant-time comparison (XOR loop).
 *
 * @param hmacKey - The 32-byte HMAC key
 * @param shareId - The share identifier
 * @param expiresAt - Optional expiry timestamp (Unix seconds)
 * @param expectedHmac - The expected 32-byte HMAC to verify against
 * @returns true if the HMAC matches, false otherwise
 */
export function verifyShareHmac(
  hmacKey: Uint8Array,
  shareId: string,
  expiresAt: number | undefined,
  expectedHmac: Uint8Array
): boolean {
  // Length check before computing (no timing leak since length is not secret)
  if (!expectedHmac || expectedHmac.length !== 32) {
    return false;
  }

  const computedHmac = computeShareHmac(hmacKey, shareId, expiresAt);

  // Constant-time comparison with XOR loop
  if (computedHmac.length !== expectedHmac.length) {
    return false;
  }

  let diff = 0;
  for (let i = 0; i < computedHmac.length; i++) {
    diff |= computedHmac[i] ^ expectedHmac[i];
  }

  return diff === 0;
}

/**
 * Encode share blob components into a base64url string (no padding).
 *
 * Binary format: [version(1)][salt(16)][wrappedDek(65)][hmac(32)] = 114 bytes
 *
 * @param version - Version byte (e.g. 0x01)
 * @param salt - The 16-byte salt used for key derivation
 * @param wrappedDek - The 65-byte wrapped DEK
 * @param hmacValue - The 32-byte HMAC
 * @returns base64url encoded string (~152 chars)
 */
export function encodeShareBlob(
  version: number,
  salt: Uint8Array,
  wrappedDek: Uint8Array,
  hmacValue: Uint8Array
): string {
  if (salt.length !== BLOB_SALT_SIZE) {
    throw new Error(`Salt must be ${BLOB_SALT_SIZE} bytes`);
  }
  if (wrappedDek.length !== BLOB_WRAPPED_DEK_SIZE) {
    throw new Error(`Wrapped DEK must be ${BLOB_WRAPPED_DEK_SIZE} bytes`);
  }
  if (hmacValue.length !== BLOB_HMAC_SIZE) {
    throw new Error(`HMAC must be ${BLOB_HMAC_SIZE} bytes`);
  }

  const buffer = new Uint8Array(BLOB_TOTAL_SIZE);
  let offset = 0;

  buffer[offset] = version & 0xff;
  offset += BLOB_VERSION_SIZE;

  buffer.set(salt, offset);
  offset += BLOB_SALT_SIZE;

  buffer.set(wrappedDek, offset);
  offset += BLOB_WRAPPED_DEK_SIZE;

  buffer.set(hmacValue, offset);

  return bytesToBase64url(buffer);
}

/**
 * Decode a base64url share blob string back to its components.
 *
 * @param blob - The base64url encoded share blob string
 * @returns ShareBlob with version, salt, wrappedDek, and hmac
 */
export function decodeShareBlob(blob: string): ShareBlob {
  let bytes: Uint8Array;
  try {
    bytes = base64urlToBytes(blob);
  } catch {
    throw new Error('Invalid share blob: failed to decode base64url');
  }

  if (bytes.length !== BLOB_TOTAL_SIZE) {
    throw new Error(
      `Invalid share blob: expected ${BLOB_TOTAL_SIZE} bytes, got ${bytes.length}`
    );
  }

  let offset = 0;

  const version = bytes[offset];
  offset += BLOB_VERSION_SIZE;

  const salt = bytes.slice(offset, offset + BLOB_SALT_SIZE);
  offset += BLOB_SALT_SIZE;

  const wrappedDek = bytes.slice(offset, offset + BLOB_WRAPPED_DEK_SIZE);
  offset += BLOB_WRAPPED_DEK_SIZE;

  const hmacBytes = bytes.slice(offset, offset + BLOB_HMAC_SIZE);

  return { version, salt, wrappedDek, hmac: hmacBytes };
}
