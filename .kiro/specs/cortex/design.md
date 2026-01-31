# Cortex Productivity Suite - Design Document

## Overview

Cortex is a zero-knowledge cloud-based productivity suite built on AWS serverless infrastructure. The system implements end-to-end encryption where all sensitive data (media files, notes, tasks, events, metadata, tags, collections, and organizational structure) is encrypted client-side before transmission. The server operates exclusively on encrypted data, ensuring that neither service administrators nor the infrastructure provider can access user content.

The productivity suite includes:
- **Media Storage**: Secure backup and storage for photos, videos, and files
- **Notes**: Rich text documents with optional attachments
- **Tasks**: To-do items with due dates, priorities, and reminders
- **Events**: Calendar entries with start/end times, locations, and recurrence
- **Collections**: User-defined groupings for organizing items
- **Tags**: Searchable labels for categorization
- **Push Notifications**: Encrypted reminders for tasks and events
- **Real-Time Sync**: Cross-device synchronization via WebSocket

The architecture implements a two-password model: an **account password** for authentication with AWS Cognito, and a separate **vault password** for encrypting/decrypting the vault's master key and all data. This separation allows users to change their account password without re-encrypting all vault data, and provides a more flexible security model.

The architecture follows AWS best practices using Lambda for compute, API Gateway for API management, DynamoDB for metadata storage, S3 for object storage, Cognito for authentication, SNS for push notifications, and EventBridge for scheduled tasks. The Smithy model defines the service contract, enabling type-safe API definitions and automatic SDK generation.

### Terminology

Throughout this document:
- **Item** refers to any data object stored in a vault, regardless of type (media, note, task, or event).
- **File** and **media** refer specifically to binary content stored in S3, applicable only to media items.
- **File content** refers to the binary data stored in S3 (media items only). **Inline content** refers to encrypted content stored directly in DynamoDB (notes, tasks, and events).
- When a section discusses DEKs and envelope encryption, it applies to media items (which have file content in S3). Notes, tasks, and events use inline content encryption with their respective derived keys.

### Key Design Principles

1. **True Zero-Knowledge Architecture**: Server never has access to plaintext data, encryption keys, or encrypted key bundles
2. **Two-Password Model**: Separate account password (authentication) and vault password (data encryption)
3. **Client-Side Encryption**: All encryption/decryption happens in the React frontend using ChaCha20-Poly1305
4. **Direct S3 Access**: Presigned URLs enable fast uploads/downloads bypassing Lambda
5. **Serverless Scalability**: Auto-scaling infrastructure with pay-per-use pricing
6. **Multi-Device Support**: Vault password + server-stored salt enables key derivation on any device
7. **Privacy-Preserving Search**: Encrypted tags and collections enable organization without exposing content
8. **No Server-Side Key Storage**: Vault keys are derived on-demand and stored only locally on devices

## Architecture

### Two-Password Security Model

Cortex implements a dual-password architecture that separates authentication from encryption:

**Account Password:**
- Used for authentication with AWS Cognito
- Grants access to the user's account and vault metadata
- Can be changed without re-encrypting vault data
- Managed by AWS Cognito with standard password policies
- Supports account recovery via recovery codes

**Vault Password:**
- Used exclusively for deriving vault encryption keys
- Never transmitted to or stored by the server
- Combined with server-stored vault salt to derive vault master key using Argon2id
- Changing vault password requires re-encrypting all vault data
- Supports vault recovery via recovery key (derived from vault master key)

**Key Derivation Flow:**
```
Vault Password + Vault Salt → [Argon2id] → Vault Master Key (256-bit)
                                                    ↓
                                                 [HKDF]
                                                    ↓
        ┌───────────────────────────┼───────────────────────────┬──────────────────────────┐
        ↓                           ↓                           ↓                          ↓
  Key Encryption Key     Metadata Encryption Key    Share Key Derivation Key    Notes/Tasks/Events/
  (KEK - wraps DEKs)     (common metadata)          (file sharing)              Notification Keys
        │
        │ Wraps/Unwraps
        ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │                              PER-FILE DEKs (Data Encryption Keys)                        │
  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
  │  │   DEK #1    │    │   DEK #2    │    │   DEK #3    │    │   DEK #N    │              │
  │  │ (File 1)    │    │ (File 2)    │    │ (File 3)    │    │ (File N)    │              │
  │  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │
  │         │                  │                  │                  │                     │
  │         ▼                  ▼                  ▼                  ▼                     │
  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
  │  │ Encrypted   │    │ Encrypted   │    │ Encrypted   │    │ Encrypted   │              │
  │  │  File #1    │    │  File #2    │    │  File #3    │    │  File #N    │              │
  │  │   (S3)      │    │   (S3)      │    │   (S3)      │    │   (S3)      │              │
  │  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘              │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Envelope Encryption Benefits:**
- **Efficient Key Rotation**: Only re-wrap DEKs (small key blobs), not re-encrypt entire files
- **Fast File Sharing**: Create share-wrapped DEK without re-uploading file content
- **Per-File Key Isolation**: Compromise of one DEK doesn't affect other files
- **Bandwidth Efficient**: Key rotation downloads only wrapped DEKs, not file content

This separation provides:
- Flexibility to change account credentials without expensive re-encryption
- True zero-knowledge architecture (server never sees vault password or keys)
- Multi-device support (vault password + salt enables key derivation on any device)
- Independent recovery mechanisms for account access vs. data access

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Browser)                  │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Encryption     │  │ Content      │  │ Key Management  │ │
│  │ Engine         │  │ Analysis     │  │ (Argon2id/HKDF) │ │
│  │ (ChaCha20)     │  │ (Optional)   │  │                 │ │
│  └────────────────┘  └──────────────┘  └─────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              React Components & UI                     │ │
│  │  (Upload, Download, Collections, Tags, Notifications)  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (SigV4) / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AWS Cognito (OIDC)                      │
│                   Authentication & Identity                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Scoped Credentials
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AWS API Gateway                         │
│              (REST + WebSocket, Smithy Defined)              │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Lambda   │  │ Lambda   │  │ Lambda   │
        │ Items    │  │ Notif.   │  │ Sync     │
        └──────────┘  └──────────┘  └──────────┘
                │             │             │
                ▼             ▼             ▼
        ┌──────────────────────────────────────┐
        │           DynamoDB                   │
        │  Items | Notifications | Collections │
        │  Connections | Vaults | Users        │
        └──────────────────────────────────────┘
                │
                ▼
        ┌──────────────────────────┐
        │         S3 Bucket        │
        │  (Encrypted Media Files) │
        │  (Server-Side Encryption)│
        └──────────────────────────┘
                
        ┌──────────────────────────┐
        │      AWS SNS (Push)      │
        │   Notification Delivery  │
        └──────────────────────────┘
                ▲
                │
        ┌──────────────────────────┐
        │   EventBridge (Cron)     │
        │   Every 5 minutes        │
        └──────────────────────────┘
```

### Component Interaction Flow

**Item Creation Flow (Generic):**
1. React frontend encrypts item content and metadata locally using appropriate encryption key
2. React frontend requests API endpoint (authenticated via SigV4)
3. For media items: 
   - React frontend generates unique DEK for the file
   - React frontend encrypts file content with DEK
   - React frontend wraps DEK with vault's KEK
   - Lambda generates presigned S3 URL
   - React frontend uploads encrypted content directly to S3
   - React frontend sends wrapped DEK and encrypted metadata to Lambda
4. For other items: Content stored inline in DynamoDB as encrypted blob
5. React frontend sends encrypted metadata to Lambda
6. Lambda stores encrypted metadata (and wrapped DEK for media) in Items table

**Item Retrieval Flow:**
1. React frontend requests item list from API Gateway
2. Lambda queries DynamoDB Items table for user's encrypted metadata
3. React frontend decrypts metadata locally in browser
4. For media items: 
   - React frontend requests download URL
   - Lambda returns presigned S3 URL and wrapped DEK
   - React frontend downloads encrypted content from S3
   - React frontend unwraps DEK using vault's KEK
   - React frontend decrypts content using unwrapped DEK
   - React frontend clears DEK from memory after decryption

**Notification Flow:**
1. React frontend creates task/event with reminder time
2. React frontend encrypts notification payload and exact time
3. React frontend generates time bucket (15-min window, plaintext)
4. React frontend sends notification schedule to Lambda
5. Lambda stores in Notification Schedules table
6. EventBridge triggers Lambda every 5 minutes
7. Lambda queries schedules with timeBucket <= now + 15min
8. Lambda sends push notifications via SNS with encrypted payloads
9. React frontend receives notification, decrypts payload, displays to user

**Multi-Device Flow:**
1. New device: User enters account password (authenticates with Cognito)
2. User enters vault password in React frontend
3. React frontend retrieves vault salt from DynamoDB
4. React frontend derives vault master key from vault password + salt using Argon2id
5. React frontend derives HMAC key from vault master key using HKDF with salt and context "cortex-salt-hmac-v1"
6. React frontend computes HMAC-SHA256 over vault salt using HMAC key
7. On first access, React frontend stores vault salt HMAC locally for integrity verification
8. On subsequent accesses, React frontend verifies vault salt HMAC using constant-time comparison
9. If HMAC verification fails, React frontend displays security warning and refuses to proceed with key derivation
10. If HMAC verification fails, React frontend provides "reset salt HMAC" option requiring re-authentication with both account password and vault password
11. When user initiates salt HMAC reset, React frontend re-computes HMAC using newly authenticated vault password and updates locally stored HMAC
12. React frontend derives KEK, metadata encryption key, and other derived keys from vault master key using HKDF
13. React frontend stores derived keys encrypted locally in browser storage
14. React frontend can now decrypt all user's files and metadata

**Vault Recovery Key Flow (Server-Assisted with Offline Fallback):**

The recovery key encodes the vault master key. KEK version is fetched from the server for efficiency. If the server is unavailable, the client can brute-force the KEK version by trying successive versions (v1, v2, ...) until successful decryption.

1. Initial setup: React frontend generates vault recovery key (BIP39 24-word mnemonic) derived from vault master key
2. React frontend displays recovery key to user once with instructions to store securely offline
3. Server stores current KEK version number as non-secret metadata in DynamoDB Vaults table
4. User confirms they have saved the recovery key before proceeding
5. Vault password forgotten: User initiates recovery process
6. User enters vault recovery key in React frontend
7. React frontend uses recovery key to re-derive the vault master key
8. React frontend fetches current KEK version from DynamoDB Vaults table (if server available)
9. React frontend derives appropriate versioned KEK from recovered vault master key using HKDF with correct version context
10. If vault has undergone key rotation since recovery key creation, React frontend derives latest KEK version to access re-wrapped files
11. If server is unavailable, React frontend attempts incremental KEK version derivation (v1, v2, v3...) until decryption of a known item succeeds, enabling degraded offline recovery
12. Upon successful validation, user sets new vault password while maintaining same vault master key (no re-encryption needed)
13. Server never receives or stores the vault recovery key itself (only KEK version number stored as metadata)

## Components and Interfaces

### 1. Frontend (Monorepo Architecture)

**Monorepo Structure:**
- npm workspaces for package management
- `@cortex/encryption` - Standalone encryption library (reusable across platforms)
- `@cortex/web` - React web application (imports encryption library)

**@cortex/encryption Library Responsibilities:**
- Provide pure TypeScript encryption/decryption functions
- Implement ChaCha20-Poly1305 authenticated encryption
- Implement Argon2id key derivation and HKDF key expansion
- Generate cryptographically secure random nonces
- Provide password validation and breach checking utilities
- Support share key derivation
- No React dependencies - pure crypto library
- Reusable across web, mobile (React Native), and desktop (Electron) platforms

**@cortex/web Application Responsibilities:**
- Import and use `@cortex/encryption` for all cryptographic operations
- Generate and manage vault encryption keys locally in browser
- Encrypt/decrypt all user data before transmission/after receipt
- Perform optional local content analysis for tagging
- Derive vault master key from vault password + vault salt using Argon2id
- Derive data and metadata encryption keys from vault master key using HKDF
- Store derived keys encrypted locally in browser storage only
- Coordinate concurrent uploads for improved throughput (configurable based on network conditions)
- Never transmit vault keys or vault password to server
- Manage account password separately from vault password
- Validate passwords against breach databases and enforce strength requirements
- Handle automatic vault key rotation every 90 days

**Key Modules (@cortex/encryption):**

