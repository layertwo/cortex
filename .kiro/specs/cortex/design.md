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

### Key Design Principles

1. **True Zero-Knowledge Architecture**: Server never has access to plaintext data, encryption keys, or encrypted key bundles
2. **Two-Password Model**: Separate account password (authentication) and vault password (data encryption)
3. **Client-Side Encryption**: All encryption/decryption happens on the client device using ChaCha20-Poly1305
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
  Data Encryption Key    Metadata Encryption Key    Share Key Derivation Key    Notes/Tasks/Events/
  (media content)        (common metadata)          (file sharing)              Notification Keys
```

This separation provides:
- Flexibility to change account credentials without expensive re-encryption
- True zero-knowledge architecture (server never sees vault password or keys)
- Multi-device support (vault password + salt enables key derivation on any device)
- Independent recovery mechanisms for account access vs. data access

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Application                      │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Encryption     │  │ Content      │  │ Key Management  │ │
│  │ Engine         │  │ Analysis     │  │                 │ │
│  └────────────────┘  └──────────────┘  └─────────────────┘ │
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
1. Client encrypts item content and metadata locally using appropriate encryption key
2. Client requests API endpoint (authenticated via SigV4)
3. For media items: Lambda generates presigned S3 URL, client uploads directly to S3
4. For other items: Content stored inline in DynamoDB as encrypted blob
5. Client sends encrypted metadata to Lambda
6. Lambda stores encrypted metadata in Items table

**Item Retrieval Flow:**
1. Client requests item list from API Gateway
2. Lambda queries DynamoDB Items table for user's encrypted metadata
3. Client decrypts metadata locally
4. For media items: Client requests download URL, Lambda generates presigned S3 URL
5. Client downloads and decrypts content locally

**Notification Flow:**
1. Client creates task/event with reminder time
2. Client encrypts notification payload and exact time
3. Client generates time bucket (15-min window, plaintext)
4. Client sends notification schedule to Lambda
5. Lambda stores in Notification Schedules table
6. EventBridge triggers Lambda every 5 minutes
7. Lambda queries schedules with timeBucket <= now + 15min
8. Lambda sends push notifications via SNS with encrypted payloads
9. Client receives notification, decrypts payload, displays to user

**Multi-Device Flow:**
1. New device: User enters account password (authenticates with Cognito)
2. User enters vault password
3. Client retrieves vault salt from DynamoDB
4. Client derives vault master key from vault password + salt using Argon2id
5. Client derives data encryption key and metadata encryption key from vault master key using HKDF
6. Client stores derived keys encrypted locally on device
7. Client can now decrypt all user's files and metadata

**Vault Recovery Key Flow:**
1. Initial setup: Client generates vault recovery key derived from vault master key
2. Client displays recovery key to user once with instructions to store securely offline
3. User confirms they have saved the recovery key before proceeding
4. Vault password forgotten: User initiates recovery process
5. User enters vault recovery key
6. Client uses recovery key to re-derive the vault master key
7. Upon successful validation, user sets new vault password
8. Client continues using the same vault master key (no re-encryption needed)
9. Server never receives or stores the vault recovery key

## Components and Interfaces

### 1. Client Application

**Responsibilities:**
- Generate and manage vault encryption keys locally
- Encrypt/decrypt all user data before transmission/after receipt
- Perform optional local content analysis for tagging
- Derive vault master key from vault password + vault salt using Argon2id
- Derive data and metadata encryption keys from vault master key using HKDF
- Store derived keys encrypted locally on device only
- Coordinate concurrent uploads for improved throughput (configurable based on network conditions)
- Never transmit vault keys or vault password to server
- Manage account password separately from vault password
- Validate passwords against breach databases and enforce strength requirements
- Handle automatic vault key rotation every 90 days

**Key Modules:**

**Encryption Engine:**
- Algorithm: ChaCha20-Poly1305 for symmetric encryption (fast, secure, authenticated)
- Key derivation: Argon2id for vault password-to-key derivation (64MB memory, 3 iterations, 4 parallelism)
- HKDF for deriving multiple keys from vault master key
- Random nonce generation for each encryption operation
- Authenticated encryption to prevent tampering

**Key Management:**
- **Two-Password Architecture**: Separate account password (for AWS Cognito authentication) and vault password (for data encryption)
- **Vault Master Key Derivation**: Argon2id(vault_password, vault_salt) → 256-bit vault master key
- **Derived Key Generation**: HKDF used to derive multiple keys from vault master key:
  - Data encryption key (for media file content encryption)
  - Metadata encryption key (for metadata, tags, collections encryption)
  - Share key derivation key (for generating file share keys)
  - Notes encryption key (for note content encryption)
  - Tasks encryption key (for task content encryption)
  - Events encryption key (for event content encryption)
  - Notification encryption key (for notification payload encryption)
  - Date bucket key (for deterministic date bucket encryption via HMAC)
- **Local Key Storage**: Derived keys encrypted with device-specific key and stored locally only (never transmitted to server)
- **Vault Recovery Key**: Generated from vault master key, displayed once to user with secure offline storage guidance
- **Recovery Key Validation**: Enables vault password reset without re-encrypting data
- **Account Password Management**: Handled separately via AWS Cognito, can be changed without affecting vault encryption
- **Password Validation**: Enforces minimum 12 characters, complexity requirements (uppercase, lowercase, numbers, special characters), and breach database checking
- **Key Rotation**: Automatic vault key rotation every 90 days with background re-encryption

**Content Analysis (Optional):**
- Local ML model for image/video analysis (e.g., TensorFlow Lite for mobile, Core ML for iOS, ONNX Runtime for desktop)
- Offline tag generation (no network requests during analysis)
- Privacy-preserving (no data sent to external services or cloud APIs)
- Model runs entirely on-device before encryption
- Generated tags are encrypted before any transmission
- Recommended models: MobileNet, EfficientNet (optimized for on-device inference)
- Supports any file type, but analysis is optional and file-type specific

**Sharing Module:**
- Generate unique share keys for individual files (derived from share key derivation key)
- Create share URLs containing file ID and base64-encoded share key
- Support optional password protection (double-encrypt share key with password-derived key)
- Handle time-limited expiration for shares
- Enable share revocation
- Anonymous access to shared files (no authentication required)

**Key Rotation Module:**
- Monitor key age and trigger rotation after 90 days
- Generate new derived keys from vault master key using updated HKDF context
- Re-encrypt vault data in background with new keys
- Maintain dual-key access during transition period
- Update local encrypted key storage upon completion
- Minimize user disruption during rotation process

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
    - status (enum: PENDING, SENT, CANCELLED)
    - createdAt (number)
    - sentAt (number, optional)
  - GSI1 (Global notification processing): `PK: STATUS#{status}, SK: TIMEBUCKET#{timeBucket}`

