# Cortex Backup System - Design Document

## Overview

Cortex is a zero-knowledge cloud backup system for photos and videos built on AWS serverless infrastructure. The system implements end-to-end encryption where all sensitive data (media content, metadata, tags, collections, and organizational structure) is encrypted client-side before transmission. The server operates exclusively on encrypted data, ensuring that neither service administrators nor the infrastructure provider can access user content.

The architecture follows AWS best practices using Lambda for compute, API Gateway for API management, DynamoDB for metadata storage, S3 for object storage, and Cognito for authentication. The Smithy model defines the service contract, enabling type-safe API definitions and automatic SDK generation.

### Key Design Principles

1. **Zero-Knowledge Architecture**: Server never has access to plaintext data or encryption keys
2. **Client-Side Encryption**: All encryption/decryption happens on the client device
3. **Direct S3 Access**: Presigned URLs enable fast uploads/downloads bypassing Lambda
4. **Serverless Scalability**: Auto-scaling infrastructure with pay-per-use pricing
5. **Multi-Device Support**: Password-based key derivation enables access from any device
6. **Privacy-Preserving Search**: Encrypted tags and collections enable organization without exposing content

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Application                      │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Encryption     │  │ Image        │  │ Key Management  │ │
│  │ Engine         │  │ Recognition  │  │                 │ │
│  └────────────────┘  └──────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (SigV4)
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
│                    (Smithy Model Defined)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Lambda   │  │ Lambda   │  │ Lambda   │
        │ Upload   │  │ Metadata │  │ Download │
        └──────────┘  └──────────┘  └──────────┘
                │             │             │
                ▼             ▼             │
        ┌──────────────────────────┐       │
        │      DynamoDB            │       │
        │  (Encrypted Metadata)    │       │
        └──────────────────────────┘       │
                                            │
                ┌───────────────────────────┘
                │
                ▼
        ┌──────────────────────────┐
        │         S3 Bucket        │
        │  (Encrypted Media Files) │
        │  (Server-Side Encryption)│
        └──────────────────────────┘
```

### Component Interaction Flow

**Upload Flow:**
1. Client encrypts media and metadata locally
2. Client requests upload URL from API Gateway (authenticated via SigV4)
3. Lambda generates presigned S3 URL with scoped permissions
4. Client uploads encrypted media directly to S3
5. Client sends encrypted metadata to Lambda
6. Lambda stores encrypted metadata in DynamoDB

**Download Flow:**
1. Client requests media list from API Gateway
2. Lambda queries DynamoDB for user's encrypted metadata
3. Client decrypts metadata locally
4. Client requests download URL for specific media
5. Lambda generates presigned S3 URL
6. Client downloads encrypted media directly from S3
7. Client decrypts media locally

**Multi-Device Flow:**
1. New device: User enters password
2. Client derives key from password using Argon2id
3. Client retrieves encrypted key bundle from DynamoDB
4. Client decrypts key bundle to obtain master key
5. Client can now decrypt all user's media and metadata

**Recovery Key Flow:**
1. Initial setup: Client generates recovery key (BIP39 mnemonic format)
2. Client displays recovery key to user with instructions to store securely offline
3. User confirms they have saved the recovery key before proceeding
4. Password forgotten: User initiates recovery process
5. User enters recovery key for authentication
6. Client validates recovery key against stored hash
7. Upon successful validation, user sets new password
8. Client re-encrypts key bundle with new password-derived key
9. Client updates encrypted key bundle in DynamoDB

## Components and Interfaces

### 1. Client Application

**Responsibilities:**
- Generate and manage encryption keys
- Encrypt/decrypt all user data before transmission/after receipt
- Perform local image recognition for tagging
- Derive keys from user passwords
- Manage encrypted key bundles
- Coordinate concurrent uploads for improved throughput (configurable based on network conditions)

**Key Modules:**

**Encryption Engine:**
- Algorithm: AES-256-GCM for symmetric encryption
- Key derivation: Argon2id for password-to-key derivation
- Random IV generation for each encryption operation
- Authenticated encryption to prevent tampering

**Key Management:**
- Master key generation (256-bit random key)
- Password-based key derivation (Argon2id with salt)
- Key bundle encryption/decryption
- Recovery key generation (BIP39 mnemonic or similar)
- Recovery key display and secure storage guidance for users
- Recovery key validation during password reset flow

**Image Recognition:**
- Local ML model (e.g., TensorFlow Lite for mobile, Core ML for iOS, ONNX Runtime for desktop)
- Offline tag generation (no network requests during recognition)
- Privacy-preserving (no data sent to external services or cloud APIs)
- Model runs entirely on-device before encryption
- Generated tags are encrypted before any transmission
- Recommended models: MobileNet, EfficientNet (optimized for on-device inference)

### 2. API Gateway

**Responsibilities:**
- Expose RESTful API endpoints
- Validate SigV4 signatures
- Route requests to appropriate Lambda functions
- Rate limiting and throttling
- API versioning

**Endpoints (defined in Smithy model):**

**API Versioning Strategy:** The API uses URI versioning (e.g., `/v1/media/list`) to support backward-compatible evolution. The current version is v1. Breaking changes will result in a new version (v2), while non-breaking changes can be added to existing versions.

```
POST   /v1/auth/login              - Initiate authentication
POST   /v1/auth/refresh            - Refresh credentials