**Encryption Engine:**
- Algorithm: ChaCha20-Poly1305 for symmetric encryption (fast, secure, authenticated)
- Key derivation: Argon2id for vault password-to-key derivation (64MB memory, 3 iterations, 4 parallelism)
- HKDF for deriving multiple keys from vault master key
- Random nonce generation for each encryption operation
- Authenticated encryption to prevent tampering
- **Key Commitment**: ChaCha20-Poly1305 does not provide key commitment (attacker could potentially find two DEKs decrypting to valid plaintexts)
- **Key Commitment Risk Assessment**: Low risk in Cortex because attacker needs to replace both ciphertext AND wrapped DEK
- **Optional Key Binding**: For additional security, compute HMAC(DEK, file_id) and store with wrapped DEK to bind DEK to specific file and prevent key substitution attacks
- **Error Handling**: Distinguish between failure types when unwrapping DEKs:
  - CORRUPTED_DEK: Authentication tag verification failed or malformed structure (data corruption)
  - WRONG_KEK_VERSION: KEK version mismatch during rotation (user should wait and retry)
  - AUTHENTICATION_FAILED: Generic decryption failure (could be wrong KEK or corruption)
- **Corrupted DEK Handling**: Allow user to mark file as corrupted, delete it, or report issue for investigation
- **KEK Version Mismatch Handling**: Inform user that key rotation is in progress and to retry in a few minutes

**Key Management:**
- **Two-Password Architecture**: Separate account password (for AWS Cognito authentication) and vault password (for data encryption)
- **Vault Master Key Derivation**: Argon2id(vault_password, vault_salt) → 256-bit vault master key
- **Envelope Encryption**: Each media file encrypted with unique DEK, DEK wrapped with KEK
- **Derived Key Generation**: HKDF used to derive multiple keys from vault master key:
  - Key Encryption Key (KEK) - for wrapping/unwrapping per-file DEKs
  - Metadata encryption key (for metadata, tags, collections encryption)
  - Share key derivation key (for generating file share keys)
  - Notes encryption key (for note content encryption)
  - Tasks encryption key (for task content encryption)
  - Events encryption key (for event content encryption)
  - Notification encryption key (for notification payload encryption)
  - Date bucket key (for deterministic date bucket encryption via HMAC)
- **Per-File DEK Generation**: Each media file gets a unique 256-bit DEK generated using CSPRNG
- **DEK Wrapping**: DEKs wrapped with KEK using ChaCha20-Poly1305 before storage
- **Local Key Storage**: Derived keys encrypted with browser-specific key and stored in browser storage only (never transmitted to server)
- **Vault Recovery Key**: Generated from vault master key, displayed once to user with secure offline storage guidance
- **Recovery Key Validation**: Enables vault password reset without re-encrypting data
- **Account Password Management**: Handled separately via AWS Cognito, can be changed without affecting vault encryption
- **Password Validation**: Enforces minimum 12 characters, complexity requirements (uppercase, lowercase, numbers, special characters), and breach database checking
- **Key Rotation**: Automatic vault key rotation every 90 days - only re-wraps DEKs, does not re-encrypt file content

**Content Analysis (Optional):**
- Local ML model for image/video analysis (e.g., TensorFlow.js for browser)
- Offline tag generation (no network requests during analysis)
- Privacy-preserving (no data sent to external services or cloud APIs)
- Model runs entirely in browser before encryption
- Generated tags are encrypted before any transmission
- Recommended models: MobileNet, EfficientNet (optimized for browser inference)
- Supports any file type, but analysis is optional and file-type specific

**Sharing Module:**
- All shares require a password (no passwordless sharing)
- Generate unique random share salt (16 bytes) per share using CSPRNG
- Derive share encryption key from password + share salt using Argon2id
- Derive share HMAC key using HKDF with share encryption key, share salt, and context "cortex-share-hmac-v1" (ensures unique HMAC keys per share even with password reuse)
- Unwrap file's DEK using vault's KEK
- Wrap DEK with password-derived share encryption key
- Generate timestamp nonce representing share creation time
- Compute HMAC-SHA256 over share metadata (shareId, expiration, timestamp nonce) using share HMAC key to prevent tampering and replay attacks
- Embed password-wrapped DEK, share salt, HMAC, and timestamp nonce in share URL fragment (not stored on server)
- Server stores only share metadata (expiration, access count) - no keys, no HMAC
- When accessing share: extract salt, HMAC, and nonce from URL, derive HMAC key, verify HMAC using constant-time comparison
- Server validates timestamp nonce is within expiration window to prevent replay attacks
- Handle time-limited expiration for shares
- Enable share revocation by server blocking access
- File content never re-uploaded for sharing (same S3 object used)
- Validate share password entropy using zxcvbn (minimum 80 bits estimated entropy)
- Client-side exponential backoff after 3 failed attempts (UX improvement, not security)

**Key Rotation Module:**
- Monitor key age and trigger rotation after 90 days
- Maintain rotation state machine: NOT_STARTED, IN_PROGRESS, PAUSED, COMPLETED, FAILED
- Generate new KEK from vault master key using updated HKDF context with incremented version
- Store rotation progress in IndexedDB: vault ID, old KEK version, new KEK version, last processed item cursor (sort key)
- Resume from checkpoint on browser crash or network failure by validating both KEKs accessible
- Provide rollback option for unrecoverable errors to mark rotation as failed and continue with old KEK
- Auto-pause rotation if not completed within 7 days and prompt user to resume or rollback
- Download only wrapped DEKs from server (not file content)
- Process DEKs in configurable batches (recommended 100-500 per batch)
- Monitor browser heap memory usage and auto-pause if exceeds 80% of available heap
- Clear processed DEK buffers immediately after upload to manage memory
- Retry failed batches with exponential backoff (max 3 attempts), then pause and prompt user
- Unwrap each DEK with old KEK, re-wrap with new KEK
- Upload re-wrapped DEKs to server
- Maintain dual-KEK access during transition period (check DEK version to select KEK)
- Update local encrypted key storage upon completion
- Securely zeroize old KEK from memory after completion
- Minimize user disruption during rotation process
- Support pausing and resuming rotation for large vaults with progress stored in IndexedDB
- Block share creation during rotation (shares must use new KEK only)
- New uploads use new KEK; in-progress downloads use KEK matching file's DEK version

### 2. API Gateway

**Responsibilities:**
- Expose RESTful API endpoints
- Validate SigV4 signatures
- Route requests to appropriate Lambda functions
- Rate limiting and throttling
- API versioning

**Endpoints (defined in Smithy model):**

**API Versioning Strategy:** The API uses URI versioning (e.g., `/v1/items`) to support backward-compatible evolution. The current version is v1. Breaking changes will result in a new version (v2), while non-breaking changes can be added to existing versions.

```
POST   /v1/auth/login              - Initiate authentication with account password
POST   /v1/auth/refresh            - Refresh credentials
POST   /v1/auth/recover            - Initiate account recovery with recovery code

POST   /v1/vaults                  - Create new vault with vault salt
GET    /v1/vaults/{id}/salt        - Retrieve vault salt for key derivation

POST   /v1/items                   - Create any item type (MEDIA, NOTE, TASK, EVENT)
GET    /v1/items                   - List items (filter by type, tags, date buckets)
GET    /v1/items/{id}              - Get item metadata
PUT    /v1/items/{id}              - Update item
DELETE /v1/items/{id}              - Delete item
POST   /v1/items/search            - Search across types or specific type
GET    /v1/items/{id}/download     - Get presigned download URL (for media items)
POST   /v1/items/upload/init       - Initialize upload, get presigned URL (for media items)
POST   /v1/items/upload/complete   - Mark upload complete, store metadata (for media items)

POST   /v1/collections             - Create collection
GET    /v1/collections             - List collections
GET    /v1/collections/{id}        - Get collection details
PUT    /v1/collections/{id}        - Update collection
DELETE /v1/collections/{id}        - Delete collection
POST   /v1/collections/{id}/items  - Add item to collection
DELETE /v1/collections/{id}/items/{itemId} - Remove item from collection

GET    /v1/tags/search             - Search by encrypted tag

POST   /v1/shares                  - Create item share with metadata
GET    /v1/shares/{id}             - Access shared item (anonymous)
DELETE /v1/shares/{id}             - Revoke share

POST   /v1/notifications/schedules           - Create notification schedule
GET    /v1/notifications/schedules           - List pending schedules
GET    /v1/notifications/schedules/{id}      - Get schedule details
PUT    /v1/notifications/schedules/{id}      - Update schedule
DELETE /v1/notifications/schedules/{id}      - Cancel notification
POST   /v1/notifications/devices             - Register device token (encrypted)
DELETE /v1/notifications/devices/{deviceId} - Unregister device

POST   /v1/recovery/codes          - Generate account recovery codes
POST   /v1/recovery/validate       - Validate recovery code

WebSocket /v1/sync                  - Real-time sync connection
  - onConnect: Authenticate and register connection
  - onDisconnect: Clean up connection state
  - onMessage: Handle ping/pong for keep-alive
  - Server sends: Item update notifications (metadata only)
```

### 3. Lambda Functions

**Implementation Language:** All Lambda functions are implemented in Python 3.11+ for consistency, performance, and rich library ecosystem support.

**Item Handler (Generic CRUD):**
- Extracts user identity from API Gateway authorizer context
- Validates user permissions (user can only access their own namespace)
- Handles all item types (MEDIA, NOTE, TASK, EVENT) with unified logic
- For media items: Generates presigned S3 URLs for upload/download
- For other items: Stores encrypted content inline in DynamoDB
- Stores encrypted metadata in Items table with user isolation
- Supports filtering by itemType and encrypted date buckets
- Links items to user account using userId from Cognito token

**Notification Processing Handler:**
- Triggered by EventBridge every 5 minutes
- Queries Notification Schedules table for due notifications (timeBucket <= now + 15min)
- Sends push notifications via AWS SNS with encrypted payloads
- Marks schedules as SENT after successful delivery
- Handles retry logic for failed notifications
- No access to plaintext notification content
- Supports multiple device tokens per user for multi-device notifications

**Collection Handler:**
- CRUD operations for collections
- Manages item-collection associations (supports all item types)
- Supports multi-collection membership

**Vault Salt Handler:**
- Stores/retrieves vault salts for key derivation
- Salt is non-secret information used for Argon2id
- One salt per vault, generated using cryptographically secure random number generator
- Ensures each vault salt is unique and never reused
- No access to vault keys or passwords

**Account Recovery Handler:**
- Stores/retrieves account recovery codes (10 codes per user)
- Validates recovery codes during account recovery flow
- Invalidates used recovery codes to prevent reuse
- Separate from vault recovery keys (which are never stored on server)

**Tag Search Handler:**
- Searches encrypted tags using exact match
- Returns matching items (any type)
- No plaintext tag access

**Share Handler:**
- Creates share records with metadata (expiration, password protection flag)
- Validates share access (checks expiration and revocation status)
- Enables anonymous access to shared items
- Increments access counter on each retrieval
- Never stores share keys (embedded in URLs)
- Generates presigned S3 URLs for shared media downloads

**Sync Handler (WebSocket):**
- Manages WebSocket connections for real-time sync
- Sends vault update notifications to connected devices when items are modified
- Includes only metadata (item ID, item type, version number, timestamp) in sync messages
- Never includes encrypted content in sync notifications
- Enables cross-device real-time updates
- Connected devices fetch full encrypted data via REST API after receiving notification
- Uses last-write-wins conflict resolution based on version numbers
- Maintains connection state in DynamoDB for connection management

### 4. DynamoDB Schema

**Three-Table Design:**

**Items Table** (`cortex-{env}-items`) - Unified storage for all item types:
- **Items:** `PK: VAULT#{vaultId}, SK: ITEM#{itemType}#{itemId}`
  - Attributes:
    - itemId (UUID)
    - itemType (enum: MEDIA, NOTE, TASK, EVENT)
    - encryptedContent (binary) - type-specific JSON
    - encryptedMetadata (binary) - common metadata
    - encryptedTags (list<binary>)
    - encryptedDateBucket (binary, optional) - for tasks/events
    - timeBucket (string, optional) - plaintext 15-min bucket for queries
    - createdAt, updatedAt (number)
    - version (number) - for conflict resolution
    - sizeBytes (number, optional) - for media items
    - s3Key (string, optional) - for media items with large content
    - wrappedDek (binary) - DEK wrapped with KEK (required for media items)
    - dekVersion (number) - version of DEK wrapping format
  - GSI1 (Type-based queries): `PK: VAULT#{vaultId}#TYPE#{itemType}, SK: ITEM#{itemId}`
  - GSI2 (Date-based queries): `PK: VAULT#{vaultId}#TYPE#{itemType}#DATE#{timeBucket}, SK: ITEM#{itemId}`
  - GSI3 (Tag search): `PK: VAULT#{vaultId}#TAG#{encryptedTag}, SK: ITEM#{itemId}`

