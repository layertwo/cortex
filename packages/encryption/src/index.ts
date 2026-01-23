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
