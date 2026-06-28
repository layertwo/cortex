> **Phase A (Cognito Auth Integration) note:** Account authentication and recovery were moved to AWS Cognito (Amplify frontend-direct SRP; API Gateway Cognito authorizer). The Cortex `/v1/auth/*` and `/v1/recovery/*` routes, the recovery-code service/tests, and the Cognito Identity Pool were removed. Some checkboxes below are annotated inline to reflect this. See the Phase A plan and design for full context:
> - `docs/superpowers/plans/2026-06-13-cognito-auth-integration-phase-a.md`
> - `docs/superpowers/specs/2026-06-13-cognito-auth-integration-phase-a-design.md`

- [x] 1. Set up project structure and CDK infrastructure foundation
  - Create directory structure: cdk/, lambda/, frontend/, tests/
  - Initialize CDK project with TypeScript in cdk/
  - Set up Python project structure for Lambda functions
  - Configure package.json and requirements.txt with dependencies
  - Create .gitignore for build artifacts and sensitive files
  - _Requirements: 6.1, 6.2, 8.1_

- [x] 2. Define Smithy API model
  - Create smithy/models/ directory structure
  - Create smithy/models/main.smithy with service definition
  - Define operations for auth, vaults, items, collections, tags, shares, recovery
  - Define input/output structures for all operations
  - Define error types (AuthenticationError, AuthorizationError, etc.)
  - Add validation constraints and documentation
  - Configure Smithy build to generate OpenAPI 3.0 spec
  - Modular structure with separate files for each domain (auth/, vault/, item/, collection/, tag/, share/, recovery/)
  - _Requirements: 6.3, 8.1, 8.2, 8.3, 8.4_

- [x] 3. Implement CDK stacks for AWS infrastructure
- [x] 3.1 Create storage and database stacks (S3 and DynamoDB)
  - Define S3 bucket with server-side encryption (AES-256)
  - Enable versioning for accidental deletion protection
  - Configure CORS for direct client uploads
  - Set up multipart upload configuration (5MB minimum part size)
  - Enable S3 transfer acceleration
  - Configure lifecycle policies for Glacier transition
  - Create DynamoDB tables for Items, Collections, Vaults, Shares
  - Configure on-demand billing with point-in-time recovery
  - _Requirements: 1.3, 2.5, 6.5, 7.4, 7.5, 11.3, 12.2, 17.3, 19.1, 22.1, 22.2_

- [x] 3.2 Create authentication stack (Cognito configuration)
  - Set up Cognito user pool with email/password authentication
  - Configure password policy (12 chars min, complexity requirements)
  - ~~Set up custom authentication flow for recovery codes~~ — Phase A: CUSTOM_AUTH dropped (existed only for the removed recovery-code system)
  - ~~Configure identity pool for federated identities~~ — Phase A: Identity Pool removed (browser uses JWT bearer + presigned URLs, no AWS creds)
  - ~~Set up IAM roles for authenticated users~~ — Phase A: authenticated IAM role removed with the Identity Pool
  - Phase A additions: app client is a public SPA client (no secret), SRP + refresh-only auth flows, self-signup enabled
  - _Requirements: 3.1, 3.2, 19.2, 21.1, 21.2_

- [x] 3.3 Create API stack (API Gateway and Lambda)
  - Define single Lambda function for all API routes
  - Configure API Gateway with REST API and proxy integration
  - Set up Cognito authorizer for authentication
  - Configure Lambda execution IAM role with DynamoDB and S3 permissions
  - Set up CloudWatch logging (data trace disabled for encrypted payloads)
  - Configure rate limiting and throttling
  - _Requirements: 3.4, 6.1, 6.2, 6.4, 8.2_

- [x] 4. Implement Lambda shared utilities
- [x] 4.1 Create shared error handling module
  - Define custom exception classes for all error types
  - Implement error response formatter with structured JSON
  - Add request ID tracking for debugging
  - Sanitize error messages to prevent information leakage
  - _Requirements: 3.5, 8.3_

- [x] 4.2 Create shared authentication utilities
  - Implement function to extract user identity from API Gateway context
  - Add JWT token validation helpers
  - Create user authorization helpers
  - _Requirements: 3.1, 3.2, 3.4_

- [x] 4.3 Create shared repository layer
  - Implement DynamoDB repository base class
  - Create S3 repository for presigned URL generation
  - Add helper functions for DynamoDB queries
  - Implement presigned URL generation with proper scoping
  - _Requirements: 1.4, 1.5, 4.1, 7.1, 7.2_

- [x] 4.4 Create shared data models with Pydantic
  - Define request/response models for all API operations
  - Add validation rules for inputs
  - Create models for DynamoDB items
  - _Requirements: 8.1, 8.3_

- [x] 5. Build encryption library and React web app (monorepo: packages/encryption/ and packages/web/)
- [x] 5.1 Set up monorepo structure with npm workspaces
  - Create packages/encryption/ and packages/web/ directories
  - Create root package.json with workspaces configuration
  - Configure encryption library as @cortex/encryption
  - Configure web app as @cortex/web with dependency on @cortex/encryption
  - _Requirements: 1.1, 2.1, 9.1_

- [x] 5.2 Implement ChaCha20-Poly1305 encryption engine in @cortex/encryption
  - Create packages/encryption/src/lib/encryption.ts with encryption functions using @noble/ciphers
  - Generate random 96-bit nonces for each operation
  - Handle authenticated encryption with 128-bit tags
  - Implement decryption with tag verification
  - Export functions: encrypt(), decrypt(), generateNonce()
  - _Requirements: 1.1, 2.1, 9.1_

- [x] 5.3 Write property test for encryption round-trip
  - Create packages/encryption/tests/property/test_encryption.test.ts
  - Use fast-check for property-based testing
  - **Property 7: Upload and download round-trip preserves content**
  - **Validates: Requirements 4.2**

- [x] 5.4 Implement deterministic tag encryption using HMAC-SHA256
  - Add tag encryption functions to packages/encryption/src/lib/encryption.ts
  - Create tag encryption function for searchable encrypted tags
  - Normalize tags to lowercase before encryption
  - Use @noble/hashes for HMAC-SHA256
  - Export function: encryptTagForSearch()
  - _Requirements: 11.2, 11.4_

- [x] 5.5 Write property test for tag encryption consistency
  - Add to packages/encryption/tests/property/test_encryption.test.ts
  - **Property 13: Encrypted tag search functionality**
  - **Validates: Requirements 11.4, 11.5**

- [x] 6. Implement encryption library key management (@cortex/encryption)
- [x] 6.1 Create vault master key derivation with Argon2id
  - Create packages/encryption/src/lib/key-management.ts
  - Implement Argon2id key derivation using argon2-browser
  - Configure parameters: 64MB memory, 3 iterations, 4 parallelism
  - Derive 256-bit vault master key from vault password + vault salt
  - Export function: deriveVaultMasterKey(password, salt)
  - _Requirements: 14.1, 14.2_

- [x] 6.2 Implement HKDF for derived key generation
  - Add HKDF functions to packages/encryption/src/lib/key-management.ts
  - Use @noble/hashes for HKDF with SHA-256
  - Derive Key Encryption Key (KEK) (context: "cortex-kek-v1") for wrapping per-file DEKs
  - Derive metadata encryption key (context: "cortex-metadata-encryption-v1")
  - Derive share key derivation key (context: "cortex-share-key-derivation-v1")
  - Derive notes encryption key (context: "cortex-notes-encryption-v1")
  - Derive tasks encryption key (context: "cortex-tasks-encryption-v1")
  - Derive events encryption key (context: "cortex-events-encryption-v1")
  - Derive notification encryption key (context: "cortex-notification-encryption-v1")
  - Derive date bucket encryption key (context: "cortex-date-bucket-encryption-v1")
  - Derive vault salt HMAC key (context: "cortex-salt-hmac-v1") for vault salt integrity verification
  - Derive share metadata HMAC key (context: "cortex-share-hmac-v1") for share metadata integrity protection
  - Export function: deriveKeys(vaultMasterKey)
  - _Requirements: 14.2, 22.3, 24.3, 25.1, 26.1_