**Collections Table** (`cortex-{env}-collections`) - Collection metadata:
- **Collections:** `PK: VAULT#{vaultId}, SK: COLLECTION#{collectionId}`
- **Item-Collection Associations:** `PK: COLLECTION#{collectionId}, SK: ITEM#{itemId}`
  - GSI1 (reverse lookup): `PK: ITEM#{itemId}, SK: COLLECTION#{collectionId}`

**Notification Schedules Table** (`cortex-{env}-notification-schedules`) - Push notification scheduling:
- **Schedules:** `PK: VAULT#{vaultId}, SK: SCHEDULE#{timeBucket}#{scheduleId}`
  - Attributes:
    - scheduleId (UUID)
    - itemId (reference to task/event)
    - encryptedPayload (binary) - notification title, body, etc.
    - encryptedExactTime (binary) - exact notification time
    - timeBucket (string) - plaintext 15-min bucket (e.g., "2026-01-15T14:00")
    - encryptedDeviceTokens (list<binary>) - for push notifications
    - status (enum: PENDING, SENT, CANCELLED, RETRY_1, RETRY_2, RETRY_3, DEAD_LETTER)
    - createdAt (number)
    - sentAt (number, optional)
  - GSI1 (Global notification processing): `PK: STATUS#{status}, SK: TIMEBUCKET#{timeBucket}`

**Additional Tables:**
- **Users Table** (`cortex-{env}-users`): `PK: USER#{userId}, SK: PROFILE`
- **Vaults Table** (`cortex-{env}-vaults`): `PK: USER#{userId}, SK: VAULT#{vaultId}`
  - Attributes: vaultId, userId, vaultSalt (binary, non-secret), currentKekVersion (number), rotationState (enum: IDLE, IN_PROGRESS), rotationLockedAt (number, optional, Unix epoch), createdAt, updatedAt
  - Note: currentKekVersion stored as non-secret metadata to support vault recovery key compatibility with rotated keys
  - Note: rotationState and rotationLockedAt used for concurrent rotation prevention (optimistic locking via conditional writes)
- **Account Recovery Table** (`cortex-{env}-recovery`): `PK: USER#{userId}, SK: RECOVERY#{codeHash}`
- **Shares Table** (`cortex-{env}-shares`) - Anonymous access, security isolated: `PK: SHARE#{shareId}, SK: METADATA`
- **WebSocket Connections Table** (`cortex-{env}-connections`) - Real-time sync: `PK: CONNECTION#{connectionId}, SK: METADATA`
  - Attributes: connectionId, userId, vaultId, connectedAt, lastPingAt
  - GSI1: `PK: VAULT#{vaultId}, SK: CONNECTION#{connectionId}` (for broadcasting to all vault connections and enforcing per-vault connection limit of 10)

### 5. S3 Bucket Structure

**Bucket Configuration:**
- Server-side encryption: AES-256 (additional layer of defense)
- Versioning: Enabled (for accidental deletion protection)
- Lifecycle policies: Optional transition to Glacier for cost optimization
- Transfer acceleration: Enabled for faster global uploads (configurable based on user location)
- CORS: Configured for direct client uploads
- Multipart upload configuration: Minimum part size 5MB, maximum 10,000 parts per upload

**Object Key Structure:**
```
vaults/{vaultId}/files/{fileId}/{timestamp}-{random}
```

**Presigned URL Configuration:**
- Upload URLs: 15-minute expiration, PUT only
- Download URLs: 15-minute expiration, GET only
- Scoped to specific object key
- Content-type restrictions on upload

### 6. Cognito Configuration

**User Pool:**
- Email/password authentication (account password only, not vault password)
- MFA optional (recommended for additional security)
- Password policy: minimum 12 characters, complexity requirements (uppercase, lowercase, numbers, special characters)
- Account recovery via email or recovery codes
- Custom authentication flow for recovery code validation

**Identity Pool:**
- Federated identities for OIDC support
- Role-based access control
- Scoped IAM policies per user

**IAM Policy Approach:**
- No per-user IAM policies required
- All S3 access via scoped presigned URLs generated by Lambda functions
- Presigned URLs are scoped to specific objects and operations (PUT or GET)
- Lambda functions have IAM roles with permissions to generate presigned URLs and access DynamoDB
- API Gateway validates user identity via SigV4 and passes user context to Lambda
- Lambda enforces access control by:
  - Verifying user owns the vault before generating presigned URLs
  - Scoping presigned URLs to the specific file path (vaults/{vaultId}/files/{fileId}/...)
  - Setting appropriate expiration times (15 minutes)
  - Validating user permissions before any DynamoDB operations

**Lambda Execution Role (example):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::cortex-files-bucket/vaults/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
      "Resource": [
        "arn:aws:dynamodb:region:account:table/cortex-data",
        "arn:aws:dynamodb:region:account:table/cortex-data/index/GSI1",
        "arn:aws:dynamodb:region:account:table/cortex-shares"
      ]
    }
  ]
}
```

**Note:** Users never have direct S3 or DynamoDB access. All access is mediated through Lambda functions that generate scoped presigned URLs for S3 operations and enforce user isolation for all data operations.

## Data Models

### Client-Side Data Models

**Base Item (Plaintext - Client Only):**
```typescript
enum ItemType {
  MEDIA = 'MEDIA',
  NOTE = 'NOTE',
  TASK = 'TASK',
  EVENT = 'EVENT'
}

interface BaseItem {
  id: string;
  itemType: ItemType;
  createdAt: Date;
  updatedAt: Date;
  tags: string[];
  collections: string[];
}

interface MediaItem extends BaseItem {
  itemType: ItemType.MEDIA;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  s3Key: string;
}

interface NoteItem extends BaseItem {
  itemType: ItemType.NOTE;
  title: string;
  body: string; // HTML or Markdown
  attachments?: string[]; // S3 keys for attachments
}

interface TaskItem extends BaseItem {
  itemType: ItemType.TASK;
  title: string;
  description?: string;
  dueDate?: Date;
  priority: 'low' | 'medium' | 'high';
  isComplete: boolean;
  recurrence?: RecurrenceRule;
  reminderTime?: Date;
}

interface EventItem extends BaseItem {
  itemType: ItemType.EVENT;
  title: string;
  description?: string;
  startTime: Date;
  endTime: Date;
  location?: string;
  recurrence?: RecurrenceRule;
  reminderTime?: Date;
  attendees?: string[];
}

interface RecurrenceRule {
  frequency: 'daily' | 'weekly' | 'monthly' | 'yearly';
  interval: number;
  until?: Date;
  count?: number;
}
```

**Notification Models (Plaintext - Client Only):**
```typescript
interface NotificationSchedule {
  id: string;
  itemId: string;
  exactTime: Date;
  payload: NotificationPayload;
  deviceTokens: string[];
  status: 'PENDING' | 'SENT' | 'CANCELLED';
}

interface NotificationPayload {
  title: string;
  body: string;
  itemType: ItemType;
  itemId: string;
  actionUrl?: string;
}
```

**Collection (Plaintext - Client Only):**
```typescript
interface Collection {
  id: string;
  name: string;
  description?: string;
  createdAt: Date;
  updatedAt: Date;
  itemCount: number;
  coverItemId?: string;
}
```

**Vault Keys (Client Only - Never Transmitted):**
```typescript
interface VaultKeys {
  vaultMasterKey: Uint8Array; // 256-bit key derived from vault password using Argon2id
  
  // Key Encryption Key for envelope encryption
  keyEncryptionKey: Uint8Array; // derived from master key via HKDF (wraps/unwraps DEKs)
  
  // Other derived keys
  metadataEncryptionKey: Uint8Array; // derived from master key via HKDF
  shareKeyDerivationKey: Uint8Array; // derived from master key via HKDF
  
  // Keys for productivity features
  notesEncryptionKey: Uint8Array; // derived from master key via HKDF
  tasksEncryptionKey: Uint8Array; // derived from master key via HKDF
  eventsEncryptionKey: Uint8Array; // derived from master key via HKDF
  notificationEncryptionKey: Uint8Array; // derived from master key via HKDF
  dateBucketKey: Uint8Array; // derived from master key via HKDF (for HMAC)
  
  kekVersion: number; // for KEK rotation tracking
  version: number; // for key rotation
  createdAt: Date;
  lastRotatedAt: Date;
}

interface WrappedDek {
  wrappedKey: Uint8Array; // DEK encrypted with KEK using ChaCha20-Poly1305
  version: number; // DEK wrapping format version
  createdAt: Date;
}

/**
 * DEK Version Management and Deprecation (REQ-32)
 *
 * Version States:
 * - CURRENT (v1): Active version used for all new DEK wrapping
 * - SUPPORTED (v1): Can be unwrapped for reading existing files
 * - DEPRECATED: Marked as insecure, migration required, unwrapping refused
 *
 * Version Deprecation Policy:
 * - When a DEK version is deprecated, client maintains list in code
 * - Deprecated versions refuse unwrapping with error message
 * - User prompted to run migration tool to re-wrap with current version
 * - Migration tool: unwrap with old version → re-wrap with current version
 *
 * Security Protections:
 * - Constant-time comparison for authentication tag verification
 * - Downgrade attack prevention: refuse deprecated/unsupported versions
 * - Version list maintained in client code, not server-controllable
 * - Clear user guidance on migration path when deprecated version encountered
 */
const SUPPORTED_DEK_VERSIONS = [1]; // Currently supported versions
const DEPRECATED_DEK_VERSIONS: number[] = []; // Insecure versions, refuse unwrapping
const CURRENT_DEK_VERSION = 1; // Version used for new wrapping

/**
 * DEK Version Deployment Strategy (REQ-35)
 *
 * New DEK versions follow a two-phase introduction to ensure rollback safety:
 *
 * Phase 1 - SUPPORTED only (minimum 30 days):
 *   - New version added to SUPPORTED_DEK_VERSIONS
 *   - Client can READ (unwrap) DEKs wrapped with the new version
 *   - Client continues to WRITE (wrap) new DEKs with the previous CURRENT version
 *   - This ensures all deployed clients can handle the new version before it becomes active
 *
 * Phase 2 - CURRENT (after 30+ days):
 *   - CURRENT_DEK_VERSION updated to the new version
 *   - Client now WRITES new DEKs with the new version
 *   - Old version remains in SUPPORTED_DEK_VERSIONS for backward compatibility
 *
 * Rollback Safety:
 *   - Rolling back from Phase 2 to Phase 1 is safe: clients revert to wrapping with
 *     the old version, and DEKs already wrapped with the new version remain readable
 *     because the new version stays in SUPPORTED_DEK_VERSIONS
 *   - Rolling back from Phase 1 removes the new version from SUPPORTED_DEK_VERSIONS
 *     only if no DEKs have been wrapped with it (Phase 1 never writes with new version)
 *   - Data loss is prevented because rollback never removes a version that has wrapped DEKs
 */

interface LocalKeyStorage {
  encryptedKeys: Uint8Array; // VaultKeys encrypted with device-specific key
  deviceId: string;
  lastUsedAt: Date;
}