POST   /v1/media/upload/init       - Initialize upload, get presigned URL
POST   /v1/media/upload/complete   - Mark upload complete, store metadata
GET    /v1/media/list              - List user's media (paginated)
GET    /v1/media/{id}              - Get media metadata
GET    /v1/media/{id}/download     - Get presigned download URL
DELETE /v1/media/{id}              - Delete media item

POST   /v1/collections             - Create collection
GET    /v1/collections             - List collections
GET    /v1/collections/{id}        - Get collection details
PUT    /v1/collections/{id}        - Update collection
DELETE /v1/collections/{id}        - Delete collection
POST   /v1/collections/{id}/media  - Add media to collection
DELETE /v1/collections/{id}/media/{mediaId} - Remove media from collection

GET    /v1/tags/search             - Search by encrypted tag
POST   /v1/keys/bundle             - Store encrypted key bundle
GET    /v1/keys/bundle             - Retrieve encrypted key bundle
PUT    /v1/keys/bundle             - Update encrypted key bundle
```

### 3. Lambda Functions

**Implementation Language:** All Lambda functions are implemented in Python 3.11+ for consistency, performance, and rich library ecosystem support.

**Upload Handler:**
- Extracts user identity from API Gateway authorizer context
- Validates user permissions (user can only upload to their own namespace)
- Generates presigned S3 PUT URL scoped to user's S3 prefix
- For files exceeding 100MB, configures multipart upload with minimum 5MB part size
- Stores encrypted metadata in DynamoDB with user isolation
- Links media to user account using userId from Cognito token

**Metadata Handler:**
- Extracts user identity from API Gateway authorizer context
- Queries DynamoDB for user's encrypted metadata (enforces userId filter)
- Supports pagination and filtering
- Returns encrypted data without decryption
- Manages collections and media-collection associations
- Ensures all operations are scoped to the authenticated user

**Download Handler:**
- Extracts user identity from API Gateway authorizer context
- Queries DynamoDB to verify user owns requested media
- Generates presigned S3 GET URL scoped to the specific object
- Returns time-limited download URL (15 minutes)
- Rejects requests if user doesn't own the media

**Collection Handler:**
- CRUD operations for collections
- Manages media-collection associations
- Supports multi-collection membership

**Key Bundle Handler:**
- Stores/retrieves encrypted key bundles
- No access to plaintext keys
- One bundle per user

**Tag Search Handler:**
- Searches encrypted tags using exact match
- Returns matching media items
- No plaintext tag access

### 4. DynamoDB Schema

**Users Table:**
```
PK: USER#{userId}
SK: PROFILE
Attributes:
  - userId (string)
  - cognitoId (string)
  - createdAt (timestamp)
  - encryptedKeyBundle (binary) - encrypted master key
  - keyBundleSalt (binary) - salt for key derivation
  - recoveryKeyHash (string) - hash of recovery key for validation