- [x] 6.3 Implement vault recovery key generation and validation with KEK versioning
  - Add recovery key functions to packages/encryption/src/lib/key-management.ts
  - Generate BIP39 24-word mnemonic from vault master key using bip39 library
  - Display recovery key to user once with secure storage instructions
  - Backend: Store current KEK version number as non-secret metadata in DynamoDB Vaults table
  - Implement recovery key validation for vault password reset
  - Re-derive vault master key from recovery key
  - Fetch current KEK version from DynamoDB Vaults table when recovering (server-assisted path)
  - Derive appropriate versioned KEK from recovered vault master key using HKDF with correct version context
  - If vault has undergone key rotation, derive latest KEK version to access re-wrapped files
  - If server is unavailable during recovery, attempt incremental KEK version derivation (v1, v2, v3...) until decryption succeeds (offline fallback)
  - Allow user to set new vault password while maintaining same vault master key (no re-encryption needed)
  - Export functions: generateRecoveryKey(), validateRecoveryKey(), deriveKekFromRecovery(recoveredMasterKey, kekVersion)
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 15.9, 15.10, 15.11_

- [x] 6.4 Build local key storage with device-specific encryption and integrity checking
  - Create packages/encryption/src/lib/key-storage.ts
  - Encrypt derived keys with device-specific key
  - Store encrypted keys in browser localStorage or secure storage
  - Compute integrity checksum (HMAC over encrypted key blob) and store alongside keys
  - Validate integrity of stored keys on app load using checksum/MAC
  - If checksum fails or storage is corrupted/unavailable:
    - Detect corruption (checksum mismatch, read error, missing entries)
    - Prompt user to re-enter vault password
    - Fetch vault salt from server and re-derive all keys from scratch
    - Store re-derived keys with fresh integrity checksum
  - Implement key retrieval and decryption on device
  - Never transmit keys to server
  - Export functions: storeKeys(), retrieveKeys(), clearKeys(), validateKeyIntegrity()
  - _Requirements: 14.3, 14.6, 14.7, 14.8, 14.9_

- [x] 6.5 Implement password validation with entropy-based strength and breach checking
  - Create packages/encryption/src/lib/password-validation.ts
  - Validate minimum 12 characters for account passwords, 16 characters for share passwords
  - Use zxcvbn or similar entropy estimator to calculate estimated entropy (not just character class requirements)
  - Require minimum estimated entropy of 80 bits for all password types (account, vault, share)
  - Provide clear user feedback: "Password strength: X bits (minimum 80 required)" with actionable guidance
  - Character class requirements (uppercase, lowercase, numbers, special characters) are secondary to entropy
  - Integrate with Have I Been Pwned API using k-anonymity model
  - Client-side SHA-1 hash, send first 5 characters to API
  - Check full hash against returned list locally
  - Reject breached passwords
  - Apply to account passwords, vault passwords, and share passwords
  - Export function: validatePassword(password, type: 'account' | 'vault' | 'share')
  - _Requirements: 18.3, 18.4, 18.5, 18.6, 21.1, 21.2, 21.3, 21.4_

- [x] 6.6 Write property test for vault key derivation determinism
  - Create packages/encryption/tests/property/test_key_management.test.ts
  - **Property 17: Vault key derivation is deterministic**
  - **Validates: Requirements 14.1, 14.2, 14.5**

- [x] 6.7 Write property test for vault recovery key
  - Add to packages/encryption/tests/property/test_key_management.test.ts
  - **Property 18: Vault recovery key enables vault access**
  - **Validates: Requirements 15.3**

- [x] 6.8 Write property test for vault keys never transmitted
  - Add to packages/encryption/tests/property/test_key_management.test.ts
  - **Property 6: Vault keys never transmitted to server**
  - **Validates: Requirements 3.6, 9.3, 14.6, 15.5, 16.4**

- [x] 6.9 Write property test for password strength validation
  - Create packages/encryption/tests/property/test_password_validation.test.ts
  - **Property 23: Password strength validation**
  - **Validates: Requirements 21.1, 21.2**

- [x] 6.10 Write property test for breached password detection
  - Add to packages/encryption/tests/property/test_password_validation.test.ts
  - **Property 24: Breached password detection**
  - **Validates: Requirements 21.3, 21.4**

- [x] 6.11 Write property test for vault salt uniqueness
  - Create lambda/tests/property/test_vault_salt.py (server-side test)
  - **Property 27: Vault salt uniqueness**
  - **Validates: Requirements 22.4**

- [x] 6.12 Implement envelope encryption for media files
  - [x] 6.12.1 Create DEK generation and wrapping functions with key commitment documentation and binary format
    - Add to packages/encryption/src/lib/envelope-encryption.ts
    - Generate unique 256-bit DEK per file using CSPRNG
    - Wrap DEK with KEK using ChaCha20-Poly1305
    - Use documented binary format for wrapped DEKs (65 bytes total, big-endian):
      - Byte 0: Version (0x01)
      - Bytes 1-4: Timestamp (uint32_be, Unix epoch seconds)
      - Bytes 5-16: Nonce (12 bytes)
      - Bytes 17-48: Encrypted DEK (32 bytes)
      - Bytes 49-64: Auth tag (16 bytes)
    - Include DEK version in wrapped format
    - Document that ChaCha20-Poly1305 does not provide key commitment (attacker could find two DEKs decrypting to valid plaintexts)
    - Document that risk is low in Cortex because attacker needs to replace both ciphertext AND wrapped DEK
    - Optional: Compute HMAC(DEK, file_id) and store with wrapped DEK to bind DEK to specific file and prevent key substitution
    - If HMAC binding implemented, verify HMAC during unwrapping
    - Export functions: generateDek(), wrapDek(dek, kek, fileId?, includeBinding?), unwrapDek(wrappedDek, kek)
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5, 28.6, 28.7, 28.8, 28.9, 28.10, 28.11, 28.12_

  - [x] 6.12.2 Create file encryption with DEK
    - Add to packages/encryption/src/lib/envelope-encryption.ts
    - Encrypt file content with DEK using ChaCha20-Poly1305
    - Return encrypted content and wrapped DEK
    - Export function: encryptFileWithDek(content, kek)
    - _Requirements: 28.2, 28.3_

  - [x] 6.12.3 Create file decryption with DEK and error handling
    - Add to packages/encryption/src/lib/envelope-encryption.ts
    - Unwrap DEK using KEK with error handling
    - Return specific error codes for failure types:
      - CORRUPTED_DEK: Authentication tag verification failed or malformed structure
      - WRONG_KEK_VERSION: KEK version mismatch during rotation
      - AUTHENTICATION_FAILED: Generic decryption failure
    - When CORRUPTED_DEK occurs, allow user to mark file as corrupted, delete it, or report issue
    - When WRONG_KEK_VERSION occurs, inform user "Key rotation in progress, try again in a few minutes"
    - Log unwrapping failures (without key material) for monitoring corruption rates and version mismatches
    - Decrypt file content with unwrapped DEK
    - Overwrite DEK buffer with zeros before dereferencing (see REQ-34 for comprehensive zeroization)
    - Use TypedArray (Uint8Array) for DEK to enable explicit zeroing
    - Export function: decryptFileWithDek(encryptedContent, wrappedDek, kek)
    - Export error types: DekUnwrapError { code: 'CORRUPTED_DEK' | 'WRONG_KEK_VERSION' | 'AUTHENTICATION_FAILED', message: string }
    - _Requirements: 29.2, 29.3, 29.4, 29.5, 29.6, 29.7, 29.8, 29.9, 29.10, 29.11_

  - [x]* 6.12.4 Write property test for envelope encryption round-trip
    - Create packages/encryption/tests/property/test_envelope_encryption.test.ts
    - **Property 32: Envelope encryption round-trip**
    - **Validates: Requirements 28.1, 28.2, 28.3, 29.2, 29.3**

  - [x]* 6.12.5 Write property test for DEK uniqueness
    - Add to packages/encryption/tests/property/test_envelope_encryption.test.ts
    - **Property 33: DEK uniqueness**
    - **Validates: Requirements 28.4, 28.5**