interface VaultRecoveryKey {
  recoveryKey: string; // BIP39 mnemonic derived from vault master key
  createdAt: Date;
  // Never transmitted to server, displayed once to user
}
```

### Server-Side Data Models (All Encrypted)

**Stored Item:**
```typescript
interface StoredItem {
  vaultId: string;
  userId: string;
  itemId: string;
  itemType: 'MEDIA' | 'NOTE' | 'TASK' | 'EVENT';
  encryptedContent: Uint8Array; // Type-specific content as encrypted JSON
  encryptedMetadata: Uint8Array; // Common metadata
  encryptedTags: Uint8Array[];
  encryptedDateBucket?: Uint8Array; // For tasks/events
  timeBucket?: string; // Plaintext 15-min bucket for queries
  createdAt: number;
  updatedAt: number;
  version: number;
  sizeBytes?: number; // For media
  s3Key?: string; // For media
  wrappedDek: Uint8Array; // DEK wrapped with KEK (required for media items)
  dekVersion: number; // Version of DEK wrapping format
}
```

**Stored Notification Schedule:**
```typescript
interface StoredNotificationSchedule {
  vaultId: string;
  scheduleId: string;
  itemId: string;
  encryptedPayload: Uint8Array;
  encryptedExactTime: Uint8Array;
  timeBucket: string; // Plaintext for server queries
  encryptedDeviceTokens: Uint8Array[];
  status: 'PENDING' | 'SENT' | 'CANCELLED' | 'RETRY_1' | 'RETRY_2' | 'RETRY_3' | 'DEAD_LETTER';
  createdAt: number;
  sentAt?: number;
  failureReason?: string; // set when status is DEAD_LETTER
  lastAttemptAt?: number; // set on each retry or dead-letter transition
}
```

**Stored Collection:**
```typescript
interface StoredCollection {
  vaultId: string;
  userId: string;
  collectionId: string;
  encryptedMetadata: Uint8Array; // encrypted Collection
  createdAt: number;
  updatedAt: number;
  itemCount: number;
}
```

### Encryption Format

All encrypted data follows this structure:
```
[nonce (12 bytes)][encrypted data][auth tag (16 bytes)]
```

Using ChaCha20-Poly1305:
- Nonce: 96-bit random value (unique per encryption)
- Auth tag: 128-bit authentication tag
- Algorithm: ChaCha20-Poly1305
- Key size: 256 bits

### Tag Encryption Strategy

For searchable encrypted tags, we use deterministic encryption:
- Each unique tag encrypts to the same ciphertext
- Uses HMAC-SHA256 with master key as deterministic "encryption"
- Enables server-side exact match without revealing plaintext
- Trade-off: frequency analysis possible, but content remains hidden

```typescript
function encryptTagForSearch(tag: string, masterKey: Uint8Array): Uint8Array {
  return hmacSHA256(masterKey, utf8Encode(tag.toLowerCase()));
}
```

### Date Bucket Encryption Strategy

For privacy-preserving date queries on tasks and events:
- Exact times are encrypted with ChaCha20-Poly1305 (stored as binary)
- Time buckets (15-minute windows) are stored in plaintext for server queries
- Encrypted date buckets use deterministic HMAC for client-side filtering

```typescript
// Round date to 15-minute bucket
function roundToTimeBucket(date: Date): string {
  const minutes = date.getMinutes();
  const roundedMinutes = Math.floor(minutes / 15) * 15;
  const bucketDate = new Date(date);
  bucketDate.setMinutes(roundedMinutes, 0, 0);
  return bucketDate.toISOString().substring(0, 16); // "2026-01-15T14:00"
}

// Encrypt exact time (stored as binary)
function encryptExactTime(date: Date, key: Uint8Array): Uint8Array {
  const timestamp = date.toISOString();
  return encryptChaCha20Poly1305(utf8Encode(timestamp), key);
}