**Additional Tables:**
- **Users Table** (`cortex-{env}-users`): `PK: USER#{userId}, SK: PROFILE`
- **Vaults Table** (`cortex-{env}-vaults`): `PK: USER#{userId}, SK: VAULT#{vaultId}`
- **Account Recovery Table** (`cortex-{env}-recovery`): `PK: USER#{userId}, SK: RECOVERY#{codeHash}`
- **Shares Table** (`cortex-{env}-shares`) - Anonymous access, security isolated: `PK: SHARE#{shareId}, SK: METADATA`
- **WebSocket Connections Table** (`cortex-{env}-connections`) - Real-time sync: `PK: CONNECTION#{connectionId}, SK: METADATA`
  - Attributes: connectionId, userId, vaultId, connectedAt, lastPingAt
  - GSI1: `PK: VAULT#{vaultId}, SK: CONNECTION#{connectionId}` (for broadcasting to all vault connections)

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
  
  // Existing keys
  dataEncryptionKey: Uint8Array; // derived from master key via HKDF
  metadataEncryptionKey: Uint8Array; // derived from master key via HKDF
  shareKeyDerivationKey: Uint8Array; // derived from master key via HKDF
  
  // NEW keys for productivity features
  notesEncryptionKey: Uint8Array; // derived from master key via HKDF
  tasksEncryptionKey: Uint8Array; // derived from master key via HKDF
  eventsEncryptionKey: Uint8Array; // derived from master key via HKDF
  notificationEncryptionKey: Uint8Array; // derived from master key via HKDF
  dateBucketKey: Uint8Array; // derived from master key via HKDF (for HMAC)
  
  version: number; // for key rotation
  createdAt: Date;
  lastRotatedAt: Date;
}

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
  status: 'PENDING' | 'SENT' | 'CANCELLED';
  createdAt: number;
  sentAt?: number;
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