- [ ] 6.13 Implement efficient key rotation with envelope encryption
  - [ ] 6.13.1 Create KEK versioning system with state machine and concurrent rotation lock
    - Add to packages/encryption/src/lib/key-rotation.ts
    - Generate new KEK with incremented version context (e.g., "cortex-kek-v2")
    - Maintain rotation state machine: NOT_STARTED, IN_PROGRESS, PAUSED, COMPLETED, FAILED
    - Store rotation state in IndexedDB
    - Track KEK version in local key storage and DynamoDB Vaults table
    - Acquire rotation lock in DynamoDB Vaults table using conditional write on rotationState (ConditionExpression: rotationState = IDLE OR rotationLockedAt expired)
    - Reject rotation if another device already holds the lock; inform user rotation is in progress on another device
    - Auto-expire rotation locks after 7 days to prevent permanent lock-out from crashed clients
    - Release rotation lock (set rotationState = IDLE) on completion, rollback, or failure
    - Export function: deriveKekWithVersion(vaultMasterKey, version), acquireRotationLock(vaultId), releaseRotationLock(vaultId)
    - Export type: RotationState = 'NOT_STARTED' | 'IN_PROGRESS' | 'PAUSED' | 'COMPLETED' | 'FAILED'
    - _Requirements: 20.2, 20.3, 20.19, 20.20, 20.21, 20.22, 30.1_

  - [ ] 6.13.2 Create batch DEK re-wrapping functions with memory management and idempotency
    - Add to packages/encryption/src/lib/key-rotation.ts
    - Download wrapped DEKs from server (not file content)
    - Process DEKs in configurable batches (recommended default: 100-500 per batch)
    - Monitor browser heap memory usage during batch processing
    - Auto-pause rotation if memory usage exceeds 80% of available heap
    - Clear processed DEK buffers immediately after upload to manage memory
    - Unwrap each DEK with old KEK
    - Re-wrap each DEK with new KEK
    - Use conditional DynamoDB updates (ConditionExpression on dekVersion) for idempotent writes
    - When conditional update fails (ConditionalCheckFailedException), skip the already re-wrapped item and continue
    - Upload re-wrapped DEKs to server
    - Retry failed batches with exponential backoff (max 3 attempts)
    - If batch fails after 3 attempts, pause rotation and prompt user
    - Export function: rotateKeys(vaultId, oldKek, newKek, batchSize, memoryThreshold)
    - _Requirements: 30.2, 30.3, 30.4, 33.2, 33.3, 33.5, 33.6, 33.7, 33.12, 33.13_

  - [ ] 6.13.3 Create dual-KEK access during rotation with error recovery
    - Add to packages/encryption/src/lib/key-rotation.ts
    - Maintain both old and new KEKs during transition
    - Check DEK version to determine which KEK to use
    - Store rotation progress in IndexedDB: vault ID, old KEK version, new KEK version, last processed item cursor (sort key)
    - Use cursor-based progress tracking (lastProcessedSortKey) instead of storing complete lists of processed item IDs to avoid exceeding IndexedDB quotas for large vaults
    - Resume from checkpoint on browser crash or network failure by validating both KEKs accessible
    - Provide rollback option for unrecoverable errors to mark rotation as failed and continue with old KEK
    - Auto-pause rotation if not completed within 7 days and prompt user to resume or rollback
    - Securely zeroize old KEK from memory after rotation completes (overwrite with zeros then random data)
    - Clear old KEK after rotation completes
    - Export function: getKekForDekVersion(keys, dekVersion)
    - _Requirements: 20.4, 20.5, 20.6, 20.7, 20.12, 30.5, 30.6_

  - [ ] 6.13.4 Create rotation progress tracking with state persistence
    - Add to packages/encryption/src/lib/key-rotation.ts
    - Track total items, processed items, failed items
    - Store progress in IndexedDB for recovery from interruptions using cursor-based pagination (lastProcessedSortKey)
    - Check navigator.storage.estimate() before starting rotation to verify available IndexedDB quota
    - Support pause and resume for large vaults
    - Report progress to UI with estimated remaining time
    - Block share creation during rotation (shares must use new KEK only)
    - New uploads use new KEK; in-progress downloads use KEK matching file's DEK version
    - Provide clear indication to user when rotation is incomplete and dual-KEK access is active
    - Export interface: KeyRotationProgress { state, totalItems, processedItems, lastProcessedSortKey, failedItems, oldKekVersion, newKekVersion }
    - _Requirements: 20.8, 20.9, 20.10, 33.1, 33.4, 33.8, 33.9, 33.10, 33.11_

  - [ ]* 6.13.5 Write property test for key rotation efficiency
    - Add to packages/encryption/tests/property/test_key_rotation.test.ts
    - **Property 34: Key rotation efficiency**
    - **Validates: Requirements 30.2, 30.4**

  - [ ]* 6.13.6 Write property test for key rotation round-trip
    - Add to packages/encryption/tests/property/test_key_rotation.test.ts
    - **Property 35: Key rotation round-trip**
    - **Validates: Requirements 30.1, 30.3, 30.6**

  - [ ]* 6.13.7 Write property test for dual-KEK access during rotation
    - Add to packages/encryption/tests/property/test_key_rotation.test.ts
    - **Property 36: Dual-KEK access during rotation**
    - **Validates: Requirements 30.5**

- [x] 6.14 Implement password-required file sharing with envelope encryption
  - **Done note:** consolidated into `packages/encryption/src/lib/share-encryption.ts` (`deriveShareKeys`/`computeShareHmac`/`verifyShareHmac`/`encodeShareBlob`/`decodeShareBlob`) rather than the per-function `sharing.ts` layout below; UI in `ShareCreate.tsx`/`ShareAccess.tsx`, backend in `share_service.py`. Requirements met; function/file names differ from subtask text.
  - [x] 6.14.1 Create share encryption key derivation with salted HMAC
    - Add to packages/encryption/src/lib/sharing.ts
    - Generate unique random share salt (16 bytes) using CSPRNG
    - Derive share encryption key from password + share salt using Argon2id
    - Derive share HMAC key using HKDF with share encryption key, share salt, and context "cortex-share-hmac-v1"
    - Export functions: deriveShareKey(password, salt), deriveShareHmacKey(shareKey, salt)
    - _Requirements: 17.2, 17.3, 17.4, 31.2_

  - [x] 6.14.2 Create share-wrapped DEK generation with timestamp nonce
    - Add to packages/encryption/src/lib/sharing.ts
    - Unwrap file's DEK using vault's KEK
    - Wrap DEK with share encryption key
    - Generate timestamp nonce representing share creation time
    - Derive HMAC key from share encryption key using HKDF with share salt and context "cortex-share-hmac-v1"
    - Compute HMAC-SHA256 over share metadata (shareId, expiration timestamp, timestamp nonce) using HMAC key
    - Export function: createShareWrappedDek(wrappedDek, kek, shareKey, shareSalt, timestampNonce)
    - _Requirements: 17.5, 17.6, 17.7, 31.3, 31.4_

  - [x] 6.14.3 Create share URL generation with nonce
    - Add to packages/encryption/src/lib/sharing.ts
    - Embed password-wrapped DEK, share salt, HMAC, and timestamp nonce in URL fragment
    - Format: {shareId}#{base64(salt)}:{base64(wrappedDek)}:{base64(hmac)}:{base64(timestampNonce)}
    - Ensure key material never sent to server
    - Export function: createShareUrl(shareId, shareWrappedDek, salt, hmac, timestampNonce)
    - _Requirements: 17.4, 17.8, 31.4, 31.5_

  - [x] 6.14.4 Create share access functions with HMAC verification and replay protection
    - Add to packages/encryption/src/lib/sharing.ts
    - Extract wrapped DEK, salt, HMAC, and timestamp nonce from URL fragment
    - Fetch share metadata (shareId, expiration) from server
    - Derive share encryption key from password + salt using Argon2id
    - Derive HMAC key from share encryption key using HKDF with share salt and context "cortex-share-hmac-v1"
    - Recompute HMAC-SHA256 over server-provided metadata (shareId, expiration) plus timestamp nonce from URL
    - Verify computed HMAC matches HMAC from URL using constant-time comparison
    - If HMAC verification fails, display error indicating share metadata tampering
    - Server validates timestamp nonce is within share expiration window to prevent replay attacks
    - Unwrap DEK using share encryption key
    - Implement client-side exponential backoff after 3 failed attempts (UX improvement, not security layer)
    - Do NOT re-validate share password entropy at access time; entropy is validated at creation time only (prevents zxcvbn dictionary updates from retroactively blocking access)
    - Export function: accessShare(shareUrl, password)
    - _Requirements: 17.7, 17.8, 17.10, 17.11, 17.12, 17.13, 17.14, 17.15, 17.16, 17.17, 18.3, 18.4, 18.5, 18.6, 18.11, 18.13, 18.14, 31.6_

  - [ ]* 6.14.5 Write property test for share creation round-trip
    - Add to packages/encryption/tests/property/test_sharing.test.ts
    - **Property 37: Share creation round-trip**
    - **Validates: Requirements 31.1, 31.2, 31.4, 31.5**

  - [ ]* 6.14.6 Write property test for share isolation and zero-knowledge
    - Add to packages/encryption/tests/property/test_sharing.test.ts
    - **Property 38: Share isolation and zero-knowledge**
    - **Validates: Requirements 31.3, 31.6**

