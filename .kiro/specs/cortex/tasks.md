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
  - Create DynamoDB tables for Items, Collections, Vaults, Recovery codes, Shares
  - Configure on-demand billing with point-in-time recovery
  - _Requirements: 1.3, 2.5, 6.5, 7.4, 7.5, 11.3, 12.2, 17.3, 19.1, 22.1, 22.2_

- [x] 3.2 Create authentication stack (Cognito configuration)
  - Set up Cognito user pool with email/password authentication
  - Configure password policy (12 chars min, complexity requirements)
  - Set up custom authentication flow for recovery codes
  - Configure identity pool for federated identities
  - Set up IAM roles for authenticated users
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
  - Derive data encryption key (context: "cortex-data-encryption-v1")
  - Derive metadata encryption key (context: "cortex-metadata-encryption-v1")
  - Derive share key derivation key (context: "cortex-share-key-derivation-v1")
  - Derive notes encryption key (context: "cortex-notes-encryption-v1")
  - Derive tasks encryption key (context: "cortex-tasks-encryption-v1")
  - Derive events encryption key (context: "cortex-events-encryption-v1")
  - Derive notification encryption key (context: "cortex-notification-encryption-v1")
  - Derive date bucket encryption key (context: "cortex-date-bucket-encryption-v1")
  - Export function: deriveKeys(vaultMasterKey)
  - _Requirements: 14.2, 24.3, 25.1, 26.1_

- [x] 6.3 Implement vault recovery key generation and validation
  - Add recovery key functions to packages/encryption/src/lib/key-management.ts
  - Generate BIP39 mnemonic from vault master key using bip39 library
  - Display recovery key to user once with secure storage instructions
  - Implement recovery key validation for vault password reset
  - Re-derive vault master key from recovery key
  - Export functions: generateRecoveryKey(), validateRecoveryKey()
  - _Requirements: 15.1, 15.2, 15.3_

- [x] 6.4 Build local key storage with device-specific encryption
  - Create packages/encryption/src/lib/key-storage.ts
  - Encrypt derived keys with device-specific key
  - Store encrypted keys in browser localStorage or secure storage
  - Implement key retrieval and decryption on device
  - Never transmit keys to server
  - Export functions: storeKeys(), retrieveKeys(), clearKeys()
  - _Requirements: 14.3, 14.6_

- [x] 6.5 Implement password validation with strength and breach checking
  - Create packages/encryption/src/lib/password-validation.ts
  - Validate minimum 12 characters and complexity requirements
  - Integrate with Have I Been Pwned API using k-anonymity model
  - Client-side SHA-1 hash, send first 5 characters to API
  - Check full hash against returned list locally
  - Reject breached passwords
  - Apply to both account and vault passwords
  - Export function: validatePassword(password)
  - _Requirements: 21.1, 21.2, 21.3, 21.4_

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

- [ ] 7. Build React web application (@cortex/web)
- [ ] 7.1 Set up React web app with Vite
  - Create packages/web/src directory structure
  - Configure Vite build tooling
  - Import @cortex/encryption for all cryptographic operations
  - Set up TypeScript configuration with reference to encryption package
  - _Requirements: 1.1, 2.1, 9.1_

- [ ] 7.2 Create React components for authentication
  - Build Login component (account password authentication)
  - Build Signup component (account + vault password setup)
  - Build VaultUnlock component (vault password entry for key derivation)
  - Use @cortex/encryption for password validation and key derivation
  - _Requirements: 3.1, 3.2, 14.1, 14.2, 21.1, 21.2_

- [ ] 7.3 Create React components for file management
  - Build FileUpload component (encrypt and upload files)
  - Build FileList component (list and decrypt metadata)
  - Build FileDownload component (download and decrypt files)
  - Use @cortex/encryption for all encryption/decryption operations
  - _Requirements: 1.1, 1.4, 2.1, 2.3, 4.1, 4.2_

- [ ] 7.4 Create React components for collections and tags
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

- [x] 9. Implement authentication routes and services
- [x] 9.1 Create authentication route handlers
  - Implement POST /v1/auth/login route
  - Implement POST /v1/auth/refresh route
  - Implement POST /v1/auth/recover route
  - Extract user identity from API Gateway context
  - _Requirements: 3.1, 3.2, 19.2_

- [x] 9.2 Create authentication service layer
  - Implement user registration logic
  - Implement login validation
  - Handle token refresh
  - Implement custom authentication flow for recovery codes
  - _Requirements: 3.1, 3.2_

- [x] 9.3 Implement account recovery code system
  - Generate 10 recovery codes at signup (16 chars, format: XXXX-XXXX-XXXX-XXXX)
  - Hash codes with SHA-256 before storage in DynamoDB
  - Store in Account Recovery table
  - Validate recovery codes during account recovery
  - Invalidate used codes (mark as used, set usedAt timestamp)
  - _Requirements: 19.1, 19.2, 19.3, 19.5_

