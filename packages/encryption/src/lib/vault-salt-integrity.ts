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

// ---------------------------------------------------------------------------
// Salt binding helpers
// ---------------------------------------------------------------------------

import { retrieveKeys, storeKeys, type KeyStorageConfig } from './key-storage';

/**
 * Error thrown by the salt-binding / salt-reset helpers.
 *
 * Codes:
 *  - NO_BUNDLE        – no stored key bundle for the given vaultId
 *  - TAMPERED         – reserved for future verify-and-throw callers; not
 *                       emitted by this module yet
 *  - STORAGE_FAILURE  – storeKeys threw while persisting the updated bundle
 */
export class SaltIntegrityError extends Error {
  constructor(
    message: string,
    public readonly code: 'NO_BUNDLE' | 'TAMPERED' | 'STORAGE_FAILURE'
  ) {
    super(message);
    this.name = 'SaltIntegrityError';
  }
}

/**
 * Arguments for both bindSaltHmac and resetSaltHmac.
 *
 * `config` is forwarded verbatim to storeKeys / retrieveKeys.  Pass
 * `{ ...DEFAULT_CONFIG, forceFallback: true }` in jsdom test environments
 * that lack IndexedDB / Web Crypto — this is Option A (explicit forwarding)
 * which keeps the helpers environment-agnostic without global side effects.
 */
export interface SaltBindingArgs {
  vaultId: string;
  saltHmacKey: Uint8Array;
  salt: Uint8Array;
  /** Storage configuration forwarded to retrieveKeys / storeKeys. */
  config?: KeyStorageConfig;
}

/**
 * Internal shared implementation for bindSaltHmac and resetSaltHmac.
 * NOT exported — callers use the named public functions below.
 */
async function persistSaltHmac(args: SaltBindingArgs): Promise<void> {
  const bundle = await retrieveKeys(args.vaultId, args.config);
  if (!bundle) {
    throw new SaltIntegrityError(
      `No stored key bundle for vault "${args.vaultId}"; unlock the vault first.`,
      'NO_BUNDLE'
    );
  }
  const mac = computeSaltHmac(args.saltHmacKey, args.salt);
  try {
    await storeKeys(args.vaultId, { ...bundle, saltHmac: mac }, args.config);
  } catch (err) {
    throw new SaltIntegrityError(
      `Failed to persist salt HMAC: ${err instanceof Error ? err.message : 'unknown error'}`,
      'STORAGE_FAILURE'
    );
  }
}

/**
 * First-time binding: compute HMAC(saltHmacKey, salt) and persist it on the
 * stored key bundle after a successful vault unlock.
 *
 * Throws SaltIntegrityError(NO_BUNDLE) when no bundle is found for vaultId.
 */
export async function bindSaltHmac(args: SaltBindingArgs): Promise<void> {
  await persistSaltHmac(args);
}

/**
 * Reset binding: overwrite any previously stored saltHmac with a freshly
 * computed one.  Call this after the user has re-derived keys by successfully
 * entering BOTH account and vault passwords (Argon2id success is the implicit
 * re-authentication — an attacker who lacks the vault password cannot produce
 * a valid saltHmacKey).
 *
 * Throws SaltIntegrityError(NO_BUNDLE) when no bundle is found for vaultId.
 */
export async function resetSaltHmac(args: SaltBindingArgs): Promise<void> {
  await persistSaltHmac(args);
}