- [ ] 6.15 Implement DEK versioning and downgrade protection
  - [ ] 6.15.1 Create DEK version handling with deprecation policy and deployment strategy
    - Add to packages/encryption/src/lib/envelope-encryption.ts
    - Include version identifier in wrapped DEK metadata
    - Maintain lists: SUPPORTED_DEK_VERSIONS, DEPRECATED_DEK_VERSIONS, CURRENT_DEK_VERSION
    - Implement two-phase version deployment: Phase 1 (SUPPORTED only, 30+ days) → Phase 2 (CURRENT)
    - Ensure rollback from Phase 2 to Phase 1 is safe (old version stays SUPPORTED, no data loss)
    - Ensure rollback from Phase 1 is safe (no DEKs wrapped with new version in Phase 1)
    - Maintain backward compatibility with all non-deprecated DEK versions
    - Refuse to unwrap DEKs with deprecated/unsupported versions
    - Provide migration path and user guidance for deprecated versions
    - Use constant-time comparison when verifying DEK authentication tags
    - Support reading DEKs wrapped with any supported (non-deprecated) version
    - Export function: getWrappedDekVersion(wrappedDek), isDekVersionDeprecated(version)
    - _Requirements: 32.1, 32.2, 32.3, 32.5, 32.6, 32.7, 32.8, 32.9, 35.1, 35.2, 35.3_

  - [ ]* 6.15.2 Write property test for DEK version compatibility
    - Add to packages/encryption/tests/property/test_envelope_encryption.test.ts
    - **Property 39: DEK version compatibility**
    - **Validates: Requirements 32.1, 32.2, 32.3, 32.5**

  - [ ]* 6.15.3 Write property test for batch rotation with retry
    - Add to packages/encryption/tests/property/test_key_rotation.test.ts
    - **Property 40: Batch rotation with retry**
    - **Validates: Requirements 33.1, 33.2, 33.4, 33.5, 33.6**

- [ ] 6.16 Implement secure key zeroization on logout (REQ-34)
  - [ ] 6.16.1 Create key zeroization utilities
    - Add to packages/encryption/src/lib/key-storage.ts
    - Use TypedArray (Uint8Array) for all key material storage
    - Implement secure buffer clearing: overwrite twice (first with zeros, then with random data)
    - Create function to zeroize individual key buffers
    - Export function: secureZeroize(buffer: Uint8Array)
    - _Requirements: 34.1, 34.2_

  - [ ] 6.16.2 Implement logout key clearing
    - Add to packages/encryption/src/lib/key-storage.ts
    - On logout, overwrite all key material buffers:
      - Vault master key
      - KEK (current and old during rotation)
      - All derived keys (metadata, notes, tasks, events, notification, date bucket)
      - All cached DEKs
    - Clear all browser storage containing encrypted keys:
      - localStorage
      - sessionStorage
      - IndexedDB
    - Export function: clearAllKeys()
    - _Requirements: 34.1, 34.2, 34.3, 34.4_

  - [ ] 6.16.3 Implement session timeout handling
    - Add to packages/encryption/src/lib/key-storage.ts
    - Perform same key zeroization on session timeout as explicit logout
    - Track last activity timestamp
    - Auto-logout after inactivity period
    - Export function: handleSessionTimeout()
    - _Requirements: 34.8_

  - [ ] 6.16.4 Implement beforeunload key clearing
    - Add to packages/web/src/hooks/useKeyCleanup.ts (React hook)
    - Register beforeunload event handler for unexpected tab/window close
    - Attempt best-effort key zeroization
    - Document that this is best-effort due to browser limitations
    - _Requirements: 34.5_

  - [ ] 6.16.5 Use Web Crypto API non-extractable keys
    - Update packages/encryption/src/lib/key-management.ts
    - Prefer crypto.subtle.generateKey() with extractable: false where possible
    - Use CryptoKey objects instead of raw Uint8Array for keys when feasible
    - Document which keys can be non-extractable vs. which need to be extractable
    - _Requirements: 34.7_

  - [ ] 6.16.6 Document JavaScript memory clearing limitations
    - Add to packages/encryption/README.md
    - Document that complete memory clearing cannot be guaranteed in JavaScript
    - Explain garbage collection and browser memory management limitations
    - List best practices implemented (TypedArray, double overwrite, Web Crypto API)
    - _Requirements: 34.6_

  - [ ]* 6.16.7 Write property test for key zeroization
    - Create packages/encryption/tests/property/test_key_zeroization.test.ts
    - **Property 41: Key material is zeroized on logout**
    - Verify buffers are overwritten with zeros then random data
    - Verify browser storage is cleared
    - **Validates: Requirements 34.1, 34.2, 34.3, 34.4**

- [x] 7. Build React web application (@cortex/web)
- [x] 7.1 Set up React web app with Vite
  - Create packages/web/src directory structure
  - Configure Vite build tooling
  - Import @cortex/encryption for all cryptographic operations
  - Set up TypeScript configuration with reference to encryption package
  - _Requirements: 1.1, 2.1, 9.1_

- [x] 7.2 Create React components for authentication
  - Build Login component (account password authentication)
  - Build Signup component (account + vault password setup)
  - Build VaultUnlock component (vault password entry for key derivation)
  - Use @cortex/encryption for password validation and key derivation
  - _Requirements: 3.1, 3.2, 14.1, 14.2, 21.1, 21.2_

- [x] 7.3 Create React components for file management
  - Build FileUpload component (encrypt and upload files)
  - Build FileList component (list and decrypt metadata)
  - Build FileDownload component (download and decrypt files)
  - Use @cortex/encryption for all encryption/decryption operations
  - _Requirements: 1.1, 1.4, 2.1, 2.3, 4.1, 4.2_

- [x] 7.4 Create React components for collections and tags
  - Build CollectionManager component
  - Build TagSearch component
  - Use @cortex/encryption for tag encryption
  - _Requirements: 11.2, 11.4, 12.1, 13.1_

- [x] 8. Implement Lambda API handler foundation
- [x] 8.1 Create main Lambda handler with APIGatewayRestResolver
  - Update lambda/src/api/handler.py with Lambda Powertools
  - Configure Logger, Tracer, and Metrics
  - Initialize APIGatewayRestResolver
  - Set up error handling with format_error_response
  - _Requirements: 6.1, 6.2_

- [x] 8.2 Create route registration system
  - Create lambda/src/api/routes/ directory structure
  - Create route modules: auth.py, vaults.py, items.py, collections.py, tags.py, shares.py, recovery.py
  - Import and register all routes in api_router in Service Provider
  - Setup handler at lambda/src/entrypoint/api.py to run the API handler
  - _Requirements: 8.1, 8.2_

- [x] 9. Implement authentication routes and services — **REMOVED / superseded by Cognito (Phase A)**. Account sign-in, refresh, and recovery now happen frontend-direct against Cognito via Amplify; the `/v1/auth/*` and `/v1/recovery/*` routes, the auth/recovery service layers, and their tests were deleted this branch.
- [x] 9.1 Create authentication route handlers — **REMOVED (Phase A)**: `/v1/auth/login|refresh|recover` route handlers deleted; the API Gateway Cognito authorizer now extracts user identity (`sub` → userId).
  - ~~Implement POST /v1/auth/login route~~
  - ~~Implement POST /v1/auth/refresh route~~
  - ~~Implement POST /v1/auth/recover route~~
  - Extract user identity from API Gateway context (now done by the native Cognito authorizer)
  - _Requirements: 3.1, 3.2, 19.2_