*For any* user data (file content, metadata, tags, or collection information), when the client prepares to send it to the server, the transmitted data must be encrypted using ChaCha20-Poly1305 and must not match the plaintext original.

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

*For any* tag search query, the client must encrypt the search term before sending, and the server must return all files with matching encrypted tags without accessing plaintext tag values.

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

**Design Rationale:** This property is fundamental to the zero-knowledge architecture. All encryption happens client-side with keys that never leave the client. Even with full infrastructure access, administrators can only see:
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

### Property 22: Vault password change requires data re-encryption

*For any* vault, changing the vault password must result in deriving a new vault master key and re-encrypting all vault data with keys derived from the new master key.

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

*For any* vault undergoing automatic key rotation (after 90 days), all previously encrypted data must remain accessible during and after the rotation process, with new data encrypted using the new keys.

**Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5**

### Property 27: Vault salt uniqueness

*For any* two distinct vaults, their vault salts must be different, ensuring that the same vault password produces different vault master keys for different vaults.

**Validates: Requirements 22.4**

### Property 28: Generic item CRUD operations

*For any* item type (MEDIA, NOTE, TASK, EVENT), creating, reading, updating, and deleting items must work consistently regardless of type, with all sensitive data encrypted client-side before transmission.

**Validates: Requirement 24**

### Property 29: Date bucket privacy

*For any* task or event with a date, the server must only have access to the 15-minute time bucket, not the exact time, while the client can decrypt and access the exact time.

**Validates: Requirement 25**

### Property 30: Notification content privacy

*For any* notification, the server must send push notifications with encrypted payloads, and only the client can decrypt and display the notification content.

**Design Rationale:** Notifications are scheduled with encrypted payloads that include the notification title, body, and action URL. The server stores the encrypted payload and exact time (also encrypted), along with a plaintext time bucket for query efficiency. When EventBridge triggers the notification handler every 5 minutes, it queries for schedules with timeBucket <= now + 15min. The handler sends the encrypted payload via AWS SNS to registered device tokens. The client receives the notification, decrypts the payload locally, and displays it to the user. The server never has access to notification content, maintaining zero-knowledge architecture even for time-sensitive reminders.

**Validates: Requirement 26**

### Property 31: Cross-device sync consistency

*For any* item modified on one device, all other connected devices must eventually receive the update and converge to the same state after decryption.

**Design Rationale:** Real-time sync is implemented using WebSocket connections managed by API Gateway and Lambda. When a user modifies an item (create, update, delete), the API handler broadcasts a sync notification to all WebSocket connections for that vault. The notification contains only metadata: item ID, item type, version number, and timestamp. Connected devices receive the notification and fetch the full encrypted item data via REST API. Conflicts are resolved using last-write-wins based on version numbers stored in DynamoDB. Each item has a version field that increments on every update. When a conflict is detected (two devices modified the same item), the client compares version numbers and accepts the higher version. This ensures eventual consistency across all devices while maintaining zero-knowledge architecture (sync notifications never contain encrypted content).

**Validates: Requirement 27**

## Error Handling

### Client-Side Error Handling

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

**Client-Side Unit Tests:**
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
    # Client encrypts notification payload
    encrypted_payload = encrypt_notification(notification_payload, notification_key)
    
    # Server stores and sends encrypted payload
    schedule_id = create_notification_schedule(encrypted_payload)
    sent_payload = send_notification(schedule_id)
    
    # Verify server never sees plaintext
    assert sent_payload == encrypted_payload
    assert sent_payload != notification_payload
    
    # Client decrypts on receipt
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
  - "cortex-data-encryption-v1" → Data encryption key (media content)
  - "cortex-metadata-encryption-v1" → Metadata encryption key (common metadata)
  - "cortex-share-key-derivation-v1" → Share key derivation key (file sharing)
  - "cortex-notes-encryption-v1" → Notes encryption key (note content)
  - "cortex-tasks-encryption-v1" → Tasks encryption key (task content)
  - "cortex-events-encryption-v1" → Events encryption key (event content)
  - "cortex-notification-encryption-v1" → Notification encryption key (notification payloads)
  - "cortex-date-bucket-v1" → Date bucket key (deterministic date bucket HMAC)
