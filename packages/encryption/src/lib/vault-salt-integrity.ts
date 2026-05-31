/**
 * Vault Salt Integrity Module
 *
 * Detects tampering with the server-stored vault salt by binding the salt
 * to the vault master key via an HMAC computed and verified locally.
 *
 * Spec: .kiro/specs/cortex/tasks.md task 10.2, requirements 22.6-22.12.
 */

import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';

export const SALT_HMAC_KEY_BYTES = 32;
export const VAULT_SALT_BYTES = 16;
export const SALT_HMAC_BYTES = 32;

export function computeSaltHmac(saltHmacKey: Uint8Array, salt: Uint8Array): Uint8Array {
  if (saltHmacKey.length !== SALT_HMAC_KEY_BYTES) {
    throw new Error(`saltHmacKey must be 32 bytes, got ${saltHmacKey.length}`);
  }
  if (salt.length !== VAULT_SALT_BYTES) {
    throw new Error(`salt must be 16 bytes, got ${salt.length}`);
  }
  return hmac(sha256, saltHmacKey, salt);
}

/**
 * Constant-time byte-array equality.
 *
 * Returns false immediately on length mismatch (length is not a secret).
 * Otherwise XOR-accumulates over every byte so the comparison cost is
 * independent of where the first differing byte appears.
 */
function constantTimeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

export function verifySaltHmac(
  saltHmacKey: Uint8Array,
  salt: Uint8Array,
  expectedMac: Uint8Array
): boolean {
  if (expectedMac.length !== SALT_HMAC_BYTES) return false;
  const actualMac = computeSaltHmac(saltHmacKey, salt);
  return constantTimeEqual(actualMac, expectedMac);
}