- [x] 9.2 Create authentication service layer — **REMOVED (Phase A)**: auth service deleted; registration, login validation, and token refresh are owned by Cognito.
  - ~~Implement user registration logic~~ (Cognito self-signup)
  - ~~Implement login validation~~ (Cognito SRP)
  - ~~Handle token refresh~~ (Cognito refresh tokens)
  - ~~Implement custom authentication flow for recovery codes~~ (CUSTOM_AUTH dropped)
  - _Requirements: 3.1, 3.2_

- [x] 9.3 Implement account recovery code system — **REMOVED (Phase A)**: recovery-code service and Account Recovery table usage deleted; account recovery is now Cognito forgot-password (email).
  - ~~Generate 10 recovery codes at signup (16 chars, format: XXXX-XXXX-XXXX-XXXX)~~
  - ~~Hash codes with SHA-256 before storage in DynamoDB~~
  - ~~Store in Account Recovery table~~
  - ~~Validate recovery codes during account recovery~~
  - ~~Invalidate used codes (mark as used, set usedAt timestamp)~~
  - _Requirements: 19.1, 19.2, 19.3, 19.5_

- [x] 9.4 Write property test for account recovery code validation — **REMOVED (Phase A)**: property test deleted along with the recovery-code system (recovery now verified via Cognito).
  - ~~**Property 25: Account recovery code validation**~~
  - **Validates: Requirements 19.2, 19.3**

- [x] 10. Implement vault management routes and services
- [x] 10.1 Create vault route handlers
  - Implement POST /v1/vaults route (create vault with salt)
  - Implement GET /v1/vaults/{id}/salt route (retrieve salt for key derivation)
  - _Requirements: 14.4, 22.1, 22.2, 22.3_

- [x] 10.2 Create vault service layer with salt integrity protection and recovery
  - Backend: Generate unique vault salt using cryptographically secure RNG (16 bytes)
  - Backend: Store vault salt, current KEK version, rotationState (IDLE/IN_PROGRESS), and rotationLockedAt in DynamoDB Vaults table
  - Backend: Retrieve vault salt for key derivation on new devices
  - Backend: Ensure vault salt uniqueness across all vaults
  - Frontend: Derive HMAC key from vault master key using HKDF with salt and context "cortex-salt-hmac-v1"
  - Frontend: Compute HMAC-SHA256 over vault salt using derived HMAC key on first access
  - Frontend: Store vault salt HMAC locally for integrity verification
  - Frontend: Verify HMAC on subsequent accesses using constant-time comparison
  - Frontend: Display security warning and refuse key derivation if HMAC verification fails
  - Frontend: Provide "reset salt HMAC" option requiring re-authentication with both account password and vault password
  - Frontend: On salt HMAC reset, re-compute HMAC using newly authenticated vault password and update locally stored HMAC
  - Frontend: Document recovery procedure for HMAC verification failures including legitimate salt changes (account recovery)
  - _Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7, 22.8, 22.9, 22.10, 22.11, 22.12_

- [x] 10.3 Write property test for vault salt uniqueness
  - **Property 27: Vault salt uniqueness**
  - **Validates: Requirements 22.4**

- [x] 11. Implement item upload routes and services (generic for all item types)
- [x] 11.1 Create item upload route handlers
  - Implement POST /v1/items/upload/init route (for MEDIA items with S3 storage)
  - Implement POST /v1/items route (for NOTE, TASK, EVENT items with inline encrypted content)
  - Implement POST /v1/items/upload/complete route (for MEDIA items)
  - Extract user identity from API Gateway context
  - Support item type parameter (MEDIA, NOTE, TASK, EVENT)
  - _Requirements: 1.4, 1.5, 7.1, 7.2, 24.1, 24.2_

- [x] 11.2 Create item upload service layer
  - Validate user permissions (user can only upload to own namespace)
  - For MEDIA items: Generate presigned S3 PUT URLs scoped to user's S3 prefix
  - For MEDIA items: Configure multipart upload for files >100MB (5MB min part size)
  - For MEDIA items: Store wrapped DEK in DynamoDB alongside encrypted metadata
  - For NOTE/TASK/EVENT items: Store encrypted content directly in DynamoDB
  - Return upload URL with 15-minute expiration (MEDIA only)
  - Store encrypted metadata in DynamoDB with user isolation
  - Link items to user account using userId from Cognito token
  - Handle encrypted tags storage
  - Store item type and encryption scheme in DynamoDB
  - _Requirements: 1.2, 1.4, 1.5, 2.1, 2.2, 2.4, 4.5, 7.1, 7.2, 7.4, 11.3, 24.1, 24.2, 24.3, 28.4, 28.6_

- [x] 11.3 Add upload error handling and cleanup logic
  - Handle S3 upload failures with DynamoDB cleanup (MEDIA items)
  - Handle DynamoDB failures with S3 cleanup (MEDIA items)
  - Implement idempotency for critical operations
  - _Requirements: 2.5_

- [x] 11.4 Write property test for frontend encryption before transmission
  - **Property 1: Frontend encryption before transmission**
  - **Note: Moved to frontend tests (packages/encryption/) - encryption happens client-side**
  - **Validates: Requirements 1.1, 2.1, 11.2, 12.1, 13.1, 24.3**

- [x] 11.5 Write property test for server storage preserves encryption
  - **Property 2: Server storage preserves encryption**
  - **Note: Covered by Property 28 - backend treats data as opaque bytes**
  - **Validates: Requirements 1.2, 2.2, 11.3, 12.2, 24.3**

- [x] 11.6 Write property test for referential integrity
  - **Property 5: Referential integrity between S3 and DynamoDB**
  - **File: lambda/tests/property/test_item_api.py**
  - **Validates: Requirements 2.5**

- [x] 11.7 Write property test for generic item API supports all types
  - **Property 28: Generic item API supports all types**
  - **File: lambda/tests/property/test_item_api.py**
  - **Validates: Requirements 24.1, 24.2, 24.3**

- [x] 12. Implement item download and listing routes and services
- [x] 12.1 Create item listing route handlers
  - Implement GET /v1/items route (list all items with optional type filter)
  - Implement GET /v1/items/{id} route (get specific item)
  - Extract user identity and query parameters
  - Support filtering by item type (MEDIA, NOTE, TASK, EVENT)
  - _Requirements: 2.3, 10.1, 10.2, 24.1, 24.2_

- [x] 12.2 Create item listing service layer
  - Query DynamoDB for user's encrypted metadata
  - Implement pagination with consistent results (use DynamoDB pagination tokens)
  - Support filtering by item type and sorting by timestamp
  - Enforce user boundary restrictions (filter by userId and vaultId)
  - Return encrypted data without decryption
  - _Requirements: 2.3, 2.4, 10.1, 10.2, 10.4, 10.5, 24.1, 24.2_

- [x] 12.3 Create item download route handler
  - Implement GET /v1/items/{id}/download route (for MEDIA items)
  - Extract user identity from context
  - Return error for non-MEDIA items
  - _Requirements: 4.1, 4.3, 24.2_

- [x] 12.4 Create item download service layer
  - Query DynamoDB to verify user owns requested item
  - Verify item type is MEDIA
  - Generate presigned S3 GET URLs scoped to specific object
  - Return time-limited download URL (15 minutes) and wrapped DEK
  - Return authorization errors for unauthorized access
  - _Requirements: 4.1, 4.3, 4.4, 24.2, 29.1_

- [ ]* 12.5 Write property test for server responses contain only encrypted data
  - **Property 3: Server responses contain only encrypted data**
  - **Validates: Requirements 2.3, 10.3, 12.4, 13.5, 24.3**

- [ ]* 12.6 Write property test for item list queries respect vault boundaries
  - **Property 11: File list queries respect vault boundaries**
  - **Validates: Requirements 10.1, 10.4**

- [ ]* 12.7 Write property test for pagination consistency
  - **Property 12: Pagination consistency**
  - **Validates: Requirements 10.2**

- [ ]* 12.8 Write property test for vault data isolation
  - **Property 4: Vault data isolation**
  - **Validates: Requirements 2.4, 3.3, 4.3, 5.1**

- [x] 13. Implement item deletion routes and services
- [x] 13.1 Create item deletion route handler
  - Implement DELETE /v1/items/{id} route
  - Extract user identity from context
  - Support all item types (MEDIA, NOTE, TASK, EVENT)
  - _Requirements: 5.1, 24.2_