- [x] 9.4 Write property test for account recovery code validation
  - **Property 25: Account recovery code validation**
  - **Validates: Requirements 19.2, 19.3**

- [x] 10. Implement vault management routes and services
- [x] 10.1 Create vault route handlers
  - Implement POST /v1/vaults route (create vault with salt)
  - Implement GET /v1/vaults/{id}/salt route (retrieve salt for key derivation)
  - _Requirements: 14.4, 22.1, 22.2, 22.3_

- [x] 10.2 Create vault service layer
  - Generate unique vault salt using cryptographically secure RNG (16 bytes)
  - Store vault salt in DynamoDB Vaults table
  - Retrieve vault salt for key derivation on new devices
  - Ensure vault salt uniqueness across all vaults
  - _Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5_

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
  - For NOTE/TASK/EVENT items: Store encrypted content directly in DynamoDB
  - Return upload URL with 15-minute expiration (MEDIA only)
  - Store encrypted metadata in DynamoDB with user isolation
  - Link items to user account using userId from Cognito token
  - Handle encrypted tags storage
  - Store item type in DynamoDB
  - _Requirements: 1.2, 1.4, 1.5, 2.1, 2.2, 2.4, 4.5, 7.1, 7.2, 7.4, 11.3, 24.1, 24.2, 24.3_

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
  - Return time-limited download URL (15 minutes)
  - Return authorization errors for unauthorized access
  - _Requirements: 4.1, 4.3, 4.4, 24.2_

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

- [ ] 14. Implement collection management routes and services
- [ ] 14.1 Create collection CRUD route handlers
  - Implement POST /v1/collections route (create)
  - Implement GET /v1/collections route (list)
  - Implement GET /v1/collections/{id} route (get details)
  - Implement PUT /v1/collections/{id} route (update)
  - Implement DELETE /v1/collections/{id} route (delete)
  - _Requirements: 12.1, 12.2, 13.1, 13.3, 13.4, 13.5_

- [ ] 14.2 Create collection service layer
  - Create collection with encrypted metadata
  - List user's collections with item counts
  - Update collection metadata
  - Delete collection while preserving items
  - Enforce user isolation for all operations
  - _Requirements: 12.1, 12.2, 13.1, 13.3, 13.4, 13.5_

- [ ] 14.3 Create item-collection association route handlers
  - Implement POST /v1/collections/{id}/items route (add items)
  - Implement DELETE /v1/collections/{id}/items/{itemId} route (remove items)
  - Support all item types (MEDIA, NOTE, TASK, EVENT)
  - _Requirements: 12.3, 12.5, 13.2_

- [ ] 14.4 Create item-collection association service layer
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

- [ ] 15. Implement tag search routes and services
- [ ] 15.1 Create tag search route handler
  - Implement GET /v1/tags/search route
  - Extract encrypted search term from query parameters
  - Extract user identity from context
  - _Requirements: 11.4, 11.5_

- [ ] 15.2 Create tag search service layer
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

- [ ] 16.2 Create vault password change functionality (frontend)
  - Derive new vault master key from new vault password
  - Trigger background re-encryption of all vault data
  - Re-encrypt files in batches
  - Update local key storage with new keys
  - Maintain dual-key access during transition
  - _Requirements: 23.3, 23.4, 23.5_

- [ ]* 16.3 Write property test for account password change independence
  - **Property 21: Account password change does not affect vault encryption**
  - **Validates: Requirements 23.1**

- [ ]* 16.4 Write property test for vault password change re-encryption
  - **Property 22: Vault password change requires data re-encryption**
  - **Validates: Requirements 23.3, 23.4**

- [ ] 17. Implement file sharing system
- [ ] 17.1 Build frontend share key generation and URL creation
  - Generate unique share keys using HKDF from share key derivation key + file ID
  - Create share URLs with share ID and base64-encoded share key in fragment
  - Implement password-protected shares with double encryption
  - Password-derived key encrypts share key before embedding in URL
  - _Requirements: 17.1, 17.2, 18.3, 18.4_

- [ ] 17.2 Create share route handlers
  - Implement POST /v1/shares route (create share)
  - Implement GET /v1/shares/{id} route (access share, anonymous)
  - Implement DELETE /v1/shares/{id} route (revoke share)
  - _Requirements: 17.3, 17.4, 17.5, 18.2, 18.5_

- [ ] 17.3 Create share service layer
  - Store share metadata (expiration, password protection flag, revocation status)
  - Validate share access (check expiration and revocation)
  - Allow anonymous access to shared files
  - Generate presigned S3 URLs for shared file downloads
  - Track access count and last accessed time
  - Never store share keys (embedded in URLs)
  - _Requirements: 17.3, 17.4, 17.5, 18.2, 18.5_