```

**Media Table:**
```
PK: USER#{userId}
SK: MEDIA#{mediaId}
Attributes:
  - mediaId (string)
  - userId (string)
  - s3Key (string) - path in S3
  - encryptedMetadata (binary) - encrypted filename, size, type, etc.
  - encryptedTags (list<binary>) - list of encrypted tags
  - uploadedAt (timestamp) - for sorting/filtering
  - sizeBytes (number) - for storage calculations
  
GSI1:
  PK: USER#{userId}#TAG#{encryptedTag}
  SK: MEDIA#{mediaId}
  - Enables tag-based queries
```

**Collections Table:**
```
PK: USER#{userId}
SK: COLLECTION#{collectionId}
Attributes:
  - collectionId (string)
  - userId (string)
  - encryptedMetadata (binary) - encrypted name, description
  - createdAt (timestamp)
  - updatedAt (timestamp)
  - itemCount (number)
```

**Media-Collection Association Table:**
```
PK: COLLECTION#{collectionId}
SK: MEDIA#{mediaId}
Attributes:
  - collectionId (string)
  - mediaId (string)
  - userId (string)
  - addedAt (timestamp)

GSI1:
  PK: MEDIA#{mediaId}
  SK: COLLECTION#{collectionId}
  - Enables reverse lookup (which collections contain this media)
```

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
users/{userId}/media/{mediaId}/{timestamp}-{random}
```

**Presigned URL Configuration:**
- Upload URLs: 15-minute expiration, PUT only
- Download URLs: 15-minute expiration, GET only
- Scoped to specific object key
- Content-type restrictions on upload

### 6. Cognito Configuration

**User Pool:**
- Email/password authentication
- MFA optional (recommended)
- Password policy: minimum 12 characters, complexity requirements
- Account recovery via email

**Identity Pool:**
- Federated identities for OIDC support
- Role-based access control
- Scoped IAM policies per user

**IAM Policy Template (per user):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::cortex-media-bucket/users/${cognito-identity.amazonaws.com:sub}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["execute-api:Invoke"],
      "Resource": "arn:aws:execute-api:region:account:api-id/*/POST|GET|PUT|DELETE/*"
    }
  ]
}
```

**Note:** Users only have direct S3 access for uploading/downloading via presigned URLs (scoped to their own prefix). All DynamoDB operations are performed by Lambda functions on behalf of the user. The API Gateway validates the user's identity via SigV4 and passes the user context to Lambda, which enforces access control.

## Data Models

### Client-Side Data Models

**Media Item (Plaintext - Client Only):**
```typescript
interface MediaItem {
  id: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  width?: number;
  height?: number;
  duration?: number; // for videos
  capturedAt?: Date;
  uploadedAt: Date;
  tags: string[];
  collections: string[];
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
  coverMediaId?: string;
}
```

**Encryption Key Bundle (Client):**
```typescript
interface KeyBundle {
  masterKey: Uint8Array; // 256-bit AES key
  version: number; // for key rotation
  createdAt: Date;
}