- [x] 13.2 Create item deletion service layer
  - Verify user ownership before deletion
  - For MEDIA items: Delete S3 object and DynamoDB metadata atomically
  - For NOTE/TASK/EVENT items: Delete DynamoDB record only
  - Handle partial failures with rollback (cleanup)
  - Return deletion confirmation
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 24.2_

- [ ]* 13.3 Write property test for deletion maintains referential integrity
  - **Property 8: Deletion maintains referential integrity**
  - **Validates: Requirements 5.2, 5.3, 5.4**

- [x] 14. Implement collection management routes and services
- [x] 14.1 Create collection CRUD route handlers — **Phase A: vault-ownership enforcement added** (closes the cross-tenant read/write gap)
  - Implement POST /v1/collections route (create)
  - Implement GET /v1/collections route (list)
  - Implement GET /v1/collections/{id} route (get details)
  - Implement PUT /v1/collections/{id} route (update)
  - Implement DELETE /v1/collections/{id} route (delete)
  - Phase A: all seven collection routes now raise 404 when `vault_exists()` is false (previously the boolean was discarded, permitting cross-tenant access)
  - _Requirements: 12.1, 12.2, 13.1, 13.3, 13.4, 13.5_

- [x] 14.2 Create collection service layer
  - Create collection with encrypted metadata
  - List user's collections with item counts
  - Update collection metadata
  - Delete collection while preserving items
  - Enforce user isolation for all operations
  - _Requirements: 12.1, 12.2, 13.1, 13.3, 13.4, 13.5_

- [x] 14.3 Create item-collection association route handlers
  - Implement POST /v1/collections/{id}/items route (add items)
  - Implement DELETE /v1/collections/{id}/items/{itemId} route (remove items)
  - Support all item types (MEDIA, NOTE, TASK, EVENT)
  - _Requirements: 12.3, 12.5, 13.2_

- [x] 14.4 Create item-collection association service layer
  - Add items to collections (many-to-many support)
  - Remove items from collections (preserve items)
  - Query collections by item ID (using GSI)
  - Query items by collection ID
  - Update collection item counts
  - _Requirements: 12.3, 12.5, 13.2_

- [ ]* 14.5 Write property test for item-collection many-to-many relationships
  - **Property 14: File-collection many-to-many relationships**
  - **Validates: Requirements 12.3, 12.5**

- [ ]* 14.6 Write property test for collection deletion preserves items
  - **Property 15: Collection deletion preserves files**
  - **Validates: Requirements 13.3, 13.4**

- [ ]* 14.7 Write property test for item removal from collection preserves item
  - **Property 16: File removal from collection preserves file**
  - **Validates: Requirements 13.2**

- [x] 15. Implement tag search routes and services
- [x] 15.1 Create tag search route handler
  - Implement GET /v1/tags/search route
  - Extract encrypted search term from query parameters
  - Extract user identity from context
  - _Requirements: 11.4, 11.5_

- [x] 15.2 Create tag search service layer
  - Receive encrypted search term from client
  - Query DynamoDB GSI for matching encrypted tags
  - Return matching items with encrypted metadata
  - Enforce user isolation (filter by vaultId)
  - _Requirements: 11.4, 11.5_

- [ ]* 15.3 Write property test for encrypted tag search functionality
  - **Property 13: Encrypted tag search functionality**
  - **Validates: Requirements 11.4, 11.5**

- [ ] 16. Implement password change functionality
- [ ] 16.1 Create account password change route handler (frontend)
  - Implement account password change flow with Cognito
  - Update Cognito credentials with new account password
  - Verify vault encryption keys remain unchanged
  - No re-encryption required
  - _Requirements: 23.1, 23.2_

- [ ] 16.2 Create vault password change functionality with KEK versioning and progress tracking (frontend)
  - Derive new vault master key from new vault password and existing vault salt using Argon2id
  - Generate new KEK with incremented version number using HKDF with updated version context (e.g., "cortex-kek-v2")
  - Store KEK version alongside each wrapped DEK in DynamoDB to track which version was used for wrapping
  - Implement progress tracking in IndexedDB storing vault ID, old KEK version, new KEK version, and last processed item cursor (sort key)
  - Resume from checkpoint if process is interrupted (network failure, browser crash) by validating both KEKs accessible
  - Download only wrapped DEKs from server (not file content)
  - Re-wrap all DEKs in configurable batches to manage memory usage
  - Check DEK's version metadata to determine whether to use old or new KEK for unwrapping during transition
  - Upload re-wrapped DEKs to server with new version metadata
  - Maintain dual-KEK access during transition allowing both old and new KEKs to unwrap files
  - Update local key storage with new KEK version upon completion
  - Securely clear old KEK from memory after completion
  - _Requirements: 23.3, 23.4, 23.5, 23.6, 23.7, 23.8, 23.9, 23.10, 23.11_

- [ ]* 16.3 Write property test for account password change independence
  - **Property 21: Account password change does not affect vault encryption**
  - **Validates: Requirements 23.1**

- [ ]* 16.4 Write property test for vault password change DEK re-wrapping
  - **Property 22: Vault password change requires DEK re-wrapping**
  - **Validates: Requirements 23.3, 23.4**

- [x] 17. Implement file sharing system
- [x] 17.1 Build frontend share creation with envelope encryption
  - Require share password (no passwordless sharing)
  - Validate password meets minimum strength requirements (16+ chars with 80 bits entropy)
  - Generate random share salt (16 bytes)
  - Derive share encryption key from password + salt using Argon2id
  - Unwrap file's DEK using vault's KEK
  - Wrap DEK with share encryption key
  - Derive HMAC key from share password using HKDF (context: "cortex-share-hmac-v1")
  - Compute HMAC-SHA256 over share metadata (shareId, expiration) using HMAC key
  - Create share URL with embedded password-wrapped DEK, salt, and HMAC in fragment
  - Display warning about not using URL shorteners
  - Provide alternative share ID + password entry method for truncated URLs
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.10, 17.11, 18.3, 31.1, 31.2, 31.3, 31.4_

- [x] 17.2 Create share route handlers
  - Implement POST /v1/shares route (create share metadata only, no keys)
  - Implement GET /v1/shares/{id} route (access share, anonymous)
  - Implement DELETE /v1/shares/{id} route (revoke share)
  - _Requirements: 17.4, 17.5, 17.7, 18.2, 18.5_

- [x] 17.3 Create share service layer with server-side rate limiting — **Phase A: error mapping completed** (rate-limit → 429 + `Retry-After`, revoked/expired → 410, with structured error bodies; previously these fell through to 500)
  - Store share metadata only (share ID, file reference, creation time, optional expiration, access count)
  - Never store any key material (DEK, wrapped DEK, share key, salt, HMAC)
  - Validate share access (check optional expiration and revocation)
  - Implement server-side rate limiting: max 5 password attempts per IP per share ID per hour
  - Return HTTP 429 with Retry-After header when rate limit exceeded
  - Log rate limit violations for security monitoring
  - Allow anonymous access to shared files
  - Generate presigned S3 URLs for shared file downloads
  - Track access count and last accessed time
  - _Requirements: 17.4, 17.5, 17.7, 18.1, 18.2, 18.5, 18.6, 18.7, 18.9, 31.5_

- [x] 17.4 Build frontend share access with envelope encryption and HMAC verification
  - Extract password-wrapped DEK, salt, and HMAC from URL fragment
  - Fetch share metadata (shareId, expiration) from server
  - Prompt for share password
  - Derive HMAC key from share password using HKDF (context: "cortex-share-hmac-v1")
  - Compute HMAC-SHA256 over received share metadata using HMAC key
  - Verify computed HMAC matches HMAC from URL using constant-time comparison
  - If HMAC verification fails, display error indicating share metadata tampering
  - Derive share encryption key from password + salt using Argon2id
  - Unwrap DEK using share encryption key
  - Implement client-side rate limiting (exponential backoff after 3 failed attempts)
  - Display generic error for incorrect password (prevent enumeration)
  - Download encrypted file from S3 via presigned URL
  - Decrypt file using unwrapped DEK
  - Overwrite DEK buffer with zeros before dereferencing
  - _Requirements: 17.5, 17.6, 17.7, 17.8, 18.4, 18.5, 31.6_

- [x]* 17.5 Write property test for share keys enable file access without vault password
  - **Property 20: Share keys enable file access without vault password**
  - **Validates: Requirements 17.1, 17.4**