// Create deterministic encrypted date bucket for queries
function encryptDateBucket(date: Date, key: Uint8Array): Uint8Array {
  const bucket = roundToTimeBucket(date);
  return hmacSHA256(key, utf8Encode(bucket)); // Deterministic
}
```

**Privacy Trade-off:**
- Server knows notifications/tasks exist in 15-minute windows
- Server doesn't know exact times
- Server doesn't know content
- Acceptable for practical notification delivery and date-based queries

## Cor
rectness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Client-side encryption before transmission

*For any* user data (file content, metadata, tags, or collection information), when the React frontend prepares to send it to the server, the transmitted data must be encrypted using ChaCha20-Poly1305 and must not match the plaintext original.

**Validates: Requirements 1.1, 2.1, 11.1, 12.1, 13.1**

### Property 2: Server storage preserves encryption

*For any* encrypted data received by the server, the data stored in S3 or DynamoDB must exactly match the encrypted data that was transmitted, with no decryption or re-encryption occurring.

**Validates: Requirements 1.2, 2.2, 11.3, 12.2**

### Property 3: Server responses contain only encrypted data

*For any* API response containing user data (file lists, metadata, collections, tags), all sensitive fields in the response must be encrypted and must not contain plaintext user information.

**Validates: Requirements 2.3, 10.3, 12.4, 13.5**

### Property 4: Vault data isolation

*For any* two distinct vaults A and B, a user with access to vault A must not be able to access, modify, or delete any resources (files, metadata, collections) belonging to vault B, regardless of the API operation attempted.

**Validates: Requirements 2.4, 3.3, 4.3, 5.1**

### Property 5: Referential integrity between S3 and DynamoDB

*For any* file, if metadata exists in DynamoDB, then the corresponding encrypted object must exist in S3, and if an encrypted object exists in S3, then corresponding metadata must exist in DynamoDB.

**Validates: Requirements 2.5**

### Property 6: Vault keys never transmitted to server

*For any* API request or response in the system, the vault master key, data encryption key, metadata encryption key, vault password, or vault recovery key must never appear in the request/response payload, headers, or logs.

**Validates: Requirements 3.6, 9.3, 14.6, 15.5, 16.4**

### Property 7: Upload and download round-trip preserves content

*For any* file, uploading the encrypted file and then downloading it must result in the same plaintext content after client-side decryption (encryption and decryption are inverse operations).

**Validates: Requirements 4.2**

### Property 8: Deletion maintains referential integrity

*For any* file deletion operation, either both the S3 object and DynamoDB metadata are successfully deleted, or both remain unchanged (atomic deletion or rollback on failure).

**Validates: Requirements 5.2, 5.3, 5.4**

### Property 9: API error responses are well-formed

*For any* API error condition (authentication failure, authorization failure, not found, etc.), the error response must include a valid HTTP status code, a structured error message, and must not leak sensitive information.

**Validates: Requirements 8.3**

### Property 10: All server-stored data is encrypted

*For any* data stored in S3 or DynamoDB (files, metadata, tags, collections), the stored representation must be encrypted and must not be readable without the vault's encryption keys.

**Validates: Requirements 9.2, 9.5, 16.1, 16.2**

### Property 11: File list queries respect vault boundaries

*For any* vault's file list query (with any pagination, filtering, or sorting parameters), the results must contain only files belonging to that vault and must include all of that vault's files that match the query criteria.

**Validates: Requirements 10.1, 10.4**

### Property 12: Pagination consistency

*For any* paginated file list query, iterating through all pages must return each file exactly once, with no duplicates and no omissions.

**Validates: Requirements 10.2**

### Property 13: Encrypted tag search functionality

*For any* tag search query, the React frontend must encrypt the search term before sending, and the server must return all files with matching encrypted tags without accessing plaintext tag values.

**Validates: Requirements 11.3, 11.4**

### Property 14: File-collection many-to-many relationships

*For any* file and any set of collections, the file can be added to multiple collections simultaneously, and each collection correctly reports the file as a member.

**Validates: Requirements 12.3, 12.5**

### Property 15: Collection deletion preserves files

*For any* collection containing files, deleting the collection must remove all file-collection associations and the collection metadata, but all files must remain accessible and unchanged.

**Validates: Requirements 13.3, 13.4**

### Property 16: File removal from collection preserves file

*For any* file in a collection, removing the file from the collection must delete only the association, leaving both the file and the collection intact and accessible.

**Validates: Requirements 13.2**

### Property 17: Vault key derivation is deterministic

*For any* vault password and vault salt, deriving the vault master key using Argon2id must produce the same key every time, enabling multi-device access with the same credentials.

**Validates: Requirements 14.1, 14.2, 14.5**

### Property 18: Vault recovery key enables vault access

*For any* vault with a recovery key, using the recovery key must allow re-deriving the vault master key, enabling the user to set a new vault password while maintaining access to all encrypted data.

**Validates: Requirements 15.3**

### Property 19: Administrator cannot access plaintext data

*For any* data stored in the system (S3, DynamoDB, logs), an administrator with full AWS console access but without the vault password or keys must not be able to decrypt or determine the content, subject matter, or organizational structure of user data.

**Design Rationale:** This property is fundamental to the zero-knowledge architecture. All encryption happens in the React frontend with keys that never leave the browser. Even with full infrastructure access, administrators can only see:
- Encrypted binary blobs in S3
- Encrypted metadata in DynamoDB
- User IDs, vault IDs, and timestamps (non-sensitive)
- Vault salts (non-secret, useless without vault password)
- System metrics and performance data

Administrators cannot determine:
- What file content contains
- Original filenames or descriptions
- File types or MIME types
- Tag meanings or search terms
- Collection names or organizational structure
- Relationships between files

**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

### Property 20: Share keys enable file access without vault password

*For any* shared file, a recipient with the share URL (containing the share key) must be able to decrypt and access the file without knowing the vault password or having access to the vault's encryption keys.

**Validates: Requirements 17.1, 17.4**

### Property 21: Account password change does not affect vault encryption

*For any* user account, changing the account password must not require re-encryption of any vault data, and all previously encrypted files must remain accessible with the unchanged vault password.

**Validates: Requirements 23.1**

### Property 22: Vault password change requires DEK re-wrapping

*For any* vault, changing the vault password must result in deriving a new vault master key and KEK, and re-wrapping all DEKs with the new KEK. File content in S3 must remain unchanged.

**Validates: Requirements 23.3, 23.4**

### Property 23: Password strength validation

*For any* password (account or vault), the system must reject passwords shorter than 12 characters or lacking uppercase letters, lowercase letters, numbers, and special characters.

**Validates: Requirements 21.1, 21.2**

### Property 24: Breached password detection

*For any* password being created or changed, if the password appears in known breach databases, the system must reject it and require the user to choose a different password.

**Validates: Requirements 21.3, 21.4**

### Property 25: Account recovery code validation

*For any* valid unused account recovery code, using it for account recovery must grant access to the account and invalidate that specific code, while leaving other codes valid.

**Validates: Requirements 19.2, 19.3**

### Property 26: Automatic key rotation preserves data access

*For any* vault undergoing automatic key rotation (after 90 days), all previously encrypted data must remain accessible during and after the rotation process. Key rotation must only re-wrap DEKs with the new KEK, not re-encrypt file content.

**Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5**

### Property 27: Vault salt uniqueness

*For any* two distinct vaults, their vault salts must be different, ensuring that the same vault password produces different vault master keys for different vaults.

**Validates: Requirements 22.4**

### Property 28: Generic item CRUD operations

*For any* item type (MEDIA, NOTE, TASK, EVENT), creating, reading, updating, and deleting items must work consistently regardless of type, with all sensitive data encrypted client-side before transmission.

**Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5**

### Property 29: Date bucket privacy

*For any* task or event with a date, the server must only have access to the 15-minute time bucket, not the exact time, while the React frontend can decrypt and access the exact time.

**Validates: Requirements 25.1, 25.2, 25.3, 25.4, 25.5**

### Property 30: Notification content privacy

*For any* notification, the server must send push notifications with encrypted payloads, and only the React frontend can decrypt and display the notification content.

**Design Rationale:** Notifications are scheduled with encrypted payloads that include the notification title, body, and action URL. The server stores the encrypted payload and exact time (also encrypted), along with a plaintext time bucket for query efficiency. When EventBridge triggers the notification handler every 5 minutes, it queries for schedules with timeBucket <= now + 15min. The handler sends the encrypted payload via AWS SNS to registered device tokens. The React frontend receives the notification, decrypts the payload locally in the browser, and displays it to the user. The server never has access to notification content, maintaining zero-knowledge architecture even for time-sensitive reminders.

**Validates: Requirements 26.1, 26.2, 26.3, 26.4, 26.5**

### Property 31: Cross-device sync consistency

*For any* item modified on one device, all other connected devices must eventually receive the update and converge to the same state after decryption.

**Design Rationale:** Real-time sync is implemented using WebSocket connections managed by API Gateway and Lambda. When a user modifies an item (create, update, delete), the API handler broadcasts a sync notification to all WebSocket connections for that vault. The notification contains only metadata: item ID, item type, version number, and timestamp. Connected devices receive the notification and fetch the full encrypted item data via REST API. Conflicts are resolved using last-write-wins based on version numbers stored in DynamoDB. Each item has a version field that increments on every update. When a conflict is detected (two devices modified the same item), the React frontend compares version numbers and accepts the higher version. This ensures eventual consistency across all devices while maintaining zero-knowledge architecture (sync notifications never contain encrypted content).

**Validates: Requirements 27.1, 27.2, 27.3, 27.4, 27.5**

### Property 32: Envelope encryption round-trip

*For any* media file content, generating a unique DEK, encrypting the content with the DEK, wrapping the DEK with the KEK, then unwrapping the DEK and decrypting the content must produce the original file content.

**Design Rationale:** Envelope encryption uses a two-layer key hierarchy. Each file gets a unique 256-bit DEK generated using CSPRNG. The file content is encrypted with ChaCha20-Poly1305 using the DEK. The DEK is then wrapped (encrypted) with the vault's KEK using ChaCha20-Poly1305. On download, the wrapped DEK is unwrapped using the KEK, and the file content is decrypted using the unwrapped DEK. This round-trip must be lossless and deterministic for the same inputs.

**Validates: Requirements 28.1, 28.2, 28.3, 29.2, 29.3**

### Property 33: DEK uniqueness

*For any* two distinct media files uploaded to the same vault, their DEKs must be different, ensuring that compromise of one file's DEK does not affect other files.

**Design Rationale:** DEKs are generated using a cryptographically secure random number generator (CSPRNG), not derived from the vault master key. This ensures each file has an independent key. The probability of collision for 256-bit random keys is negligible (2^-128 for birthday attack). This property provides key isolation - if an attacker somehow obtains one DEK, they cannot decrypt other files.

**Validates: Requirements 28.4, 28.5**

### Property 34: Key rotation efficiency

*For any* key rotation operation, only wrapped DEKs must be transferred between client and server, not file content. The total data transferred during rotation must be proportional to the number of files, not the total file size.

**Design Rationale:** With envelope encryption, key rotation only requires re-wrapping DEKs with the new KEK. Each wrapped DEK is approximately 60 bytes (12-byte nonce + 32-byte encrypted DEK + 16-byte auth tag). For a vault with 10,000 files totaling 100GB, key rotation transfers only ~600KB of wrapped DEKs instead of 100GB of file content. This makes key rotation practical for large vaults.

**Validates: Requirements 30.2, 30.4**

### Property 35: Key rotation round-trip

*For any* DEK wrapped with the old KEK, unwrapping with the old KEK and re-wrapping with the new KEK must produce a valid wrapped DEK that can be unwrapped with the new KEK to recover the original DEK.

**Design Rationale:** Key rotation preserves the underlying DEKs - only the wrapping changes. The DEK itself remains constant, so file content in S3 doesn't need to be re-encrypted. After rotation, files can be decrypted using the new KEK to unwrap the DEK, then the DEK to decrypt the content.

**Validates: Requirements 30.1, 30.3, 30.6**

### Property 36: Dual-KEK access during rotation

*For any* vault undergoing key rotation, files must remain accessible using either the old KEK (for not-yet-rotated items) or the new KEK (for already-rotated items) until rotation completes.

**Design Rationale:** During rotation, the client maintains both old and new KEKs. When accessing a file, the client checks the DEK version to determine which KEK to use for unwrapping. This ensures uninterrupted access during the rotation process, which may take time for large vaults.

**Validates: Requirements 30.5**

### Property 37: Share creation round-trip

*For any* media file, creating a share by unwrapping the DEK with the vault's KEK, deriving a share encryption key from the password and salt, and wrapping the DEK with the share encryption key must produce a password-wrapped DEK that allows recipients with the correct password to decrypt the file.

**Design Rationale:** Sharing uses password-based key derivation to wrap the file's DEK. The password-wrapped DEK and salt are embedded in the share URL - no keys are stored on the server. Recipients must know the share password to derive the same share encryption key and unwrap the DEK. This ensures true zero-knowledge sharing where the server never has access to any key material.

**Validates: Requirements 31.1, 31.2, 31.4, 31.5**

### Property 38: Share isolation and zero-knowledge

*For any* share created for a media file, no key material (DEK, wrapped DEK, share key, or salt) must be stored on the server. The server must only store share metadata (expiration, access count, revocation status).

**Design Rationale:** True zero-knowledge sharing requires that all cryptographic material be embedded in the share URL. The server stores only non-sensitive metadata needed for access control (expiration, revocation). This ensures that even with full database access, an attacker cannot decrypt shared files without the share URL and password.

**Validates: Requirements 31.3, 31.6**

### Property 39: DEK version compatibility and deprecation protection

*For any* DEK wrapped with a supported (non-deprecated) version, unwrapping must succeed regardless of when the DEK was wrapped, ensuring long-term access to files. *For any* DEK wrapped with a deprecated or unsupported version, unwrapping must fail with a clear error message and migration guidance.

**Design Rationale:** DEK wrapping includes a version identifier to support future algorithm changes. The client maintains a list of SUPPORTED_DEK_VERSIONS and DEPRECATED_DEK_VERSIONS. Supported versions can be unwrapped for backward compatibility. Deprecated versions (due to security vulnerabilities) refuse unwrapping and prompt users to migrate. This prevents downgrade attacks where an attacker forces use of an old, vulnerable wrapping algorithm. Users are provided a migration path to re-wrap DEKs with the current secure version.

**Validates: Requirements 32.1, 32.2, 32.3, 32.5, 32.6, 32.7, 32.8, 32.9**

### Property 40: Batch rotation with retry

*For any* key rotation operation processing DEKs in batches, if a batch fails, retrying the batch must eventually succeed (assuming transient failures), and the final state must have all DEKs re-wrapped with the new KEK.

**Design Rationale:** Large vaults may have thousands of files. Batch processing with retry logic ensures rotation completes reliably even with transient network or server errors. Progress is tracked so rotation can be paused and resumed without re-processing already-rotated items.

**Validates: Requirements 33.1, 33.2, 33.4, 33.5, 33.6**

## Non-Functional Requirements Design

### Performance Design

**Upload Performance (REQ-NFR-1):**
- Direct S3 uploads via presigned URLs bypass Lambda, reducing latency
- Multipart upload for files >100MB with 5MB minimum part size
- Concurrent upload support (up to 5 files) via client-side queue management
- S3 Transfer Acceleration enabled for improved global upload speeds
- Target: <10 seconds for 5MB files on 10 Mbps connection

**Query Performance (REQ-NFR-2):**
- DynamoDB GSIs optimized for common query patterns (by type, by tag, by date bucket)
- Pagination with DynamoDB native tokens for consistent performance
- Target: <2 seconds for 10,000 item collections
- Tag search via GSI with encrypted tag matching: <3 seconds
- Page sizes: 10-100 items per page

**Key Derivation Performance (REQ-NFR-3):**
- Argon2id parameters balanced for security and performance (64MB memory, 3 iterations)
- Target: <5 seconds on modern client devices
- HKDF derivation: <100ms for all derived keys
- Client-side caching of derived keys in encrypted local storage

### Security Design

**Encryption Standards (REQ-NFR-4):**
- ChaCha20-Poly1305 for all symmetric encryption (256-bit keys)
- Argon2id for key derivation (64MB memory, 3 iterations, 4 parallelism)
- HKDF-SHA256 for deriving multiple keys from vault master key
- Random nonce generation using cryptographically secure RNG

**Authentication (REQ-NFR-5):**
- AWS SigV4 for all API requests
- Cognito-issued JWT tokens with 1-hour expiration
- Refresh tokens valid for 30 days
- Automatic token refresh before expiration

**Data Protection (REQ-NFR-6):**
- TLS 1.3 for all data in transit
- S3 server-side encryption (AES-256) as additional defense layer
- Presigned URLs with 15-minute expiration
- HTTPS-only bucket policy

**Session Management and Key Zeroization (REQ-34):**
- **Logout Key Clearing**: On user logout, all key material (vault master key, KEK, all derived keys, cached DEKs) is overwritten with cryptographically random data before dereferencing
- **Double Overwrite**: Key buffers are overwritten twice (first with zeros, then with random data) to reduce memory recovery risk
- **Storage Cleanup**: Logout clears all encrypted keys from browser localStorage, sessionStorage, and IndexedDB
- **Session Timeout**: Automatic logout after inactivity performs same key zeroization as explicit logout
- **Unexpected Termination**: beforeunload event handlers attempt best-effort key zeroization on tab/window close
- **TypedArray Usage**: All key material stored in TypedArray (Uint8Array) to enable explicit zeroing via `.fill(0)` and `.fill(crypto.getRandomValues())`
- **Web Crypto API Preference**: Non-extractable CryptoKey objects used where possible to minimize JavaScript-accessible key material
- **JavaScript Limitations**: Documentation acknowledges that complete memory clearing cannot be guaranteed due to garbage collection and browser memory management
- **Constant-Time Operations**: All cryptographic comparisons (HMACs, authentication tags) use constant-time comparison to prevent timing attacks

### Scalability Design

**User Capacity (REQ-NFR-7):**
- Architecture supports 100,000+ concurrent users via serverless auto-scaling
- Per-user storage limit: 1TB (configurable via quotas)
- Per-vault item limit: 1 million items
- DynamoDB partition key design prevents hot partitions

**Infrastructure Scaling (REQ-NFR-8):**
- Lambda auto-scales based on request volume (no manual intervention)
- DynamoDB on-demand billing or auto-scaling provisioned capacity
- S3 unlimited storage capacity
- API Gateway handles millions of requests per second

### Availability Design

**Uptime (REQ-NFR-9):**
- Target: 99.9% uptime (8.76 hours downtime per year)
- Multi-AZ deployment for all AWS services
- Planned maintenance: <4 hours per month, scheduled during low-traffic windows
- Automated failover and recovery: <15 minutes

**Data Durability (REQ-NFR-10):**
- S3: 99.999999999% (11 nines) durability
- DynamoDB: 99.999999999% (11 nines) durability
- Point-in-time recovery enabled for DynamoDB
- S3 versioning enabled for accidental deletion protection
- Quarterly backup and recovery testing

### Usability Design

**React Frontend (REQ-NFR-11):**
- Real-time upload/download progress indicators
- Clear error messages with actionable guidance
- Password strength indicator during vault password setup
- Visual distinction between account password and vault password
- Recovery key display with secure storage instructions

**Documentation (REQ-NFR-12):**
- API documentation auto-generated from Smithy models (OpenAPI 3.0)
- User guide explaining two-password model with diagrams
- Step-by-step recovery procedures for both account and vault recovery
- Security best practices documentation
- FAQ covering common scenarios

### Compliance Design

**Privacy Compliance (REQ-NFR-13):**
- GDPR-compliant data handling and user rights
- Data export functionality: encrypted data + metadata in portable format
- Data deletion: permanent removal from S3 and DynamoDB
- Right to be forgotten: complete account and vault deletion
- Privacy policy clearly explains zero-knowledge architecture

**Audit Logging (REQ-NFR-14):**
- CloudTrail logs all AWS API calls
- Application logs all authentication attempts (success and failure)
- Application logs all data access operations (without plaintext data)
- Log retention: minimum 90 days, configurable up to 7 years
- Log sanitization: no passwords, keys, or encrypted payloads in logs
- Logged data: user IDs, vault IDs, timestamps, operation types, error codes

## Error Handling

### React Frontend Error Handling

**Local Storage Recovery:**
- On app load, the React frontend validates integrity of stored keys using a checksum (HMAC over the encrypted key blob using a key derived from the vault password)
- If the checksum fails or IndexedDB/localStorage is corrupted or unavailable:
  1. React frontend detects corruption (checksum mismatch, read error, or missing entries)
  2. React frontend prompts the user to re-enter their vault password
  3. React frontend fetches the vault salt from the Cortex System
  4. React frontend re-derives the vault master key from the vault password + vault salt using Argon2id
  5. React frontend re-derives all keys (KEK, metadata key, etc.) from the vault master key using HKDF
  6. React frontend stores the re-derived keys in local storage with a fresh integrity checksum
  7. Normal operation resumes
- This flow is identical to the new-device key derivation flow (REQ-14.4, REQ-14.5) and requires server connectivity to fetch the vault salt

**Encryption Failures:**
- Key derivation failures: Prompt user to re-enter password
- Encryption operation failures: Retry with exponential backoff, alert user if persistent
- Key bundle decryption failures: Verify password, offer recovery key option

**Network Failures:**
- Upload failures: Implement retry logic with exponential backoff
- Partial upload failures: Resume from last successful chunk (multipart upload)
- Download failures: Retry with fresh presigned URL

**Authentication Failures:**
- Token expiration: Automatic refresh using refresh token
- Invalid credentials: Prompt user to re-authenticate
- Network timeout: Retry authentication request
- Account recovery: Validate recovery code and allow password reset

**Password Validation Failures:**
- Weak password: Display specific requirements not met (length, complexity)
- Breached password: Reject with explanation and require different password
- Password mismatch: Prompt user to re-enter confirmation
- Vault password same as account password: Warn user and recommend different passwords

**Key Rotation Failures:**
- Re-encryption errors: Retry failed files, maintain old keys until completion
- Network interruption during rotation: Resume from last successful file
- Storage errors: Roll back to previous key version if critical failure occurs

### Server-Side Error Handling

**Lambda Function Errors:**
- Input validation errors: Return 400 Bad Request with structured error
- Authentication errors: Return 401 Unauthorized
- Authorization errors: Return 403 Forbidden
- Resource not found: Return 404 Not Found
- Internal errors: Return 500 Internal Server Error, log for investigation

**DynamoDB Errors:**
- Conditional check failures: Retry with exponential backoff
- Throttling: Implement exponential backoff with jitter
- Item not found: Return 404 to client
- Transaction failures: Rollback and return error

**S3 Errors:**
- Upload failures: Return error to client, clean up partial uploads
- Object not found: Return 404 to client
- Access denied: Return 403 to client
- Throttling: Implement exponential backoff

**Consistency Errors:**
- S3 upload succeeds but DynamoDB write fails: Delete S3 object (cleanup)
- DynamoDB write succeeds but S3 upload fails: Delete DynamoDB entry (cleanup)
- Implement idempotency tokens for critical operations

### Error Response Format

All API errors follow this structure:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "requestId": "unique-request-id",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

Error codes:
- `AUTHENTICATION_REQUIRED`: User must authenticate
- `AUTHENTICATION_FAILED`: Invalid credentials
- `AUTHORIZATION_FAILED`: User lacks permission
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `INVALID_REQUEST`: Malformed request
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Server-side error
- `STORAGE_ERROR`: S3 or DynamoDB error
- `SHARE_EXPIRED`: Share link has expired
- `SHARE_REVOKED`: Share has been revoked by owner
- `RECOVERY_CODE_INVALID`: Recovery code is invalid or already used
- `PASSWORD_TOO_WEAK`: Password does not meet strength requirements
- `PASSWORD_BREACHED`: Password found in breach database
- `VAULT_SALT_NOT_FOUND`: Vault salt not found for key derivation

## Testing Strategy

### Unit Testing

Unit tests will verify specific functionality of individual components:

**React Frontend Unit Tests:**
- Encryption/decryption functions with known test vectors
- Key derivation with known inputs and outputs
- Tag encryption produces consistent output for same input
- Error handling for invalid inputs
- API client request formatting

**Server-Side Unit Tests:**
- Lambda handler input validation
- DynamoDB query construction
- S3 presigned URL generation
- Error response formatting
- Authentication token validation

**Example Unit Tests:**
- Test that encrypting empty string produces valid ciphertext
- Test that invalid authentication token returns 401
- Test that presigned URL has correct expiration time
- Test that deleting non-existent media returns 404
- Test that pagination with page_size=10 returns at most 10 items
- Test that password shorter than 12 characters is rejected
- Test that password without special character is rejected
- Test that breached password is rejected
- Test that valid unused recovery code grants access
- Test that used recovery code is rejected
- Test that expired share returns 403
- Test that revoked share returns 403
- Test that HKDF derives different keys for different contexts
- Test that vault salt is unique for each vault
- Test that account password change does not affect vault keys
- Test that vault password change triggers re-encryption

### Property-Based Testing

Property-based testing will verify universal properties across many randomly generated inputs using **Hypothesis** for Python (server-side) and **fast-check** for TypeScript/JavaScript (client-side).

**Configuration:**
- Minimum 100 iterations per property test
- Shrinking enabled to find minimal failing examples
- Seed-based reproducibility for debugging

**Property Test Requirements:**
- Each property test must run at least 100 iterations with randomly generated inputs
- Each property test must be tagged with a comment referencing the design document property
- Tag format: `# Feature: cortex, Property {number}: {property_text}`
- Each correctness property must be implemented by a single property-based test