interface EncryptedKeyBundle {
  encryptedData: Uint8Array; // encrypted KeyBundle
  salt: Uint8Array; // for password derivation
  nonce: Uint8Array; // for AES-GCM
  version: number;
}
```

### Server-Side Data Models (All Encrypted)

**Stored Media Metadata:**
```typescript
interface StoredMediaMetadata {
  userId: string;
  mediaId: string;
  s3Key: string;
  encryptedMetadata: Uint8Array; // encrypted MediaItem
  encryptedTags: Uint8Array[]; // each tag encrypted separately
  uploadedAt: number; // timestamp for sorting
  sizeBytes: number; // for storage tracking
}
```

**Stored Collection:**
```typescript
interface StoredCollection {
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

Using AES-256-GCM:
- Nonce: 96-bit random value (unique per encryption)
- Auth tag: 128-bit authentication tag
- Algorithm: AES-256-GCM
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

## Cor
rectness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Client-side encryption before transmission

*For any* user data (media content, metadata, tags, or collection information), when the client prepares to send it to the server, the transmitted data must be encrypted and must not match the plaintext original.

**Validates: Requirements 1.1, 2.1, 11.2, 12.1, 13.1**

### Property 2: Server storage preserves encryption

*For any* encrypted data received by the server, the data stored in S3 or DynamoDB must exactly match the encrypted data that was transmitted, with no decryption or re-encryption occurring.

**Validates: Requirements 1.2, 2.2, 11.3, 12.2**

### Property 3: Server responses contain only encrypted data

*For any* API response containing user data (media lists, metadata, collections, tags), all sensitive fields in the response must be encrypted and must not contain plaintext user information.

**Validates: Requirements 2.3, 10.3, 12.4, 13.5**

### Property 4: User data isolation

*For any* two distinct users A and B, user A must not be able to access, modify, or delete any resources (media, metadata, collections) belonging to user B, regardless of the API operation attempted.

**Validates: Requirements 2.4, 3.3, 4.3, 5.1**

### Property 5: Referential integrity between S3 and DynamoDB

*For any* media item, if metadata exists in DynamoDB, then the corresponding encrypted object must exist in S3, and if an encrypted object exists in S3, then corresponding metadata must exist in DynamoDB.

**Validates: Requirements 2.5**

### Property 6: Encryption keys never transmitted to server

*For any* API request or response in the system, the plaintext master key, password-derived keys, or recovery keys must never appear in the request/response payload, headers, or logs.

**Validates: Requirements 3.6, 9.1, 9.3, 15.5**

### Property 7: Upload and download round-trip preserves content

*For any* media item, uploading the encrypted media and then downloading it must result in the same plaintext content after client-side decryption (encryption and decryption are inverse operations).

**Validates: Requirements 4.2**

### Property 8: Deletion maintains referential integrity

*For any* media item deletion operation, either both the S3 object and DynamoDB metadata are successfully deleted, or both remain unchanged (atomic deletion or rollback on failure).

**Validates: Requirements 5.2, 5.3, 5.4**

### Property 9: API error responses are well-formed

*For any* API error condition (authentication failure, authorization failure, not found, etc.), the error response must include a valid HTTP status code, a structured error message, and must not leak sensitive information.

**Validates: Requirements 8.3**

### Property 10: All server-stored data is encrypted

*For any* data stored in S3 or DynamoDB (media files, metadata, tags, collections, key bundles), the stored representation must be encrypted and must not be readable without the user's encryption keys.

**Validates: Requirements 9.2, 9.5, 16.1, 16.2, 16.4**

### Property 11: Media list queries respect user boundaries

*For any* user's media list query (with any pagination, filtering, or sorting parameters), the results must contain only media items belonging to that user and must include all of that user's media items that match the query criteria.

**Validates: Requirements 10.1, 10.4**

### Property 12: Pagination consistency

*For any* paginated media list query, iterating through all pages must return each media item exactly once, with no duplicates and no omissions.

**Validates: Requirements 10.2**

### Property 13: Encrypted tag search functionality

*For any* tag search query, the client must encrypt the search term before sending, and the server must return all media items with matching encrypted tags without accessing plaintext tag values.

**Validates: Requirements 11.4, 11.5**

### Property 14: Media-collection many-to-many relationships

*For any* media item and any set of collections, the media item can be added to multiple collections simultaneously, and each collection correctly reports the media item as a member.

**Validates: Requirements 12.3, 12.5**

### Property 15: Collection deletion preserves media

*For any* collection containing media items, deleting the collection must remove all media-collection associations and the collection metadata, but all media items must remain accessible and unchanged.

**Validates: Requirements 13.3, 13.4**

### Property 16: Media removal from collection preserves media

*For any* media item in a collection, removing the media from the collection must delete only the association, leaving both the media item and the collection intact and accessible.

**Validates: Requirements 13.2**

### Property 17: Key bundle round-trip with password

*For any* master key and password, encrypting the master key to create a key bundle, storing it, retrieving it, and decrypting with the same password must return the original master key.

**Validates: Requirements 14.1, 14.5**

### Property 18: Recovery key enables password reset

*For any* user account with a recovery key, using the recovery key to authenticate must allow setting a new password, and the re-encrypted key bundle must decrypt with the new password to return the original master key.

**Validates: Requirements 15.3, 15.4**

### Property 19: Administrator cannot access plaintext data

*For any* data stored in the system (S3, DynamoDB, logs), an administrator with full AWS console access but without the user's password or keys must not be able to decrypt or determine the content, subject matter, or organizational structure of user data.

**Design Rationale:** This property is fundamental to the zero-knowledge architecture. All encryption happens client-side with keys that never leave the client. Even with full infrastructure access, administrators can only see:
- Encrypted binary blobs in S3
- Encrypted metadata in DynamoDB
- User IDs and timestamps (non-sensitive)
- System metrics and performance data

Administrators cannot determine:
- What media content depicts (photos of what, videos of what)
- Original filenames or descriptions
- Tag meanings or search terms
- Collection names or organizational structure
- Relationships between media items

**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5**

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

### Property-Based Testing

Property-based testing will verify universal properties across many randomly generated inputs using **Hypothesis** for Python (server-side) and **fast-check** for TypeScript/JavaScript (client-side).

**Configuration:**
- Minimum 100 iterations per property test
- Shrinking enabled to find minimal failing examples
- Seed-based reproducibility for debugging

**Property Test Requirements:**
- Each property test must run at least 100 iterations with randomly generated inputs
- Each property test must be tagged with a comment referencing the design document property
- Tag format: `# Feature: cortex-backup, Property {number}: {property_text}`
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

**Property Test Examples:**

*Property 1 Test (Client-side encryption):*
```python
@given(media_content=binary(min_size=1, max_size=10_000_000),
       master_key=binary(min_size=32, max_size=32))
def test_client_encrypts_before_transmission(media_content, master_key):
    """
    Feature: cortex-backup, Property 1: Client-side encryption before transmission
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
    Feature: cortex-backup, Property 4: User data isolation
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
    Feature: cortex-backup, Property 7: Upload and download round-trip preserves content
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
    Feature: cortex-backup, Property 12: Pagination consistency
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
    Feature: cortex-backup, Property 17: Key bundle round-trip with password
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

### Integration Testing

Integration tests verify end-to-end workflows:

- Complete upload flow: authenticate → get presigned URL → upload to S3 → store metadata
- Complete download flow: authenticate → list media → get download URL → download from S3
- Multi-device flow: setup on device 1 → login on device 2 → access same media
- Collection management: create collection → add media → retrieve collection → delete collection
- Tag search: upload with tags → search by tag → verify results
- Error recovery: simulate S3 failure during upload → verify cleanup

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
- Salt: 16 bytes (random, stored with key bundle)
- Output: 32 bytes (256-bit key)

These parameters provide strong protection against brute-force attacks while remaining performant on client devices.

### Encryption Implementation Details

**AES-256-GCM:**
- Library: Web Crypto API (browser), cryptography (Python)
- Key size: 256 bits
- Nonce size: 96 bits (12 bytes)
- Tag size: 128 bits (16 bytes)
- Each encryption operation uses a fresh random nonce

**Tag Encryption (Deterministic):**
- HMAC-SHA256 with master key
- Consistent output for same tag enables search
- Tag normalized to lowercase before encryption
- Output: 32 bytes (256 bits)

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