- [ ] 18. Implement automatic key rotation with envelope encryption (frontend)
- [ ] 18.1 Build key rotation trigger and monitoring
  - Monitor key age (90 days since last rotation)
  - Trigger automatic rotation
  - Support manual rotation via user settings
  - _Requirements: 20.1_

- [ ] 18.2 Implement efficient DEK re-wrapping process with active operation handling
  - Generate new KEK with incremented version context (e.g., "cortex-kek-v2")
  - Acquire rotation lock in DynamoDB Vaults table using conditional write on rotationState (only one rotation per vault at a time)
  - If lock acquisition fails, inform user that rotation is already in progress on another device
  - Download only wrapped DEKs from server (not file content)
  - Process DEKs in configurable batches (default 100)
  - Unwrap each DEK with old KEK
  - Re-wrap each DEK with new KEK
  - Use conditional DynamoDB updates (ConditionExpression on dekVersion) for idempotent re-wrapping
  - Skip items where conditional update fails (already re-wrapped by retry)
  - Upload re-wrapped DEKs to server
  - Update DynamoDB metadata with new KEK version
  - Maintain dual-KEK access during transition:
    - Old KEK for reading files not yet re-wrapped
    - New KEK for all new file uploads during rotation
    - Check DEK version to determine which KEK to use for unwrapping
  - Handle multipart uploads during rotation:
    - Capture current KEK version at upload initiation time
    - On upload completion, verify captured KEK version is still available before wrapping DEK
    - If captured KEK version unavailable (rotation rollback), abort upload and prompt user to retry
  - BLOCK share creation during active rotation (display "Key rotation in progress" message to user)
  - Ensure in-progress downloads complete using the KEK version matching the file's DEK version
  - Update local key storage with new KEK version
  - Release rotation lock in DynamoDB Vaults table (set rotationState = IDLE) on completion or rollback
  - Securely zeroize old KEK from memory after completion (overwrite with zeros then random data)
  - Support pause and resume for large vaults
  - Report progress to UI
  - _Requirements: 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 20.10, 20.16, 20.17, 20.18, 20.19, 20.20, 20.21, 20.22, 30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 33.12, 33.13_

- [ ]* 18.3 Write property test for key rotation preserves data access
  - **Property 26: Automatic key rotation preserves data access**
  - **Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5**

- [ ] 19. Implement optional local content analysis (frontend)
- [ ] 19.1 Integrate on-device ML model
  - Load TensorFlow Lite/Core ML/ONNX model (MobileNet or EfficientNet)
  - Run inference on media before encryption
  - Generate tags from recognition results
  - Ensure no network requests during recognition
  - Privacy-preserving (no data sent to external services)
  - _Requirements: 11.5_

- [ ] 19.2 Encrypt generated tags before transmission
  - Apply deterministic tag encryption to all generated tags
  - Store encrypted tags with media metadata
  - _Requirements: 11.1, 11.2_

- [ ] 20. Implement concurrent upload coordination (frontend)
- [ ] 20.1 Build upload queue and concurrency manager
  - Queue multiple media items for upload
  - Configure concurrent upload limit based on network conditions
  - Handle upload failures with retry logic (exponential backoff)
  - Track upload progress for UI feedback
  - _Requirements: 7.3_

- [ ] 21. Enhance error handling across all components
- [ ] 21.1 Enhance Lambda error handling — **Phase A: partially completed** (structured `ErrorResponse` with `code` + `requestId` + `timestamp` shipped; DynamoDB exponential-backoff retry still pending → kept unchecked)
  - Ensure all error codes are defined (AUTHENTICATION_REQUIRED, AUTHENTICATION_FAILED, etc.)
  - Verify appropriate HTTP status codes for all error types
  - Add request IDs to all error responses
  - Sanitize error messages to prevent information leakage
  - Implement exponential backoff for DynamoDB throttling — _still pending (the only remaining item for 21.1)_
  - _Requirements: 3.5, 4.4, 8.3_

- [ ] 21.2 Add frontend error handling
  - Handle encryption failures (key derivation, encryption operations)
  - Implement network failure retry logic with exponential backoff
  - Handle authentication failures (token expiration, invalid credentials)
  - Handle password validation failures (weak password, breached password)
  - Handle key rotation failures (re-encryption errors, network interruption)
  - _Requirements: 3.5, 21.1, 21.2, 21.3, 21.4_

- [ ]* 21.3 Write property test for API error responses are well-formed
  - **Property 9: API error responses are well-formed**
  - **Validates: Requirements 8.3**

- [ ] 22. Implement monitoring and logging
- [ ] 22.1 Configure CloudWatch metrics and alarms
  - Set up Lambda metrics (invocation count, duration, errors)
  - Set up API Gateway metrics (request count, latency, 4xx/5xx errors)
  - Set up DynamoDB metrics (consumed capacity, throttled requests)
  - Set up S3 metrics (request count, bytes uploaded/downloaded)
  - Create alarms: Lambda error rate >1%, API Gateway 5xx >0.5%, DynamoDB throttling, S3 4xx >5%
  - Enable X-Ray tracing for request analysis
  - _Requirements: 16.5_

- [ ] 22.2 Implement log sanitization
  - Ensure no plaintext data in logs
  - Exclude encrypted payloads from logs
  - Log only user IDs, vault IDs, timestamps, operation types, error codes, performance metrics
  - Never log vault keys, passwords, recovery keys, or share keys
  - Configure CloudWatch log retention
  - Add log sanitization to all Lambda functions
  - _Requirements: 16.5_

- [ ]* 22.3 Write property test for administrator cannot access plaintext data
  - **Property 19: Administrator cannot access plaintext data**
  - **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

- [ ]* 22.4 Write property test for all server-stored data is encrypted
  - **Property 10: All server-stored data is encrypted**
  - **Validates: Requirements 9.2, 9.5, 16.1, 16.2**

- [ ] 23. Set up deployment pipeline
- [ ] 23.1 Configure CDK deployment
  - Define CDK app entry point (bin/app.ts)
  - Configure environment-specific parameters (dev, staging, prod)
  - Set up CDK context in cdk.json
  - Define stack outputs for cross-stack references
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 23.2 Create deployment scripts
  - Create build script for Lambda functions
  - Create CDK synth and deploy scripts
  - Add environment validation
  - Document deployment process
  - _Requirements: 8.4_

- [ ] 23.3 Set up CI/CD pipeline (optional)
  - Automate testing on every commit
  - Deploy to dev environment automatically
  - Require manual approval for staging/production
  - Implement blue-green deployment strategy
  - _Requirements: 8.4_

- [ ] 24. Write integration tests
  - Test complete upload flow (authenticate → get presigned URL → upload to S3 → store metadata with wrapped DEK)
  - Test complete download flow (authenticate → list items → get download URL and wrapped DEK → download from S3 → unwrap DEK → decrypt)
  - Test multi-device flow (setup on device 1 → login on device 2 → access same items)
  - Test collection management (create → add items → retrieve → delete)
  - Test tag search (upload with tags → search → verify results)
  - Test error recovery (simulate S3 failure → verify cleanup)
  - Test two-password flow (change account password → verify vault unchanged → change vault password → verify DEK re-wrapping)
  - Test account recovery (Cognito forgot-password: email code → reset password → verify access)
  - Test vault recovery (use recovery key → reset vault password → verify data accessible)
  - Test file sharing with envelope encryption (create share → access anonymously with password → verify download and decryption)
  - Test password-protected sharing (create protected share → enter password → unwrap DEK → verify access)
  - Test share expiration (create time-limited share → wait → verify access denied)
  - Test share revocation (create share → revoke → verify access denied)
  - Test key rotation with envelope encryption (trigger rotation → verify DEK re-wrapping only → verify data accessible with new KEK)
  - Test password validation (attempt weak password → verify rejection → attempt breached password → verify rejection)
  - Test notification scheduling (create TASK/EVENT with notification → verify encrypted schedule stored → verify notification delivery)
  - Test date bucket privacy (create multiple notifications → verify server only knows 15-min buckets → verify exact times encrypted)
  - Test real-time sync (update item on device 1 → verify device 2 receives update via WebSocket)
  - Test envelope encryption round-trip (generate DEK → encrypt file → wrap DEK → unwrap DEK → decrypt file → verify content)
  - Test legacy file migration (access legacy file → migrate to envelope encryption → verify content preserved)
  - Test DEK uniqueness (upload multiple files → verify each has unique DEK)
  - _Requirements: All_