**Test Data Generators:**

*Media Content Generator:*
- Random binary data (1KB to 100MB)
- Various file sizes including edge cases
- Different content types (JPEG, PNG, MP4, etc.)

*Metadata Generator:*
- Random filenames (including special characters, Unicode)
- Random timestamps
- Random file sizes
- Random MIME types

*User Generator:*
- Random user IDs
- Multiple users for isolation testing
- Random authentication tokens

*Tag Generator:*
- Random tag strings (including Unicode, special characters)
- Empty tags, very long tags
- Duplicate tags

*Collection Generator:*
- Random collection names and descriptions
- Collections with 0 to 1000 media items
- Nested collection structures

*Password Generator:*
- Various password strengths
- Special characters, Unicode
- Very long passwords

*Notification Generator:*
- Random notification titles and bodies
- Various action URLs
- Different item types (TASK, EVENT)
- Random reminder times

*Device Generator:*
- Multiple devices per user
- Random device IDs and connection states
- Various device types (mobile, desktop, tablet)

**Property Test Examples:**

*Property 1 Test (Client-side encryption):*
```python
@given(media_content=binary(min_size=1, max_size=10_000_000),
       master_key=binary(min_size=32, max_size=32))
def test_client_encrypts_before_transmission(media_content, master_key):
    """
    Feature: cortex, Property 1: Client-side encryption before transmission
    """
    encrypted = encrypt_media(media_content, master_key)
    assert encrypted != media_content
    assert len(encrypted) > len(media_content)  # includes nonce and tag
```

*Property 4 Test (User isolation):*
```python
@given(user_a=user_generator(),
       user_b=user_generator(),
       media_item=media_generator())
def test_user_data_isolation(user_a, user_b, media_item):
    """
    Feature: cortex, Property 4: User data isolation
    """
    assume(user_a.id != user_b.id)
    
    # User A uploads media
    upload_media(user_a, media_item)
    
    # User B attempts to access User A's media
    with pytest.raises(AuthorizationError):
        download_media(user_b, media_item.id)
```

*Property 7 Test (Round-trip):*
```python
@given(media_content=binary(min_size=1, max_size=10_000_000),
       master_key=binary(min_size=32, max_size=32))
def test_upload_download_roundtrip(media_content, master_key):
    """
    Feature: cortex, Property 7: Upload and download round-trip preserves content
    """
    # Encrypt and upload
    encrypted = encrypt_media(media_content, master_key)
    media_id = upload_to_s3(encrypted)
    
    # Download and decrypt
    downloaded_encrypted = download_from_s3(media_id)
    decrypted = decrypt_media(downloaded_encrypted, master_key)
    
    assert decrypted == media_content
```

*Property 12 Test (Pagination):*
```python
@given(media_items=lists(media_generator(), min_size=0, max_size=1000),
       page_size=integers(min_value=1, max_value=100))
def test_pagination_consistency(media_items, page_size):
    """
    Feature: cortex, Property 12: Pagination consistency
    """
    # Upload all media items
    for item in media_items:
        upload_media(user, item)
    
    # Paginate through all results
    all_results = []
    next_token = None
    while True:
        response = list_media(user, page_size=page_size, next_token=next_token)
        all_results.extend(response.items)
        if not response.next_token:
            break
        next_token = response.next_token
    
    # Verify no duplicates and no omissions
    assert len(all_results) == len(media_items)
    assert set(item.id for item in all_results) == set(item.id for item in media_items)
```

*Property 17 Test (Key bundle round-trip):*
```python
@given(master_key=binary(min_size=32, max_size=32),
       password=text(min_size=12, max_size=128))
def test_key_bundle_roundtrip(master_key, password):
    """
    Feature: cortex, Property 17: Key bundle round-trip with password
    """
    # Create encrypted key bundle
    salt = generate_salt()
    password_key = derive_key_from_password(password, salt)
    encrypted_bundle = encrypt_key_bundle(master_key, password_key)
    
    # Store and retrieve
    store_key_bundle(user_id, encrypted_bundle, salt)
    retrieved_bundle, retrieved_salt = retrieve_key_bundle(user_id)
    
    # Decrypt with same password
    retrieved_password_key = derive_key_from_password(password, retrieved_salt)
    decrypted_master_key = decrypt_key_bundle(retrieved_bundle, retrieved_password_key)
    
    assert decrypted_master_key == master_key
```

*Property 30 Test (Notification privacy):*
```python
@given(notification_payload=notification_generator(),
       notification_key=binary(min_size=32, max_size=32))
def test_notification_content_privacy(notification_payload, notification_key):
    """
    Feature: cortex, Property 30: Notification content privacy
    """
    # React frontend encrypts notification payload
    encrypted_payload = encrypt_notification(notification_payload, notification_key)
    
    # Server stores and sends encrypted payload
    schedule_id = create_notification_schedule(encrypted_payload)
    sent_payload = send_notification(schedule_id)
    
    # Verify server never sees plaintext
    assert sent_payload == encrypted_payload
    assert sent_payload != notification_payload
    
    # React frontend decrypts on receipt
    decrypted = decrypt_notification(sent_payload, notification_key)
    assert decrypted == notification_payload
```

*Property 31 Test (Sync consistency):*
```python
@given(item=item_generator(),
       device_count=integers(min_value=2, max_value=5))
def test_cross_device_sync_consistency(item, device_count):
    """
    Feature: cortex, Property 31: Cross-device sync consistency
    """
    # Create item on device 1
    devices = [create_device() for _ in range(device_count)]
    create_item(devices[0], item)
    
    # All devices should eventually see the item
    for device in devices[1:]:
        sync_notification = receive_sync_notification(device)
        assert sync_notification.item_id == item.id
        
        # Fetch and decrypt full item
        fetched_item = fetch_item(device, item.id)
        decrypted_item = decrypt_item(fetched_item, device.keys)
        assert decrypted_item == item
    
    # Test conflict resolution
    item_v2 = update_item(devices[0], item, version=2)
    item_v3 = update_item(devices[1], item, version=3)
    
    # Last write wins (version 3)
    for device in devices:
        final_item = fetch_item(device, item.id)
        assert final_item.version == 3
```

### Integration Testing

Integration tests verify end-to-end workflows:

- Complete upload flow: authenticate → get presigned URL → upload to S3 → store metadata
- Complete download flow: authenticate → list media → get download URL → download from S3
- Multi-device flow: setup on device 1 → login on device 2 with vault password → access same media
- Collection management: create collection → add media → retrieve collection → delete collection
- Tag search: upload with tags → search by tag → verify results
- Error recovery: simulate S3 failure during upload → verify cleanup
- Two-password flow: change account password → verify vault access unchanged → change vault password → verify re-encryption
- Account recovery: use recovery code → reset account password → verify account access restored
- Vault recovery: use recovery key → reset vault password → verify vault data accessible
- File sharing: create share → access anonymously → verify file download
- Password-protected sharing: create protected share → enter password → verify access
- Share expiration: create time-limited share → wait for expiration → verify access denied
- Share revocation: create share → revoke → verify access denied
- Key rotation: trigger rotation → verify background re-encryption → verify data accessible with new keys
- Password validation: attempt weak password → verify rejection → attempt breached password → verify rejection
- Push notifications: create task with reminder → wait for time bucket → verify notification sent → verify client decrypts payload
- Real-time sync: modify item on device 1 → verify device 2 receives sync notification → verify device 2 fetches and decrypts update
- Conflict resolution: modify same item on two devices → verify last-write-wins based on version number

### Security Testing

- Penetration testing for authentication bypass attempts
- Verify encrypted data cannot be decrypted without keys
- Test that admin access cannot reveal plaintext data
- Verify presigned URLs expire correctly
- Test rate limiting and throttling
- Verify CORS configuration prevents unauthorized origins

### Performance Testing

- Upload performance with various file sizes
- Concurrent upload performance
- Query performance with large media collections (10K+ items)
- Pagination performance
- Tag search performance with many tags

## Implementation Notes

### Smithy Model Structure

The Smithy model will define:
- Service definition with metadata
- Operation definitions for all API endpoints
- Input/output structures
- Error definitions
- Authentication requirements
- Validation constraints

**API Documentation Generation:** The Smithy model serves as the single source of truth for API documentation. Smithy tooling will automatically generate:
- OpenAPI 3.0 specification for REST API documentation
- Client SDKs for multiple languages (TypeScript, Python, Swift, Kotlin)
- Server stubs for Lambda function handlers
- API reference documentation in HTML format

This ensures documentation stays synchronized with implementation and reduces manual documentation maintenance.

