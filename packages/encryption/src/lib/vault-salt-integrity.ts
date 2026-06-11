/**
 * Vault Salt Integrity Module
 *
 * Detects tampering with the server-stored vault salt by binding the salt
 * to the vault master key via an HMAC computed and verified locally.
 *
 * The HMAC is stored in a **separate, standalone, non-expiring** record
 * (IndexedDB or localStorage) — NOT inside the encrypted key bundle.
 * This means the integrity baseline survives bundle expiry (default 24 h)
 * and persists for the lifetime of the device or until explicitly cleared.
 *
 * Spec: .kiro/specs/cortex/tasks.md task 10.2, requirements 22.6-22.12.
 */

import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';
import {
  storeSaltHmacRecord,
  retrieveSaltHmacRecord,
  type KeyStorageConfig,
} from './key-storage';

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

/**
 * Verifies a salt HMAC without throwing for any input lengths.
 *
 * Returns `false` (never throws) when:
 * - `saltHmacKey` is not exactly 32 bytes
 * - `salt` is not exactly 16 bytes
 * - `expectedMac` is not exactly 32 bytes
 * - the computed HMAC does not match `expectedMac`
 */
export function verifySaltHmac(
  saltHmacKey: Uint8Array,
  salt: Uint8Array,
  expectedMac: Uint8Array
): boolean {
  if (saltHmacKey.length !== SALT_HMAC_KEY_BYTES) return false;
  if (salt.length !== VAULT_SALT_BYTES) return false;
  if (expectedMac.length !== SALT_HMAC_BYTES) return false;
  const actualMac = computeSaltHmac(saltHmacKey, salt);
  return constantTimeEqual(actualMac, expectedMac);
}

// ---------------------------------------------------------------------------
// Salt binding helpers
// ---------------------------------------------------------------------------

/**
 * Error thrown by the salt-binding / salt-reset helpers.
 *
 * Codes:
 *  - NO_PRIOR_BINDING – no salt-HMAC record exists for the given vaultId on
 *                       this device (regardless of whether a key bundle exists)
 *  - ALREADY_BOUND    – bindSaltHmac was called but a record already exists;
 *                       use resetSaltHmac after re-authentication to overwrite
 *  - TAMPERED         – reserved for future verify-and-throw callers; not
 *                       emitted by this module yet
 *  - STORAGE_FAILURE  – the underlying store threw while persisting the record
 */
export class SaltIntegrityError extends Error {
  constructor(
    message: string,
    public readonly code: 'NO_PRIOR_BINDING' | 'ALREADY_BOUND' | 'TAMPERED' | 'STORAGE_FAILURE'
  ) {
    super(message);
    this.name = 'SaltIntegrityError';
  }
}

/**
 * Arguments for both bindSaltHmac and resetSaltHmac.
 *
 * `config` is forwarded verbatim to the underlying salt-HMAC record store.
 * Pass `{ ...DEFAULT_CONFIG, forceFallback: true }` in jsdom test environments
 * that lack IndexedDB / Web Crypto — this keeps the helpers
 * environment-agnostic without global side effects.
 */
export interface SaltBindingArgs {
  vaultId: string;
  saltHmacKey: Uint8Array;
  salt: Uint8Array;
  /** Storage configuration forwarded to the salt-HMAC record store. */
  config?: KeyStorageConfig;
}

/**
 * Internal shared implementation: compute and persist the salt HMAC in the
 * standalone salt-HMAC record store. Does NOT touch the key bundle.
 *
 * Any storage error is wrapped in SaltIntegrityError('STORAGE_FAILURE').
 */
async function persistSaltHmac(args: SaltBindingArgs): Promise<void> {
  const mac = computeSaltHmac(args.saltHmacKey, args.salt);
  try {
    await storeSaltHmacRecord(args.vaultId, mac, args.config);
  } catch (err) {
    throw new SaltIntegrityError(
      `Failed to persist salt HMAC: ${err instanceof Error ? err.message : 'unknown error'}`,
      'STORAGE_FAILURE'
    );
  }
}

/**
 * First-time binding: compute HMAC(saltHmacKey, salt) and write it to the
 * standalone salt-HMAC record store.
 *
 * Throws `SaltIntegrityError('ALREADY_BOUND')` if a record already exists for
 * this vaultId on this device. Callers who legitimately need to overwrite an
 * existing binding (e.g. after account recovery) must call `resetSaltHmac`
 * instead.
 */
export async function bindSaltHmac(args: SaltBindingArgs): Promise<void> {
  const existing = await retrieveSaltHmacRecord(args.vaultId, args.config);
  if (existing !== null) {
    throw new SaltIntegrityError(
      `Salt HMAC already bound for vault "${args.vaultId}". ` +
        'Use resetSaltHmac to overwrite after re-authentication.',
      'ALREADY_BOUND'
    );
  }
  await persistSaltHmac(args);
}

/**
 * Reset binding: overwrite any previously stored salt HMAC with a freshly
 * computed one.  Call this after the user has re-derived keys by successfully
 * entering BOTH account and vault passwords (Argon2id success is the implicit
 * re-authentication — an attacker who lacks the vault password cannot produce
 * a valid saltHmacKey).
 *
 * Unlike `bindSaltHmac`, this function succeeds even when no prior record exists.
 */
export async function resetSaltHmac(args: SaltBindingArgs): Promise<void> {
  await persistSaltHmac(args);
}

/**
 * Returns the previously-bound saltHmac for the vault, or `null` if none has
 * been bound on this device.
 *
 * This is a thin public wrapper over `retrieveSaltHmacRecord` so that external
 * callers do not need to import directly from `./key-storage`.
 */
export async function getStoredSaltHmac(
  vaultId: string,
  config?: KeyStorageConfig
): Promise<Uint8Array | null> {
  return retrieveSaltHmacRecord(vaultId, config);
}