- [ ] 25. Implement date bucket encryption (frontend)
- [ ] 25.1 Create date bucket encryption functions
  - Create frontend/src/lib/date-bucket.ts
  - Implement function to round notification time to 15-minute bucket
  - Derive date bucket encryption key using HKDF (context: "cortex-date-bucket-encryption-v1")
  - Encrypt exact notification time with ChaCha20-Poly1305
  - Create encrypted notification payload (item ID, notification type, encrypted exact time)
  - Export functions: roundToTimeBucket(), encryptExactTime(), encryptDateBucket()
  - _Requirements: 25.1, 25.3_

- [ ] 25.2 Create date bucket decryption functions
  - Add to frontend/src/lib/date-bucket.ts
  - Decrypt notification payloads received from server
  - Extract exact notification time from encrypted payload
  - Validate notification time matches expected bucket
  - Export functions: decryptExactTime(), decryptNotificationPayload()
  - _Requirements: 25.3_

- [ ]* 25.3 Write property test for date bucket privacy
  - Create frontend/tests/property/test_date_bucket.test.ts
  - **Property 29: Date bucket encryption preserves privacy**
  - **Validates: Requirements 25.1, 25.2, 25.3**

- [ ] 26. Implement notification scheduling system
- [ ] 26.1 Update Smithy model for notifications
  - Add notification schedule structures to smithy/models/
  - Define operations for creating, listing, and canceling notification schedules
  - Add timeBucket field to item structures for tasks/events
  - Add date bucket query parameters to list/search operations
  - _Requirements: 25.1, 25.2, 25.3, 26.1_

- [ ] 26.2 Update CDK to add Notification Schedules table and EventBridge
  - Create Notification Schedules DynamoDB table (PK: VAULT#{vaultId}, SK: SCHEDULE#{timeBucket}#{scheduleId})
  - Add GSI for global notification processing (PK: STATUS#{status}, SK: TIMEBUCKET#{timeBucket}) where status is one of: PENDING, SENT, CANCELLED, DEAD_LETTER, RETRY_1, RETRY_2, RETRY_3
  - Configure EventBridge rule to trigger Lambda every 5 minutes
  - Create SNS topic for push notifications
  - Grant Lambda permissions for SNS publish
  - _Requirements: 26.1, 26.2, 26.3, 26.4_

- [ ] 26.3 Create notification scheduling route handlers (server-side)
  - Create lambda/src/api/routes/notifications.py
  - Implement POST /v1/notifications/schedules route (store encrypted notification)
  - Implement DELETE /v1/notifications/schedules/{id} route (cancel notification)
  - Implement GET /v1/notifications/schedules route (list pending schedules)
  - Extract user identity from API Gateway context
  - _Requirements: 26.1, 26.2, 26.3_

- [ ] 26.4 Create notification scheduling service layer (server-side)
  - Create lambda/src/api/services/notification_service.py
  - Store encrypted notification payload in Notification Schedules table
  - Index by date bucket (PK: VAULT#{vaultId}, SK: SCHEDULE#{timeBucket}#{scheduleId})
  - Query notifications by date bucket for polling
  - Delete notification schedules after delivery
  - Never decrypt notification payloads
  - _Requirements: 26.1, 26.2, 26.3_

- [ ] 26.5 Create notification processing Lambda handler with failure handling
  - Create lambda/src/notification_processor/handler.py
  - Triggered by EventBridge every 5 minutes
  - Query schedules with timeBucket <= now + 15min
  - Send push notifications via SNS with encrypted payloads
  - Mark schedules as SENT after delivery
  - Classify failures as transient (network errors, throttling) vs permanent (EndpointDisabled, InvalidParameter, expired tokens)
  - Retry transient failures up to 3 times with exponential backoff (5 minutes, 15 minutes, 45 minutes)
  - For permanent failures (EndpointDisabled, InvalidParameter), mark device token as invalid and do NOT retry
  - After 3 failed retries, move notification to DEAD_LETTER status with failure reason and last attempt timestamp
  - On next app access, React frontend queries for dead-letter notifications and displays summary to user
  - _Requirements: 26.3, 26.4, 26.6, 26.7, 26.8, 26.9_

- [ ] 26.6 Create recurring event notification scheduling (frontend)
  - When user creates a recurring task/event with a reminder, expand recurrence rule into individual notification schedules
  - Lazy expansion strategy: generate individual schedules for the next 90 days
  - When current date is within 7 days of the end of the pre-generated window, generate the next batch (extending another 90 days)
  - When a recurring event is modified, cancel all future notification schedules (status = CANCELLED) and regenerate based on updated recurrence rule
  - When a recurring event is deleted, cancel all associated future notification schedules
  - Each expanded schedule is a standard entry in the Notification Schedules table with its own encrypted payload and time bucket
  - _Requirements: 26.10, 26.11, 26.12_

- [ ] 26.7 Create notification polling system (frontend)
  - Create frontend/src/lib/notifications.ts
  - Poll server every 15 minutes for current date bucket
  - Decrypt notification payloads locally
  - Check if exact notification time has passed
  - Display local notifications for due items
  - Mark notifications as delivered
  - _Requirements: 26.3, 26.4_

- [ ] 26.8 Integrate SNS for push notifications (optional)
  - Configure SNS topics for notification delivery
  - Subscribe client devices to SNS topics
  - Send encrypted notification payloads via SNS
  - Client decrypts and displays notifications
  - _Requirements: 26.4_

- [ ]* 26.9 Write property test for notification encryption
  - Create lambda/tests/property/test_notifications.py
  - **Property 30: Notification metadata is encrypted**
  - **Validates: Requirements 26.1, 26.2**

- [ ]* 26.10 Write property test for server cannot determine exact notification times
  - Add to lambda/tests/property/test_notifications.py
  - **Property 31: Server cannot determine exact notification times**
  - **Validates: Requirements 25.2, 26.2**

- [ ] 27. Implement real-time sync (optional)
- [ ] 27.1 Update Smithy model for WebSocket API
  - Add WebSocket connection structures to smithy/models/
  - Define sync notification message formats
  - _Requirements: 27.1, 27.2_

- [ ] 27.2 Update CDK to add WebSocket API and Connections table
  - Create WebSocket API Gateway
  - Create WebSocket Connections DynamoDB table (PK: CONNECTION#{connectionId}, SK: METADATA)
  - Add GSI for vault-based queries (PK: VAULT#{vaultId}, SK: CONNECTION#{connectionId})
  - Grant Lambda permissions for API Gateway Management API
  - _Requirements: 27.1, 27.2_

- [ ] 27.3 Create WebSocket API for real-time sync with connection limits
  - Create lambda/src/websocket/handler.py
  - Implement connection management (connect, disconnect)
  - Store connection IDs in DynamoDB
  - Associate connections with user IDs and vault IDs
  - Handle ping/pong for keep-alive
  - Enforce maximum 10 concurrent WebSocket connections per vault
  - On new connection, query Connections table GSI for vault's active connections
  - If count reaches 10, gracefully terminate oldest connection (by connectedAt) with close frame indicating reason
  - Log excessive connection attempts (>20 per hour per vault) for security monitoring
  - _Requirements: 27.1, 27.2, 27.6, 27.7, 27.8_

- [ ] 27.4 Create sync notification system
  - Update item route handlers to trigger sync notifications
  - Send encrypted item metadata to connected clients
  - Broadcast to all user's connected devices
  - Never send unencrypted data over WebSocket
  - _Requirements: 27.1, 27.2, 27.3_

- [ ] 27.5 Create frontend sync handler
  - Create frontend/src/lib/sync.ts
  - Establish WebSocket connection on app startup
  - Listen for sync notifications
  - Decrypt received item metadata
  - Update local cache with new data
  - Trigger UI refresh
  - _Requirements: 27.1, 27.2, 27.3_

- [ ]* 27.6 Write property test for real-time sync preserves encryption
  - Create lambda/tests/property/test_sync.py
  - **Property 32: Real-time sync preserves encryption**
  - **Validates: Requirements 27.2, 27.3**

- [ ] 28. Final checkpoint - Ensure all tests pass
  - Run all unit tests and verify they pass
  - Run all property-based tests and verify they pass
  - Run all integration tests and verify they pass
  - Fix any failing tests
  - Ensure all tests pass, ask the user if questions arise.