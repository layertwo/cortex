/**
 * Key Management Module
 * 
 * Implements vault master key derivation using Argon2id and HKDF-based
 * key derivation for multiple encryption keys.
 */

import { hkdf } from '@noble/hashes/hkdf';
import { sha256 } from '@noble/hashes/sha2';
import { mnemonicToEntropy, entropyToMnemonic, validateMnemonic } from '@scure/bip39';
import { wordlist } from '@scure/bip39/wordlists/english.js';

// Dynamic import for argon2id to handle both browser and Node.js environments
let loadArgon2idWasm: (() => Promise<(params: {
  password: Uint8Array;
  salt: Uint8Array;
  parallelism: number;
  passes: number;
  memorySize: number;
  tagLength: number;
}) => Uint8Array>) | null = null;

// Initialize the loader based on environment
async function initArgon2idLoader() {
  if (loadArgon2idWasm) return loadArgon2idWasm;
  
  // Check if we're in Node.js environment
  if (typeof process !== 'undefined' && process.versions && process.versions.node) {
    // Node.js environment - use fs to load WASM files
    try {
      const fs = await import('fs');
      const path = await import('path');
      const { fileURLToPath } = await import('url');
      const setupWasm = (await import('argon2id/lib/setup.js')).default;
      
      // Dynamically resolve argon2id package location using import.meta.resolve()
      // This works in all monorepo configurations (npm workspaces, yarn PnP, pnpm)
      // by letting Node.js resolve the package path instead of assuming a structure
      let argon2idPath: string;
      
      try {
        // Try import.meta.resolve() first (Node.js 20.6+)
        const argon2idPackageUrl = import.meta.resolve('argon2id');
        const argon2idPackagePath = fileURLToPath(argon2idPackageUrl);
        argon2idPath = path.dirname(argon2idPackagePath);
      } catch (resolveError) {
        // Fallback: Use require.resolve if import.meta.resolve is not available
        // This handles older Node.js versions and different module systems
        try {
          const argon2idMainPath = require.resolve('argon2id');
          argon2idPath = path.dirname(argon2idMainPath);
        } catch (requireError) {
          throw new Error(
            'Failed to resolve argon2id package location. ' +
            'Ensure argon2id is installed and accessible. ' +
            `import.meta.resolve error: ${resolveError instanceof Error ? resolveError.message : 'unknown'}; ` +
            `require.resolve error: ${requireError instanceof Error ? requireError.message : 'unknown'}`
          );
        }
      }
      
      const simdPath = path.join(argon2idPath, 'dist/simd.wasm');
      const nonSimdPath = path.join(argon2idPath, 'dist/no-simd.wasm');
      
      loadArgon2idWasm = () => setupWasm(
        (importObject: WebAssembly.Imports) => WebAssembly.instantiate(fs.readFileSync(simdPath), importObject),
        (importObject: WebAssembly.Imports) => WebAssembly.instantiate(fs.readFileSync(nonSimdPath), importObject)
      );
    } catch (error) {
      throw new Error(`Failed to initialize Argon2id for Node.js: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  } else {
    // Browser environment - use default loader
    const defaultLoader = (await import('argon2id')).default;
    loadArgon2idWasm = defaultLoader;
  }
  
  return loadArgon2idWasm;
}

/**
 * Argon2id parameters for vault master key derivation
 * - Memory: 64MB (65536 KB)
 * - Iterations: 3
 * - Parallelism: 4
 * - Hash length: 32 bytes (256 bits)
 */
const ARGON2_PARAMS = {
  memorySize: 65536, // 64MB in KB
  passes: 3,
  parallelism: 4,
  tagLength: 32, // 256 bits output
};

/**
 * Cached Argon2id WASM instance
 * Initialized on first use to avoid repeated WASM loading
 */
let argon2idInstance: ((params: {
  password: Uint8Array;
  salt: Uint8Array;
  parallelism: number;
  passes: number;
  memorySize: number;
  tagLength: number;
}) => Uint8Array) | null = null;

/**
 * Loads and caches the Argon2id WASM instance
 * @returns Promise<Argon2id function>
 */
async function getArgon2id() {
  if (!argon2idInstance) {
    const loader = await initArgon2idLoader();
    argon2idInstance = await loader();
  }
  return argon2idInstance;
}

/**
 * HKDF fixed salts for defense-in-depth domain separation
 * 
 * These salts provide an additional layer of cryptographic separation beyond
 * the context strings (info parameter). While RFC 5869 allows optional salts,
 * using fixed versioned salts provides:
 * 
 * 1. Defense-in-depth: Two independent layers of domain separation
 * 2. Future-proofing: Version suffix allows salt rotation if needed
 * 3. Best practice: Conservative cryptographic approach
 * 
 * Design decision: Fixed salts (not random) because:
 * - Deterministic key derivation is required (same master key → same derived keys)
 * - Salts don't need to be secret, just unique per key type
 * - Master key is already high-entropy (Argon2id with 64MB memory, 3 iterations)
 */
const HKDF_SALTS = {
  // ponytail: KEK salt is versioned (-v1); key rotation (task 6.13) bumps to -v2, -v3…
  KEY_ENCRYPTION: new TextEncoder().encode('cortex-salt-kek-v1'),
  METADATA_ENCRYPTION: new TextEncoder().encode('cortex-salt-metadata-v1'),
  SHARE_KEY_DERIVATION: new TextEncoder().encode('cortex-salt-share-v1'),
  NOTES_ENCRYPTION: new TextEncoder().encode('cortex-salt-notes-v1'),
  TASKS_ENCRYPTION: new TextEncoder().encode('cortex-salt-tasks-v1'),
  EVENTS_ENCRYPTION: new TextEncoder().encode('cortex-salt-events-v1'),
  NOTIFICATION_ENCRYPTION: new TextEncoder().encode('cortex-salt-notification-v1'),
  DATE_BUCKET_ENCRYPTION: new TextEncoder().encode('cortex-salt-date-bucket-v1'),
  SALT_HMAC: new TextEncoder().encode('cortex-salt-salt-hmac-v1'),
};

/**
 * HKDF context strings for deriving different encryption keys
 * 
 * These provide the primary domain separation (via the info parameter).
 * Combined with HKDF_SALTS, this provides two independent layers of separation.
 */
const HKDF_CONTEXTS = {
  // Key Encryption Key — wraps per-file DEKs (envelope encryption). Context is
  // versioned for key rotation: v1 today, v2/v3… after a rotation (task 6.13).
  KEY_ENCRYPTION: 'cortex-kek-v1',
  METADATA_ENCRYPTION: 'cortex-metadata-encryption-v1',
  SHARE_KEY_DERIVATION: 'cortex-share-key-derivation-v1',
  NOTES_ENCRYPTION: 'cortex-notes-encryption-v1',
  TASKS_ENCRYPTION: 'cortex-tasks-encryption-v1',
  EVENTS_ENCRYPTION: 'cortex-events-encryption-v1',
  NOTIFICATION_ENCRYPTION: 'cortex-notification-encryption-v1',
  DATE_BUCKET_ENCRYPTION: 'cortex-date-bucket-encryption-v1',
  SALT_HMAC: 'cortex-salt-hmac-v1',
  // ponytail: spec 6.2 also lists a vault-level "share metadata HMAC key" — deferred,
  // nothing consumes one yet. When built, it must NOT reuse 'cortex-share-hmac-v1'
  // (share-encryption.ts already uses that for a share-password-derived key); pick a
  // domain-separated context, e.g. 'cortex-vault-share-metadata-hmac-v1'.
};

/**
 * Derives a 256-bit vault master key from a vault password and salt using Argon2id.
 * 
 * This function uses memory-hard key derivation to protect against brute-force attacks.
 * The same password and salt will always produce the same master key (deterministic).
 * 
 * @param password - The vault password (string)
 * @param salt - The vault salt (Uint8Array, 16 bytes minimum)
 * @returns Promise<Uint8Array> - The 256-bit (32-byte) vault master key
 * 
 * @example
 * const password = 'my-secure-vault-password';
 * const salt = crypto.getRandomValues(new Uint8Array(16));
 * const masterKey = await deriveVaultMasterKey(password, salt);
 */
export async function deriveVaultMasterKey(
  password: string,
  salt: Uint8Array
): Promise<Uint8Array> {
  if (!password || password.length === 0) {
    throw new Error('Password cannot be empty');
  }

  if (!salt || salt.length < 16) {
    throw new Error('Salt must be at least 16 bytes');
  }

  try {
    // Load Argon2id WASM instance (cached after first load)
    const argon2id = await getArgon2id();
    
    // Convert password string to Uint8Array
    const passwordBytes = new TextEncoder().encode(password);
    
    // Derive vault master key using Argon2id
    const hash = argon2id({
      password: passwordBytes,
      salt,
      ...ARGON2_PARAMS,
    });

    return hash;
  } catch (error) {
    throw new Error(`Failed to derive vault master key: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Interface representing all derived encryption keys for a vault
 */
export interface DerivedKeys {
  /** Key Encryption Key (KEK): wraps per-file DEKs for envelope encryption. */
  keyEncryptionKey: Uint8Array;
  metadataEncryptionKey: Uint8Array;
  shareKeyDerivationKey: Uint8Array;
  notesEncryptionKey: Uint8Array;
  tasksEncryptionKey: Uint8Array;
  eventsEncryptionKey: Uint8Array;
  notificationEncryptionKey: Uint8Array;
  dateBucketEncryptionKey: Uint8Array;
  saltHmacKey: Uint8Array;
}

/**
 * Derives multiple encryption keys from the vault master key using HKDF-SHA256.
 * 
 * Each key is derived with both a unique salt and context string for defense-in-depth
 * domain separation. This provides two independent layers of cryptographic separation.
 * All derived keys are 256 bits (32 bytes) for use with ChaCha20-Poly1305.
 * 
 * @param vaultMasterKey - The 256-bit vault master key (from deriveVaultMasterKey)
 * @returns DerivedKeys - Object containing all derived encryption keys
 * 
 * @example
 * const masterKey = await deriveVaultMasterKey(password, salt);
 * const keys = deriveKeys(masterKey);
 * // Use keys.keyEncryptionKey as the KEK to wrap per-file DEKs (envelope encryption)
 * // Use keys.metadataEncryptionKey for encrypting metadata
 */
export function deriveKeys(vaultMasterKey: Uint8Array): DerivedKeys {
  if (!vaultMasterKey || vaultMasterKey.length !== 32) {
    throw new Error('Vault master key must be 32 bytes (256 bits)');
  }

  const keyLength = 32; // 256 bits for ChaCha20-Poly1305

  try {
    return {
      keyEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.KEY_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.KEY_ENCRYPTION),
        keyLength
      ),
      metadataEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.METADATA_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.METADATA_ENCRYPTION),
        keyLength
      ),
      shareKeyDerivationKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.SHARE_KEY_DERIVATION,
        new TextEncoder().encode(HKDF_CONTEXTS.SHARE_KEY_DERIVATION),
        keyLength
      ),
      notesEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.NOTES_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.NOTES_ENCRYPTION),
        keyLength
      ),
      tasksEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.TASKS_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.TASKS_ENCRYPTION),
        keyLength
      ),
      eventsEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.EVENTS_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.EVENTS_ENCRYPTION),
        keyLength
      ),
      notificationEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.NOTIFICATION_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.NOTIFICATION_ENCRYPTION),
        keyLength
      ),
      dateBucketEncryptionKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.DATE_BUCKET_ENCRYPTION,
        new TextEncoder().encode(HKDF_CONTEXTS.DATE_BUCKET_ENCRYPTION),
        keyLength
      ),
      saltHmacKey: hkdf(
        sha256,
        vaultMasterKey,
        HKDF_SALTS.SALT_HMAC,
        new TextEncoder().encode(HKDF_CONTEXTS.SALT_HMAC),
        keyLength
      ),
    };
  } catch (error) {
    throw new Error(`Failed to derive keys: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Generates a BIP39 mnemonic recovery key from the vault master key.
 * 
 * The recovery key is a 24-word mnemonic phrase that encodes the FULL 256-bit
 * vault master key. This enables complete offline vault recovery without requiring
 * the vault salt from the server. The user can recover their vault with ONLY
 * this 24-word phrase.
 * 
 * SECURITY: This should be displayed to the user ONCE during vault creation with
 * instructions to store it securely offline (paper backup, password manager, etc.).
 * 
 * @param vaultMasterKey - The 256-bit vault master key
 * @returns string - A 24-word BIP39 mnemonic phrase
 * 
 * @example
 * const masterKey = await deriveVaultMasterKey(password, salt);
 * const recoveryKey = generateRecoveryKey(masterKey);
 * console.log('IMPORTANT: Store this 24-word recovery key securely:', recoveryKey);
 */
export function generateRecoveryKey(vaultMasterKey: Uint8Array): string {
  if (!vaultMasterKey || vaultMasterKey.length !== 32) {
    throw new Error('Vault master key must be 32 bytes (256 bits)');
  }

  try {
    // BIP39 requires entropy in multiples of 32 bits (4 bytes)
    // For 24 words, we need 256 bits (32 bytes) of entropy
    // We use the FULL master key to enable complete offline recovery
    const mnemonic = entropyToMnemonic(vaultMasterKey, wordlist);
    return mnemonic;
  } catch (error) {
    throw new Error(`Failed to generate recovery key: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Validates a recovery key and recovers the full vault master key from it.
 * 
 * This function is used during vault password reset. The user provides their
 * recovery key (24-word mnemonic), and this function validates it and returns
 * the complete 256-bit vault master key.
 * 
 * SECURITY: This enables complete offline vault recovery. The user does NOT need
 * the vault salt from the server - the 24-word phrase contains everything needed
 * to recover full vault access.
 * 
 * After recovery, the user can:
 * 1. Use the recovered master key directly to decrypt their vault
 * 2. Set a new vault password and derive a new vault salt
 * 3. Re-encrypt the vault with the new password (optional)
 * 
 * @param recoveryKey - The 24-word BIP39 mnemonic phrase
 * @returns Uint8Array - The complete 256-bit vault master key (32 bytes)
 * @throws Error if the recovery key is invalid
 * 
 * @example
 * const recoveryKey = 'word1 word2 word3 ... word24';
 * const recoveredMasterKey = validateRecoveryKey(recoveryKey);
 * const keys = deriveKeys(recoveredMasterKey);
 * // Now you can decrypt vault data with keys.keyEncryptionKey, etc.
 */
export function validateRecoveryKey(recoveryKey: string): Uint8Array {
  if (!recoveryKey || typeof recoveryKey !== 'string') {
    throw new Error('Recovery key must be a non-empty string');
  }

  // Validate the mnemonic format
  if (!validateMnemonic(recoveryKey, wordlist)) {
    throw new Error('Invalid recovery key format');
  }

  try {
    // Convert mnemonic back to full 256-bit master key
    const masterKey = mnemonicToEntropy(recoveryKey, wordlist);
    
    if (masterKey.length !== 32) {
      throw new Error('Recovery key must be 24 words (256 bits)');
    }
    
    return masterKey;
  } catch (error) {
    throw new Error(`Failed to validate recovery key: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}