Example Smithy snippet:
```smithy
namespace com.cortex.backup

service CortexBackup {
    version: "2024-01-01"
    operations: [
        InitiateUpload
        CompleteUpload
        ListMedia
        GetMediaMetadata
        GetDownloadUrl
        DeleteMedia
        CreateCollection
        ListCollections
        // ... more operations
    ]
}

@http(method: "POST", uri: "/v1/media/upload/init")
operation InitiateUpload {
    input: InitiateUploadInput
    output: InitiateUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
    ]
}

structure InitiateUploadInput {
    @required
    encryptedMetadata: Blob
    
    @required
    sizeBytes: Long
    
    @required
    contentType: String
}

structure InitiateUploadOutput {
    @required
    mediaId: String
    
    @required
    uploadUrl: String
    
    @required
    expiresAt: Timestamp
}
```

### Key Derivation Parameters

**Argon2id Configuration:**
- Memory: 64 MB
- Iterations: 3
- Parallelism: 4
- Salt: 16 bytes (random, generated using cryptographically secure RNG)
- Output: 32 bytes (256-bit key)

These parameters provide strong protection against brute-force attacks while remaining performant on client devices.

**HKDF Configuration:**
- Hash function: SHA-256
- Input key material: Vault master key (256 bits)
- Salt: None (optional, not used)
- Info contexts for key derivation:
  - "cortex-kek-v1" → Key Encryption Key (KEK - wraps per-file DEKs)
  - "cortex-metadata-encryption-v1" → Metadata encryption key (common metadata)
  - "cortex-share-key-derivation-v1" → Share key derivation key (file sharing)
  - "cortex-notes-encryption-v1" → Notes encryption key (note content)
  - "cortex-tasks-encryption-v1" → Tasks encryption key (task content)
  - "cortex-events-encryption-v1" → Events encryption key (event content)
  - "cortex-notification-encryption-v1" → Notification encryption key (notification payloads)
  - "cortex-date-bucket-v1" → Date bucket key (deterministic date bucket HMAC)
- Output: 32 bytes per derived key (256 bits)

**Per-File DEK Generation:**
- Each media file gets a unique 256-bit DEK
- DEK generated using cryptographically secure random number generator (CSPRNG)
- DEK never derived from vault master key (ensures key isolation)
- DEK wrapped with KEK using ChaCha20-Poly1305 before storage
- Wrapped DEK format (65 bytes total, big-endian):

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 byte | Version | Format version (0x01) |
| 1 | 4 bytes | Timestamp | uint32_be, Unix epoch seconds (wrap creation time) |
| 5 | 12 bytes | Nonce | Random nonce for ChaCha20-Poly1305 |
| 17 | 32 bytes | Encrypted DEK | DEK encrypted with KEK |
| 49 | 16 bytes | Auth Tag | ChaCha20-Poly1305 authentication tag |

  The version byte enables forward-compatible format changes. The timestamp allows auditing when a DEK was wrapped. All multi-byte integers use big-endian (network byte order).

### Password Validation

**Strength Requirements:**
- Minimum length: 12 characters for account passwords, 16 characters for share passwords
- **Entropy-Based Validation**: Use zxcvbn or similar entropy estimator to calculate estimated entropy
- **Minimum Entropy**: Require minimum estimated entropy of 80 bits (for account, vault, and share passwords)
- Character class requirements (uppercase, lowercase, numbers, special characters) are secondary to entropy calculation
- Provide clear user feedback: "Password strength: X bits (minimum 80 required)" with actionable guidance
- No maximum length restriction
- Applied to account passwords, vault passwords, and share passwords

**Breach Detection:**
- Integration with Have I Been Pwned API (k-anonymity model)
- Client-side SHA-1 hash of password
- Send first 5 characters of hash to API
- Check full hash against returned list locally
- No plaintext password transmitted
- Reject any password found in breach database

**Implementation:**
```typescript
async function validatePassword(password: string): Promise<ValidationResult> {
  // Check strength requirements
  if (password.length < 12) return { valid: false, reason: 'TOO_SHORT' };
  if (!/[A-Z]/.test(password)) return { valid: false, reason: 'NO_UPPERCASE' };
  if (!/[a-z]/.test(password)) return { valid: false, reason: 'NO_LOWERCASE' };
  if (!/[0-9]/.test(password)) return { valid: false, reason: 'NO_NUMBER' };
  if (!/[^A-Za-z0-9]/.test(password)) return { valid: false, reason: 'NO_SPECIAL' };
  
  // Check breach database
  const sha1Hash = await sha1(password);
  const prefix = sha1Hash.substring(0, 5);
  const suffix = sha1Hash.substring(5);
  
  const response = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`);
  const hashes = await response.text();
  
  if (hashes.includes(suffix.toUpperCase())) {
    return { valid: false, reason: 'BREACHED' };
  }
  
  return { valid: true };
}
```

### Encryption Implementation Details

**ChaCha20-Poly1305:**
- Library: Web Crypto API (browser), cryptography (Python)
- Key size: 256 bits
- Nonce size: 96 bits (12 bytes)
- Tag size: 128 bits (16 bytes)
- Each encryption operation uses a fresh random nonce
- Fast, secure, and resistant to timing attacks

**Tag Encryption (Deterministic):**
- HMAC-SHA256 with metadata encryption key
- Consistent output for same tag enables search
- Tag normalized to lowercase before encryption
- Output: 32 bytes (256 bits)

### Account Recovery Implementation

**Recovery Code Generation:**
- 10 recovery codes generated per user account at signup
- Each code: 16 characters, alphanumeric, randomly generated
- Format: XXXX-XXXX-XXXX-XXXX (for readability)
- Codes hashed with SHA-256 before storage on server
- Displayed once to user with instructions to store securely offline

**Recovery Code Usage:**
- User enters recovery code during account recovery flow
- Client sends SHA-256 hash of code to server for validation
- Server checks hash against stored hashes
- If valid and unused, server marks code as used and grants access
- User prompted to set new account password
- Used codes cannot be reused

**Vault Recovery Key:**
- Separate from account recovery codes
- BIP39 mnemonic (12-24 words) derived from vault master key
- Enables vault password reset without re-encrypting data
- Never transmitted to or stored by server
- Displayed once at vault creation with secure storage guidance

### Key Rotation Implementation

**Rotation Trigger:**
- Automatic: 90 days since last rotation
- Manual: User-initiated via settings
- Client-side monitoring of key age

**Rotation Process (Envelope Encryption - Efficient):**
1. Generate new KEK from vault master key using HKDF with incremented version context (e.g., "cortex-kek-v2")
2. Query server for all wrapped DEKs in the vault (small metadata, not file content)
3. Process DEKs in batches (configurable batch size, default 100):
   a. Download batch of wrapped DEKs
   b. Unwrap each DEK with old KEK
   c. Re-wrap each DEK with new KEK
   d. Upload re-wrapped DEKs to server
   e. Report progress to UI
4. Update DynamoDB metadata with new KEK version for each item
5. Maintain old KEK for reading during transition
6. Update local key storage with new KEK version
7. Purge old KEK after all DEKs successfully re-wrapped

**Concurrent Rotation Prevention:**
- Only one key rotation can be in progress per vault at a time
- When rotation is initiated, the client acquires a rotation lock by performing a conditional write to the DynamoDB Vaults table:
  - ConditionExpression: `rotationState = :idle OR (rotationState = :inProgress AND rotationLockedAt < :expiry)`
  - Sets `rotationState = IN_PROGRESS` and `rotationLockedAt = now()`
- If a second device attempts rotation while one is in progress, the conditional write fails and the user is informed that rotation is already in progress on another device
- Rotation locks auto-expire after 7 days (rotationLockedAt + 7 days) to prevent permanent lock-out from crashed clients
- When rotation completes or is rolled back, the client sets `rotationState = IDLE` and clears `rotationLockedAt`

**Key Rotation Benefits with Envelope Encryption:**
- **Bandwidth Efficient**: Only download/upload wrapped DEKs (~60 bytes each), not file content
- **Fast**: Re-wrapping 10,000 DEKs takes seconds, not hours
- **Resumable**: Can pause and resume rotation for large vaults
- **No S3 Operations**: File content in S3 remains unchanged
- **Progress Tracking**: UI shows percentage complete

**Dual-KEK Access Period (REQ-20):**
- During rotation, client maintains both old and new KEKs
- **Reading Existing Files**: Client checks DEK version and uses matching KEK for unwrapping
  - DEKs with old version unwrapped with old KEK
  - DEKs with new version unwrapped with new KEK
- **New File Uploads**: All new file uploads during rotation use NEW KEK for wrapping DEKs
- **In-Progress Downloads**: Downloads that started before rotation complete using the KEK version that matches the file's DEK version
- **Share Creation**: Share creation is BLOCKED during active rotation
  - UI displays "Key rotation in progress, please wait to create shares"
  - Prevents shares from being created with old KEK
  - Ensures all shares use the new KEK version for consistency
- **Re-wrapped DEKs**: DEKs that have been re-wrapped use new KEK
- Transition completes when all DEKs re-wrapped
- Old KEK securely zeroized and purged after successful completion

**Multipart Upload Handling During Rotation:**
- When a multipart upload is initiated during key rotation, the React frontend captures the current KEK version at upload initiation time
- The captured KEK version is stored in the upload session context (in-memory)
- When the multipart upload completes, the React frontend verifies the captured KEK version is still available before wrapping the DEK
- If the captured KEK version is no longer available (e.g., due to rotation rollback), the upload is aborted and the user is prompted to retry
- This prevents a scenario where a DEK is wrapped with a KEK version that has been rolled back, which would make the file inaccessible

**Batch Processing:**
```typescript
interface KeyRotationProgress {
  totalItems: number;
  processedItems: number;
  lastProcessedSortKey: string; // cursor-based progress tracking to avoid storing all IDs
  failedItems: string[]; // item IDs that failed (only failures tracked, not successes)
  status: 'in_progress' | 'paused' | 'completed' | 'failed';
  startedAt: Date;
  lastUpdatedAt: Date;
}

// Note: Use navigator.storage.estimate() to check available IndexedDB quota
// before starting rotation. Cursor-based tracking ensures progress state stays
// small regardless of vault size (avoids storing 1M+ item IDs).