- [ ]* 17.4 Write property test for share keys enable file access without vault password
  - **Property 20: Share keys enable file access without vault password**
  - **Validates: Requirements 17.1, 17.4**

- [ ] 18. Implement automatic key rotation (frontend)
- [ ] 18.1 Build key rotation trigger and monitoring
  - Monitor key age (90 days since last rotation)
  - Trigger automatic rotation
  - Support manual rotation via user settings
  - _Requirements: 20.1_

- [ ] 18.2 Implement background re-encryption process
  - Generate new derived keys with updated HKDF context (increment version)
  - Create re-encryption queue for all vault files
  - Re-encrypt files in batches (configurable batch size)
  - Upload re-encrypted files to S3 with new keys
  - Update DynamoDB metadata with new key version
  - Maintain dual-key access during transition (old keys for reading, new keys for writing)
  - Delete old encrypted versions after successful re-encryption
  - Update local key storage with new key version
  - _Requirements: 20.2, 20.3, 20.4, 20.5_

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
- [ ] 21.1 Enhance Lambda error handling
  - Ensure all error codes are defined (AUTHENTICATION_REQUIRED, AUTHENTICATION_FAILED, etc.)
  - Verify appropriate HTTP status codes for all error types
  - Add request IDs to all error responses
  - Sanitize error messages to prevent information leakage
  - Implement exponential backoff for DynamoDB throttling
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
  - Never log vault keys, passwords, recovery keys, share keys, or account recovery codes
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
  - Test complete upload flow (authenticate → get presigned URL → upload to S3 → store metadata)
  - Test complete download flow (authenticate → list items → get download URL → download from S3)
  - Test multi-device flow (setup on device 1 → login on device 2 → access same items)
  - Test collection management (create → add items → retrieve → delete)
  - Test tag search (upload with tags → search → verify results)
  - Test error recovery (simulate S3 failure → verify cleanup)
  - Test two-password flow (change account password → verify vault unchanged → change vault password → verify re-encryption)
  - Test account recovery (use recovery code → reset password → verify access)
  - Test vault recovery (use recovery key → reset vault password → verify data accessible)
  - Test file sharing (create share → access anonymously → verify download)
  - Test password-protected sharing (create protected share → enter password → verify access)
  - Test share expiration (create time-limited share → wait → verify access denied)
  - Test share revocation (create share → revoke → verify access denied)
  - Test key rotation (trigger rotation → verify re-encryption → verify data accessible)
  - Test password validation (attempt weak password → verify rejection → attempt breached password → verify rejection)
  - Test notification scheduling (create TASK/EVENT with notification → verify encrypted schedule stored → verify notification delivery)
  - Test date bucket privacy (create multiple notifications → verify server only knows 15-min buckets → verify exact times encrypted)
  - Test real-time sync (update item on device 1 → verify device 2 receives update via WebSocket)
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
  - Add GSI for global notification processing (PK: STATUS#{status}, SK: TIMEBUCKET#{timeBucket})
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

- [ ] 26.5 Create notification processing Lambda handler
  - Create lambda/src/notification_processor/handler.py
  - Triggered by EventBridge every 5 minutes
  - Query schedules with timeBucket <= now + 15min
  - Send push notifications via SNS with encrypted payloads
  - Mark schedules as SENT after delivery
  - Handle retry logic for failed notifications
  - _Requirements: 26.3, 26.4_

- [ ] 26.6 Create notification polling system (frontend)
  - Create frontend/src/lib/notifications.ts
  - Poll server every 15 minutes for current date bucket
  - Decrypt notification payloads locally
  - Check if exact notification time has passed
  - Display local notifications for due items
  - Mark notifications as delivered
  - _Requirements: 26.3, 26.4_

- [ ] 25.7 Integrate SNS for push notifications (optional)
  - Configure SNS topics for notification delivery
  - Subscribe client devices to SNS topics
  - Send encrypted notification payloads via SNS
  - Client decrypts and displays notifications
  - _Requirements: 26.4_

- [ ]* 26.8 Write property test for notification encryption
  - Create lambda/tests/property/test_notifications.py
  - **Property 30: Notification metadata is encrypted**
  - **Validates: Requirements 26.1, 26.2**

- [ ]* 26.9 Write property test for server cannot determine exact notification times
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

- [ ] 27.3 Create WebSocket API for real-time sync
  - Create lambda/src/websocket/handler.py
  - Implement connection management (connect, disconnect)
  - Store connection IDs in DynamoDB
  - Associate connections with user IDs and vault IDs
  - Handle ping/pong for keep-alive
  - _Requirements: 27.1, 27.2_

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