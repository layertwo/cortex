/**
 * Cortex Frontend Encryption Library
 * 
 * Zero-knowledge encryption library for the Cortex productivity suite.
 * All encryption and decryption happens client-side.
 */

// Export encryption functions
export {
  encrypt,
  decrypt,
  generateNonce,
  encryptTagForSearch,
  stringToBytes,
  bytesToString,
  bytesToBase64,
  base64ToBytes,
  NONCE_SIZE,
  TAG_SIZE,
  KEY_SIZE,
} from './lib/encryption';

// Export key management functions
export {
  deriveVaultMasterKey,
  deriveKeys,
  generateRecoveryKey,
  validateRecoveryKey,
  type DerivedKeys,
} from './lib/key-management';

// Export key storage functions
export {
  storeKeys,
  retrieveKeys,
  clearKeys,
  clearAllKeys,
  cleanupExpiredKeys,
  registerCleanupHandlers,
  getStorageInfo,
  clearSaltHmacRecord,
  DEFAULT_CONFIG,
  HIGH_SECURITY_CONFIG,
  type KeysToStore,
  type KeyStorageConfig,
} from './lib/key-storage';

// Export password validation functions
export {
  validatePassword,
  validatePasswordStrength,
  checkPasswordBreach,
  type PasswordValidationResult,
} from './lib/password-validation';

// Export envelope encryption functions
export {
  generateDek,
  wrapDek,
  unwrapDek,
  encryptFileWithDek,
  decryptFileWithDek,
  DekUnwrapError,
  type DekUnwrapErrorCode,
} from './lib/envelope-encryption';

// Export streaming encryption functions
export {
  STREAM_VERSION,
  NONCE_PREFIX_SIZE,
  STREAM_HEADER_SIZE,
  DEFAULT_CHUNK_SIZE,
  generateNoncePrefix,
  buildStreamHeader,
  parseStreamHeader,
  deriveChunkNonce,
  buildChunkAad,
  encryptChunk,
  decryptChunk,
  type ChunkParams,
} from './lib/streaming-encryption';

// Export share encryption functions
export {
  deriveShareKeys,
  computeShareHmac,
  verifyShareHmac,
  encodeShareBlob,
  decodeShareBlob,
  type ShareKeys,
  type ShareBlob,
} from './lib/share-encryption';

// Export vault salt integrity functions
export {
  computeSaltHmac,
  verifySaltHmac,
  bindSaltHmac,
  resetSaltHmac,
  getStoredSaltHmac,
  SaltIntegrityError,
  SALT_HMAC_KEY_BYTES,
  VAULT_SALT_BYTES,
  SALT_HMAC_BYTES,
  type SaltBindingArgs,
} from './lib/vault-salt-integrity';