- Output: 32 bytes per derived key (256 bits)

### Password Validation

**Strength Requirements:**
- Minimum length: 12 characters
- Must contain: uppercase letter, lowercase letter, number, special character
- No maximum length restriction
- Applied to both account passwords and vault passwords

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

**Rotation Process:**
1. Generate new HKDF context parameters (increment version)
2. Derive new data and metadata encryption keys from vault master key
3. Create background re-encryption queue with all vault files
4. Re-encrypt files in batches (configurable batch size)
5. Upload re-encrypted files to S3 with new keys
6. Update DynamoDB metadata with new key version
7. Maintain old keys for reading during transition
8. Delete old encrypted versions after successful re-encryption
9. Update local key storage with new key version

**Dual-Key Access Period:**
- During rotation, client maintains both old and new keys
- Old keys used for reading existing data
- New keys used for encrypting new data
- Transition completes when all data re-encrypted
- Old keys purged after successful completion

### File Sharing Implementation

**Share Key Generation:**
- Unique 256-bit share key per file
- Derived from share key derivation key + file ID using HKDF
- Share key encrypts file-specific metadata for recipient
- Share key embedded in share URL (base64-encoded)

**Share URL Format:**
```
https://cortex.example.com/share/{shareId}#{base64(shareKey)}
```
- Fragment (#) ensures share key never sent to server
- Client extracts share key from URL fragment
- Share ID used to fetch share metadata from server

**Password-Protected Shares:**
- User provides additional password for share
- Password-derived key (Argon2id) encrypts the share key
- Encrypted share key stored in URL instead of plaintext share key
- Recipient must enter password to decrypt share key
- Password never transmitted to server

**Share Expiration:**
- Server stores expiration timestamp
- Server validates expiration on each access attempt
- Expired shares return 403 error
- Client displays expiration time to share creator

**Share Revocation:**
- Owner can revoke share at any time
- Server marks share as revoked in database
- Revoked shares return 403 error
- Share key remains in URL but server blocks access

### Push Notification Implementation

**Notification Scheduling:**
- Client creates task/event with reminder time
- Client encrypts notification payload (title, body, action URL) using notification encryption key
- Client encrypts exact reminder time using notification encryption key
- Client generates plaintext time bucket (15-minute window) for server queries
- Client sends encrypted payload, encrypted exact time, time bucket, and encrypted device tokens to server
- Server stores in Notification Schedules table

**Notification Delivery:**
- EventBridge triggers Lambda function every 5 minutes
- Lambda queries Notification Schedules table: `status = PENDING AND timeBucket <= now + 15min`
- For each matching schedule, Lambda sends push notification via AWS SNS
- SNS payload contains encrypted notification data
- Lambda marks schedule as SENT with sentAt timestamp
- Client receives push notification, decrypts payload, displays to user

**Device Token Management:**
- Client registers device token (encrypted with metadata encryption key) via API
- Multiple device tokens per user supported (phone, tablet, desktop)
- Device tokens stored encrypted in Notification Schedules table
- Client can unregister device tokens when no longer needed

**Privacy Guarantees:**
- Server never sees plaintext notification content
- Server only knows notifications exist in 15-minute windows
- Exact reminder times remain encrypted
- Device tokens stored encrypted

### Real-Time Sync Implementation

**WebSocket Connection Management:**
- Client establishes WebSocket connection via API Gateway WebSocket API
- Connection authenticated using SigV4 or JWT token
- Lambda stores connection metadata in WebSocket Connections table
- Connection includes: connectionId, userId, vaultId, connectedAt, lastPingAt
- Client sends periodic ping messages to keep connection alive
- Server responds with pong messages

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

**Client Sync Handling:**
- Client receives sync notification via WebSocket
- Client compares version number with local cache
- If remote version > local version, client fetches full encrypted item via REST API
- Client decrypts item and updates local cache
- Client displays update to user

**Conflict Resolution:**
- Last-write-wins based on version numbers
- Each item has version field that increments on every update
- When conflict detected, client accepts higher version number
- Client can optionally show conflict warning to user
- Version numbers are monotonically increasing integers

**Connection Cleanup:**
- When client disconnects, Lambda removes connection from WebSocket Connections table
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