async function rotateKeys(vaultId: string, batchSize: number = 100): Promise<void> {
  const newKek = deriveKek(vaultMasterKey, newVersion);
  const oldKek = deriveKek(vaultMasterKey, currentVersion);
  
  let nextToken: string | undefined;
  do {
    // Fetch batch of wrapped DEKs
    const batch = await fetchWrappedDeks(vaultId, batchSize, nextToken);
    
    // Re-wrap each DEK (idempotent via conditional update)
    for (const item of batch.items) {
      const dek = unwrapDek(item.wrappedDek, oldKek);
      const newWrappedDek = wrapDek(dek, newKek);
      try {
        // Conditional update ensures idempotency: only update if dekVersion still matches old version
        await updateWrappedDek(item.itemId, newWrappedDek, newVersion, {
          conditionExpression: 'dekVersion = :oldVersion',
          expressionValues: { ':oldVersion': currentVersion }
        });
      } catch (e) {
        if (e.code === 'ConditionalCheckFailedException') {
          // DEK already re-wrapped (e.g., by a retry), skip and continue
          continue;
        }
        throw e;
      }
    }
    
    nextToken = batch.nextToken;
    reportProgress(batch.items.length);
  } while (nextToken);
  
  // Update local key storage
  updateLocalKeyVersion(newVersion);
}
```

### File Sharing Implementation

**Share Design Principle:** No keys or wrapped keys are ever stored on the server. All key material is embedded in the share URL, ensuring true zero-knowledge sharing.

**Password-Required Sharing:**
- All shares require a password (no anonymous/passwordless shares)
- Password is used to derive a share encryption key via Argon2id
- The file's DEK is wrapped with the password-derived key
- Password-wrapped DEK is embedded in the share URL (not stored on server)

**Share Key Derivation:**
- User provides share password
- Generate random share salt (16 bytes)
- Derive share encryption key: Argon2id(password, share_salt) → 256-bit key
- Share salt is embedded in URL (non-secret, needed for key derivation)

**Share Creation Flow:**
1. User initiates share for a media file and provides share password
2. React frontend retrieves wrapped DEK from server
3. React frontend unwraps DEK using vault's KEK
4. React frontend generates random share salt
5. React frontend derives share encryption key from password + salt using Argon2id
6. React frontend wraps DEK with share encryption key (password-wrapped DEK)
7. React frontend derives HMAC key from share password using HKDF with context "cortex-share-hmac-v1"
8. React frontend computes HMAC-SHA256 over share metadata (shareId, expiration timestamp) using HMAC key
9. React frontend creates share URL with embedded password-wrapped DEK, salt, and HMAC
10. Server stores only share metadata (expiration, access count) - NO keys or wrapped keys

**Share URL Format:**
```
https://cortex.example.com/share/{shareId}#{base64(salt)}:{base64(passwordWrappedDek)}:{base64(hmac)}
```
- Fragment (#) ensures key material never sent to server
- Salt needed for recipient to derive same share encryption key
- Password-wrapped DEK can only be unwrapped with correct password
- HMAC authenticates share metadata (shareId, expiration) to prevent tampering
- Share ID used to fetch share metadata (expiration, file location) from server

**Share Access Flow:**
1. Recipient opens share URL
2. React frontend extracts salt, password-wrapped DEK, and HMAC from URL fragment
3. React frontend prompts recipient for share password
4. React frontend derives share encryption key from password + salt using Argon2id
5. React frontend derives HMAC key from share password using HKDF with context "cortex-share-hmac-v1"
6. React frontend fetches share metadata (shareId, expiration) from server
7. React frontend computes HMAC-SHA256 over received share metadata using HMAC key
8. React frontend verifies computed HMAC matches HMAC from URL using constant-time comparison
9. If HMAC verification fails, display error indicating share metadata has been tampered with
10. React frontend unwraps DEK using share encryption key
11. If unwrapping fails (wrong password), display error and prompt again (with rate limiting)
12. React frontend fetches file metadata and presigned S3 URL from server
13. React frontend downloads encrypted file from S3
14. React frontend decrypts file using unwrapped DEK
15. React frontend overwrites DEK buffer with zeros before dereferencing

**Server-Side Share Storage (Minimal):**
```typescript
interface StoredShare {
  shareId: string;
  itemId: string;
  vaultId: string;
  userId: string;
  createdAt: number;
  expiresAt?: number;
  accessCount: number;
  lastAccessedAt?: number;
  isRevoked: boolean;
  // NO keys, NO wrapped keys, NO salt stored on server
}
```

**Benefits of Password-Required Sharing:**
- **True Zero-Knowledge**: Server never sees any key material
- **Password Protection**: Only recipients with password can access
- **No Server Key Storage**: All cryptographic material in URL
- **Revocation**: Server can block access by marking share as revoked
- **Expiration**: Server enforces time-based expiration

**Share Revocation:**
- Owner can revoke share at any time
- Server marks share as revoked in database
- Server rejects all access attempts for revoked shares
- URL still contains key material but server blocks file access
- Original file and vault-wrapped DEK remain unaffected

**Share Expiration (Optional):**
- Expiration is optional - shares can be created without expiration
- If set, server stores expiration timestamp
- Server validates expiration on each access attempt
- Expired shares return 403 error
- Client displays expiration time to share creator (if set)

**Password Attempt Rate Limiting:**
- **Server-side rate limiting** (primary defense): Maximum 5 password attempts per IP address per share ID per hour
- Server returns HTTP 429 (Too Many Requests) with Retry-After header when limit exceeded
- Server logs rate limit violations for security monitoring
- **Client-side rate limiting** (additional layer): Maximum 5 password attempts per minute per share
- Exponential backoff after 3 failed attempts (1s, 2s, 4s, 8s...)
- Generic error messages to prevent share enumeration ("Invalid password" not "Share not found")

**Security Considerations:**
- Share password **requires** minimum 16+ characters with uppercase, lowercase, numbers, and special characters (minimum 80 bits entropy)
- React frontend validates password entropy before allowing share creation
- **Entropy validation timing**: Password entropy is validated at share creation time only. When recipients access a share, the password is used to derive the share encryption key without re-validating entropy. This prevents zxcvbn dictionary updates from retroactively blocking access to previously-created shares. The entropy check is a creation-time gate, not an access-time gate.
- Argon2id parameters for share key derivation: 64MB memory, 3 iterations, 4 parallelism
- HMAC-SHA256 over share metadata (shareId, expiration) prevents metadata tampering attacks
- Share URLs should be transmitted securely (HTTPS, encrypted messaging)
- Recipients should be warned not to share URLs publicly
- Alternative share access method: Enter share ID and password separately (for truncated URLs)
- Share URLs should NOT be shortened using URL shorteners (leaks share existence to third parties)

### Push Notification Implementation

**Notification Scheduling:**
- React frontend creates task/event with reminder time
- React frontend encrypts notification payload (title, body, action URL) using notification encryption key
- React frontend encrypts exact reminder time using notification encryption key
- React frontend generates plaintext time bucket (15-minute window) for server queries
- React frontend sends encrypted payload, encrypted exact time, time bucket, and encrypted device tokens to server
- Server stores in Notification Schedules table

**Notification Delivery:**
- EventBridge triggers Lambda function every 5 minutes
- Lambda queries Notification Schedules table: `status = PENDING AND timeBucket <= now + 15min`
- For each matching schedule, Lambda sends push notification via AWS SNS
- SNS payload contains encrypted notification data
- Lambda marks schedule as SENT with sentAt timestamp
- React frontend receives push notification, decrypts payload, displays to user

**Notification Delivery Failure Handling:**
- **Transient failures** (network errors, SNS throttling, temporary service unavailability):
  - Retry up to 3 times with exponential backoff: 5 minutes, 15 minutes, 45 minutes
  - Schedule status transitions: PENDING → RETRY_1 → RETRY_2 → RETRY_3 → DEAD_LETTER
  - Each retry is triggered by the next EventBridge invocation that finds the schedule at the appropriate retry time
- **Permanent failures** (SNS EndpointDisabled, InvalidParameter, expired device tokens):
  - Do NOT retry - mark the device token as invalid immediately
  - Remove invalid device token from future notification deliveries
  - Log the permanent failure for monitoring
- **Dead-letter handling**:
  - After 3 failed retry attempts, move notification to DEAD_LETTER status
  - Store failure reason and last attempt timestamp
  - On next app access, the React frontend queries for dead-letter notifications and displays a summary to the user (e.g., "3 reminders could not be delivered while you were offline")
- **Failure classification**: Lambda notification handler inspects SNS response codes to distinguish transient from permanent failures before deciding retry strategy

**Device Token Management:**
- React frontend registers device token (encrypted with metadata encryption key) via API
- Multiple device tokens per user supported (phone, tablet, desktop)
- Device tokens stored encrypted in Notification Schedules table
- React frontend can unregister device tokens when no longer needed

**Recurring Event Notification Scheduling:**
- When a user creates a recurring task or event with a reminder, the React frontend expands the recurrence rule into individual notification schedules using a lazy expansion strategy
- **90-day expansion window**: The React frontend generates individual notification schedules for the next 90 days from the current date
- **7-day refresh threshold**: When the current date is within 7 days of the end of the pre-generated window, the React frontend generates the next batch of notification schedules (extending another 90 days)
- **Modification handling**: When a recurring event is modified, the React frontend cancels all future notification schedules (status = CANCELLED) and regenerates them based on the updated recurrence rule
- **Deletion handling**: When a recurring event is deleted, the React frontend cancels all associated future notification schedules
- Each expanded notification schedule is a standard entry in the Notification Schedules table with its own encrypted payload and time bucket
- The recurrence rule itself is stored as part of the encrypted item content (task or event), not in the notification schedule

**Privacy Guarantees:**
- Server never sees plaintext notification content
- Server only knows notifications exist in 15-minute windows
- Exact reminder times remain encrypted
- Device tokens stored encrypted

### Real-Time Sync Implementation

**WebSocket Connection Management:**
- React frontend establishes WebSocket connection via API Gateway WebSocket API
- Connection authenticated using SigV4 or JWT token
- Lambda stores connection metadata in WebSocket Connections table
- Connection includes: connectionId, userId, vaultId, connectedAt, lastPingAt
- React frontend sends periodic ping messages to keep connection alive
- Server responds with pong messages
- **Connection limits**: Maximum 10 concurrent WebSocket connections per vault
  - On new connection, Lambda queries the Connections table GSI for the vault's active connections
  - If the count reaches 10, the oldest connection (by connectedAt) is gracefully terminated with a close frame indicating the reason
  - Excessive connection attempts (>20 per hour per vault) are logged for security monitoring

**Sync Notification Broadcasting:**
- When item is modified (create, update, delete), API handler identifies affected vault
- Handler queries WebSocket Connections table for all connections to that vault
- Handler sends sync notification to each connection via API Gateway Management API
- Sync notification format:
```json
{
  "type": "ITEM_UPDATED",
  "itemId": "uuid",
  "itemType": "NOTE",
  "version": 5,
  "timestamp": "2026-01-15T14:30:00Z"
}
```
- Notification contains NO encrypted content, only metadata for fetching

**React Frontend Sync Handling:**
- React frontend receives sync notification via WebSocket
- React frontend compares version number with local cache
- If remote version > local version, React frontend fetches full encrypted item via REST API
- React frontend decrypts item and updates local cache
- React frontend displays update to user

**Conflict Resolution:**
- Last-write-wins based on version numbers
- Each item has version field that increments on every update
- When conflict detected, React frontend accepts higher version number
- React frontend can optionally show conflict warning to user
- Version numbers are monotonically increasing integers

**Connection Cleanup:**
- When React frontend disconnects, Lambda removes connection from WebSocket Connections table
- Stale connections (no ping for 10 minutes) automatically cleaned up
- Connection state is ephemeral, no persistent data stored

### S3 Bucket Policies

Bucket policy enforces:
- Encryption in transit (HTTPS only)
- Server-side encryption (AES-256)
- No public access
- Access only via presigned URLs or IAM roles
- Lifecycle policies for cost optimization

### DynamoDB Capacity Planning

**Provisioned Capacity (initial):**
- Read: 5 RCU (auto-scaling enabled)
- Write: 5 WCU (auto-scaling enabled)
- Auto-scaling target: 70% utilization
- Max capacity: 100 RCU/WCU

**On-Demand Option:**
- Consider on-demand billing for unpredictable workloads
- No capacity planning required
- Pay per request

### Monitoring and Observability

**CloudWatch Metrics:**
- Lambda invocation count, duration, errors
- API Gateway request count, latency, 4xx/5xx errors
- DynamoDB consumed capacity, throttled requests
- S3 request count, bytes uploaded/downloaded

**CloudWatch Logs:**
- Lambda function logs (sanitized, no plaintext data)
- API Gateway access logs (exclude request/response bodies containing encrypted data)
- Error logs with request IDs for debugging
- Log sanitization policy: Never log encrypted payloads, user passwords, keys, or recovery keys
- Logged data limited to: user IDs, timestamps, operation types, error codes, performance metrics

**Alarms:**
- Lambda error rate > 1%
- API Gateway 5xx error rate > 0.5%
- DynamoDB throttling events
- S3 4xx error rate > 5%

**X-Ray Tracing:**
- End-to-end request tracing
- Performance bottleneck identification
- Error analysis

### Cost Optimization

**S3:**
- Lifecycle policies: transition to S3 Glacier after 90 days of no access
- Intelligent-Tiering for automatic cost optimization
- Delete incomplete multipart uploads after 7 days

**DynamoDB:**
- Use on-demand billing for unpredictable workloads
- Or use provisioned capacity with auto-scaling
- Enable point-in-time recovery for data protection

**Lambda:**
- Optimize memory allocation for cost/performance balance
- Use ARM-based Graviton2 processors for 20% cost savings
- Set appropriate timeout values to avoid unnecessary charges

**Data Transfer:**
- Use CloudFront for global distribution (optional)
- S3 Transfer Acceleration for faster uploads (optional)
- Consider data transfer costs for large files

### Deployment Strategy

**Infrastructure as Code:**
- Use AWS CDK or Terraform for infrastructure definition
- Version control all infrastructure code
- Separate environments: dev, staging, production

**CI/CD Pipeline:**
- Automated testing on every commit
- Automated deployment to dev environment
- Manual approval for staging/production
- Blue-green deployment for zero-downtime updates

**Database Migrations:**
- DynamoDB schema changes via CloudFormation
- Backward-compatible changes only
- Test migrations in staging first

### Security Hardening

**Lambda Security:**
- Principle of least privilege for IAM roles
- No hardcoded credentials
- Environment variables for configuration
- VPC deployment for additional isolation (optional)

**API Gateway Security:**
- WAF rules for common attack patterns
- Rate limiting per user
- Request validation
- CORS configuration

**Secrets Management:**
- AWS Secrets Manager for sensitive configuration
- Automatic secret rotation
- Encryption at rest

**Audit Logging:**
- CloudTrail for AWS API calls
- Log all authentication attempts
- Log all data access (without plaintext data)
- Retain logs for compliance requirements
