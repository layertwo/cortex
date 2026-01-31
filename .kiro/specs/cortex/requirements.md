# Requirements Document

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for Cortex, a zero-knowledge cloud-based backup and storage system. It serves as the foundation for system design, implementation, and testing.

### 1.2 Scope

Cortex is a zero-knowledge cloud-based productivity suite that prioritizes user privacy through client-side encryption. The system runs on AWS infrastructure using serverless technologies (Lambda, API Gateway) and provides secure, encrypted storage where the service provider has no knowledge of the content being stored. Cortex enables users to safely store media files, notes, tasks, and calendar events while maintaining complete control over their data privacy through a vault-based architecture that separates account authentication from data encryption.

### 1.3 Intended Audience

This document is intended for:
- Software developers implementing the Cortex system
- Quality assurance engineers designing test cases
- System architects reviewing the design
- Product managers validating feature completeness
- Security auditors evaluating privacy guarantees

## 2. Glossary

- **Cortex System**: The complete cloud-based productivity suite including API, storage, and database components
- **React Frontend**: The React web application that users interact with to manage their items
- **Zero-Knowledge Architecture**: A design where the service provider cannot access or decrypt user data
- **Item**: A generic data object stored in a vault (media file, note, task, or event)
- **Item Type**: The category of an item (MEDIA, NOTE, TASK, EVENT)
- **Media Item**: A photo, video, or other file uploaded by a user to their vault
- **Note Item**: A text document with optional rich formatting and attachments
- **Task Item**: A to-do item with optional due date, priority, and reminder
- **Event Item**: A calendar entry with start time, end time, and optional recurrence
- **Encryption Key**: A cryptographic key generated and managed by the client for encrypting items
- **Metadata**: Information about items such as title, timestamps, and type-specific fields (stored encrypted)
- **User**: An authenticated individual using the Cortex System
- **Upload Session**: A temporary context for uploading one or more media items
- **S3 Bucket**: AWS Simple Storage Service container for storing encrypted media content
- **DynamoDB Table**: AWS NoSQL database for storing encrypted item metadata and user information
- **Lambda Function**: AWS serverless compute function handling API requests
- **API Gateway**: AWS service providing RESTful API endpoints
- **Smithy Model**: Interface definition language describing the API service contract
- **Multipart Upload**: S3 feature for uploading large files in chunks
- **Presigned URL**: Time-limited URL for direct S3 upload access
- **Tag**: A label or keyword associated with an item for organization and search
- **Content Analysis**: Optional client-side analysis to generate tags or metadata from item content
- **Encrypted Tag**: A tag that has been encrypted client-side before storage
- **Administrator**: A person with operational access to the Cortex System infrastructure
- **Collection**: A user-defined grouping of items such as a folder or category
- **Collection Metadata**: Information about a collection including name, description, and creation date
- **Item-Collection Association**: A relationship linking an item to one or more collections
- **Time Bucket**: A 15-minute time window used for privacy-preserving date queries (e.g., "2026-01-15T14:00")
- **Encrypted Date Bucket**: A deterministically encrypted time bucket for server-side queries
- **Notification Schedule**: A scheduled reminder for a task or event with encrypted payload
- **Notification Payload**: The encrypted content of a push notification (title, body, action)
- **Device Token**: An encrypted identifier for push notification delivery to a specific device
- **Push Notification**: A message sent to a user's device via AWS SNS when a reminder is due
- **OIDC**: OpenID Connect, an identity layer on top of OAuth 2.0 for authentication
- **Cognito**: AWS service for user authentication and authorization
- **SigV4**: AWS Signature Version 4, the signing process for authenticating AWS API requests
- **Scoped Credentials**: Temporary AWS credentials with limited permissions specific to a user's resources
- **Account Password**: The password used to authenticate with the Cortex System and access the user account
- **Vault Password**: A separate password used exclusively for encrypting and decrypting the vault's master key
- **Vault**: A logical container holding all of a user's encrypted items (media, notes, tasks, events), metadata, and collections
- **Vault Master Key**: The primary 256-bit encryption key derived from the vault password using Argon2id
- **Key Derivation**: The process of generating encryption keys from a password using Argon2id with specific parameters
- **HKDF**: HMAC-based Key Derivation Function used to derive multiple keys from the vault master key
- **Data Encryption Key**: A key derived from the vault master key specifically for encrypting media file content
- **Metadata Encryption Key**: A key derived from the vault master key specifically for encrypting metadata
- **Notes Encryption Key**: A key derived from the vault master key specifically for encrypting note content
- **Tasks Encryption Key**: A key derived from the vault master key specifically for encrypting task content
- **Events Encryption Key**: A key derived from the vault master key specifically for encrypting event content
- **Notification Encryption Key**: A key derived from the vault master key specifically for encrypting notification payloads
- **Date Bucket Key**: A key derived from the vault master key for deterministic date bucket encryption
- **Vault Salt**: A unique random value per vault stored on server for vault key derivation
- **Account Salt**: A unique random value per user account stored on server for authentication key derivation
- **Argon2id**: A memory-hard key derivation function resistant to GPU and side-channel attacks
- **ChaCha20-Poly1305**: An authenticated encryption algorithm providing confidentiality and integrity
- **Device**: A browser instance running the React Frontend used to access the Cortex System
- **Key Recovery**: The process of deriving vault encryption keys on a new device using the vault password and vault salt
- **Local Key Storage**: Encrypted storage of vault keys in the browser only
- **Share Key**: A temporary encryption key generated for sharing specific files
- **Public Sharing**: Sharing files via URL containing the share key
- **User-to-User Sharing**: Sharing files by encrypting share keys with recipient's public key
- **Device Public Key**: A public key associated with a device for encrypted communication
- **Device Private Key**: A private key stored securely on a device for decryption
- **Key Rotation**: The periodic process of generating new encryption keys and re-encrypting data
- **Recovery Code**: A backup code provided at signup for account recovery
- **Data Encryption Key (DEK)**: A unique 256-bit symmetric key generated for each file, used to encrypt the file content
- **Key Encryption Key (KEK)**: The vault's key used to encrypt (wrap) DEKs, derived from the vault master key via HKDF
- **Wrapped DEK**: A DEK that has been encrypted with a KEK for secure storage
- **Envelope Encryption**: A pattern where data is encrypted with a DEK, and the DEK is encrypted with a KEK
- **Key Wrapping**: The process of encrypting a DEK with a KEK
- **Key Unwrapping**: The process of decrypting a wrapped DEK using the KEK
- **Share-Wrapped DEK**: A DEK encrypted with a share key for sharing files with others
- **DEK Metadata**: Information stored alongside the wrapped DEK including version, algorithm, and creation timestamp
- **Share Encryption Key**: A key derived from the share password using Argon2id, used to wrap the DEK for sharing
- **URL Fragment**: The portion of a URL after the # symbol, which is never sent to the server and remains client-side only
- **Share Salt**: A random value generated per share, used with the share password to derive the share encryption key
- **File Content**: The binary data stored in S3, applicable only to media items
- **Inline Content**: Encrypted content stored directly in DynamoDB, applicable to notes, tasks, and events

## 3. Functional Requirements

### 3.1 Media Upload and Storage

**Requirement ID:** REQ-1

**User Story:** As a user, I want to securely upload my media files to cloud storage, so that I can backup my data without the service provider accessing my content.

#### Acceptance Criteria

1. WHEN a user initiates a media upload, THE React Frontend SHALL generate a unique DEK and encrypt the file using ChaCha20-Poly1305 with the DEK before transmission
2. WHEN the file is encrypted, THE React Frontend SHALL wrap the DEK using ChaCha20-Poly1305 with the vault's KEK
3. WHEN encrypted data is transmitted, THE Cortex System SHALL store the encrypted data in the S3 Bucket without decryption
4. WHEN data is stored, THE Cortex System SHALL use S3 server-side encryption for additional security layer
5. WHEN a user uploads a media file, THE Cortex System SHALL generate a presigned URL for direct S3 upload to optimize transfer speed
6. WHERE a media file exceeds 5MB, THE Cortex System SHALL support S3 multipart upload for efficient large file handling

### 3.2 Metadata Management

**Requirement ID:** REQ-2

**User Story:** As a user, I want to manage metadata about my items, so that I can organize and retrieve my data effectively while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user creates an item, THE React Frontend SHALL encrypt all metadata including title, timestamps, and type-specific fields using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN encrypted metadata is received, THE Cortex System SHALL store it in the DynamoDB Table without decryption
3. WHEN a user requests their item list, THE Cortex System SHALL return encrypted metadata that only the React Frontend can decrypt
4. WHEN storing metadata, THE Cortex System SHALL associate each item with the user identifier and vault identifier without exposing content details
5. THE Cortex System SHALL maintain referential integrity between DynamoDB Table entries and S3 Bucket objects for media items

### 3.3 User Authentication

**Requirement ID:** REQ-3

**User Story:** As a user, I want to authenticate securely with the service using my account password, so that only I can access my encrypted backups.

#### Acceptance Criteria

1. WHEN a user attempts to access the Cortex System, THE Cortex System SHALL authenticate the user through AWS Cognito using the account password
2. WHEN authentication succeeds, THE Cortex System SHALL issue temporary scoped credentials using AWS SigV4 for API requests
3. WHEN scoped credentials are issued, THE Cortex System SHALL limit permissions to only the user's own resources in S3 and DynamoDB
4. WHEN a user makes an API request, THE API Gateway SHALL validate SigV4 signatures before routing to Lambda Functions
5. WHEN credential validation fails, THE Cortex System SHALL reject the request and return an authentication error
6. THE Cortex System SHALL ensure that vault encryption keys never leave the React Frontend and are never transmitted to or stored by the service

### 3.4 Media Download and Retrieval

**Requirement ID:** REQ-4

**User Story:** As a user, I want to retrieve and download my backed-up items, so that I can restore my data when needed.

#### Acceptance Criteria

1. WHEN a user requests a media item, THE Cortex System SHALL generate a presigned URL for direct S3 download and return the wrapped DEK
2. WHEN a user downloads encrypted data, THE React Frontend SHALL unwrap the DEK using the vault's KEK and decrypt the content
3. WHEN generating download URLs, THE Cortex System SHALL verify user ownership of the requested item
4. WHEN a download request is unauthorized, THE Cortex System SHALL reject the request and return an authorization error
5. THE Cortex System SHALL set presigned URL expiration to 15 minutes to limit exposure window

### 3.5 Media Deletion

**Requirement ID:** REQ-5

**User Story:** As a user, I want to delete my backed-up items, so that I can manage my storage and remove content I no longer need.

#### Acceptance Criteria

1. WHEN a user requests deletion of an item, THE Cortex System SHALL verify user ownership before proceeding
2. WHEN deletion is authorized for a media item, THE Cortex System SHALL remove the encrypted object from the S3 Bucket
3. WHEN an item is deleted, THE Cortex System SHALL remove the corresponding metadata entry from the DynamoDB Table
4. WHEN deletion operations fail, THE Cortex System SHALL maintain consistency between the S3 Bucket and DynamoDB Table
5. THE Cortex System SHALL return confirmation of successful deletion to the React Frontend

### 3.6 Serverless Infrastructure

**Requirement ID:** REQ-6

**User Story:** As a system operator, I want the service to run on AWS serverless infrastructure, so that it scales automatically and minimizes operational overhead.

#### Acceptance Criteria

1. THE Cortex System SHALL implement all API endpoints using AWS Lambda Functions written in Python
2. THE Cortex System SHALL expose API endpoints through AWS API Gateway with RESTful design
3. THE Cortex System SHALL define the API contract using a Smithy Model for service specification
4. WHEN API requests are received, THE API Gateway SHALL route them to appropriate Lambda Functions based on the Smithy Model
5. THE Cortex System SHALL use DynamoDB Table for all metadata storage with appropriate indexes for query performance

### 3.7 Upload Performance Optimization

**Requirement ID:** REQ-7

**User Story:** As a user, I want fast upload speeds for my media files, so that I can efficiently backup large file collections.

#### Acceptance Criteria

1. WHEN uploading media files, THE Cortex System SHALL provide presigned URLs for direct client-to-S3 upload bypassing Lambda Function
2. WHEN a presigned URL is generated, THE Lambda Function SHALL configure it with 15-minute expiration for upload performance
3. WHERE network conditions support concurrent operations, THE React Frontend SHALL upload multiple media files concurrently
4. WHERE a media file exceeds 100MB, THE Cortex System SHALL support S3 multipart upload with minimum 5MB part size
5. THE Cortex System SHALL configure S3 Bucket with transfer acceleration for improved global upload speeds

### 3.8 API Definition and Documentation

**Requirement ID:** REQ-8

**User Story:** As a developer, I want a well-defined API, so that I can build React frontend applications that interact with the backup service.

#### Acceptance Criteria

1. THE Cortex System SHALL provide a Smithy Model defining all API operations, inputs, and outputs
2. THE Cortex System SHALL expose API endpoints for upload initiation, metadata management, download, and deletion operations
3. WHEN API errors occur, THE Cortex System SHALL return structured error responses with appropriate HTTP status codes
4. THE Cortex System SHALL version the API to allow backward-compatible evolution
5. THE Cortex System SHALL provide API documentation generated from the Smithy Model

### 3.9 Zero-Knowledge Architecture

**Requirement ID:** REQ-9

**User Story:** As a security-conscious user, I want the system to maintain zero-knowledge architecture, so that I can trust that my private data remains private.

#### Acceptance Criteria

1. THE React Frontend SHALL generate and manage all vault encryption keys locally without server involvement
2. THE Cortex System SHALL never receive, store, or have access to unencrypted item content or metadata
3. THE Cortex System SHALL never receive or store vault encryption keys in plaintext form
4. WHEN processing requests, THE Lambda Functions SHALL operate only on encrypted data without decryption capability
5. THE Cortex System SHALL store all data in encrypted form in both the S3 Bucket and DynamoDB Table

### 3.10 Media Listing and Pagination

**Requirement ID:** REQ-10

**User Story:** As a user, I want to list my backed-up items, so that I can see what content I have stored in the service.

#### Acceptance Criteria

1. WHEN a user requests their item list, THE Cortex System SHALL query the DynamoDB Table for items associated with the user's vault
2. WHEN returning item lists, THE Cortex System SHALL support pagination for efficient handling of large collections
3. WHEN an item list is returned, THE Cortex System SHALL include encrypted metadata for each item
4. THE Cortex System SHALL allow filtering by item type and sorting of item lists based on encrypted timestamp fields
5. WHEN list queries execute, THE Cortex System SHALL use DynamoDB indexes to optimize query performance
6. THE Cortex System SHALL support filtering by encrypted date buckets for tasks and events

### 3.11 Tag Management and Search

**Requirement ID:** REQ-11

**User Story:** As a user, I want to tag and categorize my items, so that I can organize and search my content effectively while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user adds tags to an item, THE React Frontend SHALL encrypt each tag using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN encrypted tags are received, THE Cortex System SHALL store them in the DynamoDB Table without decryption
3. WHEN a user searches by tag, THE React Frontend SHALL encrypt the search term using the metadata encryption key before querying the Cortex System
4. WHEN the Cortex System processes tag queries, THE Lambda Function SHALL match encrypted tags without accessing plaintext tag values
5. WHERE the React Frontend supports content analysis, THE React Frontend SHALL perform analysis locally in the browser to generate suggested tags

### 3.12 Collection Creation and Organization

**Requirement ID:** REQ-12

**User Story:** As a user, I want to organize my items into collections, so that I can group related content while maintaining privacy about my organizational structure.

#### Acceptance Criteria

1. WHEN a user creates a collection, THE React Frontend SHALL encrypt the collection metadata using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN encrypted collection metadata is received, THE Cortex System SHALL store it in the DynamoDB Table without decryption
3. WHEN a user adds an item to a collection, THE Cortex System SHALL store the encrypted item-collection association
4. WHEN a user requests a collection, THE Cortex System SHALL return encrypted collection metadata and associated items
5. THE Cortex System SHALL support an item belonging to multiple collections simultaneously

### 3.13 Collection Management

**Requirement ID:** REQ-13

**User Story:** As a user, I want to manage my collections, so that I can update, rename, and delete organizational structures as my needs change.

#### Acceptance Criteria

1. WHEN a user updates collection metadata, THE React Frontend SHALL encrypt the new metadata using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN a user removes an item from a collection, THE Cortex System SHALL delete the item-collection association while preserving the item
3. WHEN a user deletes a collection, THE Cortex System SHALL remove the collection metadata and all associated item-collection associations
4. WHEN a collection is deleted, THE Cortex System SHALL preserve all items that were in the collection
5. WHEN a user lists their collections, THE Cortex System SHALL return all encrypted collection metadata with item counts

### 3.14 Multi-Device Vault Access

**Requirement ID:** REQ-14

**User Story:** As a user, I want to access my encrypted vault from multiple devices using my vault password, so that I can view and manage my files from any of my devices.

#### Acceptance Criteria

1. WHEN a user first creates a vault, THE React Frontend SHALL derive a vault master key from the vault password and vault salt using Argon2id with 64MB memory, 3 iterations, and 4 parallelism
2. WHEN a vault master key is derived, THE React Frontend SHALL use HKDF to derive KEK, metadata encryption key, and other derived keys from the vault master key
3. WHEN derived keys are generated, THE React Frontend SHALL store them encrypted locally in the browser using browser-specific encryption
4. WHEN a user accesses the vault from a new device, THE React Frontend SHALL prompt for the vault password and retrieve the vault salt from the Cortex System
5. WHEN the vault salt is retrieved, THE React Frontend SHALL derive the vault master key, KEK, and all derived keys locally using the vault password
6. THE Cortex System SHALL never receive, store, or have access to the vault master key, KEK, or any derived keys
7. WHEN encrypted local key storage is corrupted or unavailable, THE React Frontend SHALL prompt the user to re-enter their vault password
8. WHEN re-entering vault password after storage corruption, THE React Frontend SHALL fetch the vault salt from the Cortex System and re-derive all keys from scratch
9. THE React Frontend SHALL validate integrity of stored keys on app load using a checksum or MAC

### 3.15 Vault Recovery

**Requirement ID:** REQ-15

**User Story:** As a user, I want to recover my vault encryption keys if I forget my vault password, so that I do not permanently lose access to my encrypted backups.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE React Frontend SHALL generate a vault recovery key derived from the vault master key using BIP39 mnemonic encoding (24 words)
2. WHEN a vault recovery key is generated, THE React Frontend SHALL display it to the user once for secure offline storage with clear instructions
3. WHEN a user stores a vault recovery key, THE Cortex System SHALL store the current KEK version number as non-secret metadata in the DynamoDB Vaults table
4. WHEN a user forgets their vault password, THE React Frontend SHALL allow vault access using the vault recovery key to re-derive the vault master key
5. WHEN recovering a vault with a recovery key, THE React Frontend SHALL fetch the current KEK version from the DynamoDB Vaults table
6. WHEN the KEK version is retrieved, THE React Frontend SHALL derive the appropriate versioned KEK from the recovered vault master key using HKDF with the correct version context
7. IF the vault has undergone key rotation since the recovery key was created, THE React Frontend SHALL derive the latest KEK version to access files that have been re-wrapped with newer KEKs
8. WHEN vault recovery key is used successfully, THE React Frontend SHALL allow the user to set a new vault password while maintaining the same vault master key (no re-encryption needed)
9. THE Cortex System SHALL never receive, store, or have access to the vault recovery key itself (only the KEK version number is stored as metadata)
10. THE React Frontend SHALL document that recovery keys enable vault password reset without re-encrypting data, and that the KEK version ensures compatibility with rotated keys
11. IF the server is unavailable during recovery, THE React Frontend SHALL attempt to derive KEK versions incrementally (v1, v2, v3...) until decryption succeeds, enabling degraded offline recovery

### 3.16 Administrator Data Privacy

**Requirement ID:** REQ-16

**User Story:** As a user, I want assurance that service administrators cannot access my data, so that I can trust the service with my private content.

#### Acceptance Criteria

1. THE Cortex System SHALL ensure that Administrators with AWS console access cannot decrypt stored items
2. THE Cortex System SHALL ensure that Administrators cannot decrypt metadata, tags, or collection information stored in the DynamoDB Table
3. THE Cortex System SHALL ensure that Administrators cannot determine the content type, subject matter, or organizational structure of stored items
4. THE Cortex System SHALL ensure that Administrators cannot access vault encryption keys as they are never transmitted to or stored by the server
5. WHEN Administrators access system logs, THE Cortex System SHALL ensure logs contain no plaintext user data or content information

### 3.17 Public File Sharing

**Requirement ID:** REQ-17

**User Story:** As a user, I want to share specific items with others via password-protected links, so that I can give access to selected content without compromising my entire vault.

#### Acceptance Criteria

1. WHEN a user initiates media item sharing, THE React Frontend SHALL require a share password (passwordless sharing is not supported)
2. WHEN a share password is provided, THE React Frontend SHALL generate a unique random share salt (16 bytes) using a cryptographically secure random number generator
3. WHEN a share salt is generated, THE React Frontend SHALL derive a share encryption key using Argon2id with the share salt for wrapping the DEK
4. WHEN deriving share HMAC key, THE React Frontend SHALL use HKDF with the share encryption key, the same share salt, and context "cortex-share-hmac-v1" to ensure unique HMAC keys per share even with password reuse
5. WHEN a share encryption key is derived, THE React Frontend SHALL unwrap the file's DEK using the vault's KEK and wrap it with the share encryption key
6. WHEN creating a share, THE React Frontend SHALL generate a timestamp nonce representing the share creation time
7. WHEN computing share metadata HMAC, THE React Frontend SHALL include shareId, expiration timestamp, and creation timestamp nonce in the HMAC computation to prevent replay attacks
8. WHEN creating a share, THE React Frontend SHALL embed the password-wrapped DEK, share salt, HMAC of share metadata, and timestamp nonce in the share URL fragment (after the # symbol, never sent to server)
9. WHEN creating a share, THE Cortex System SHALL store only share metadata (share ID, file reference, creation time, optional expiration, access count) without any key material
10. WHEN a recipient accesses a share URL, THE React Frontend SHALL extract the wrapped DEK, salt, HMAC, and timestamp nonce from the URL fragment
11. WHEN a recipient accesses a share URL, THE React Frontend SHALL derive the share HMAC key using HKDF with the share encryption key, the share salt, and context "cortex-share-hmac-v1"
12. WHEN verifying share metadata HMAC, THE React Frontend SHALL recompute the HMAC over the server-provided metadata (shareId, expiration) plus the timestamp nonce from the URL fragment
13. WHEN verifying share metadata HMAC, THE React Frontend SHALL use constant-time comparison to prevent timing attacks
14. IF HMAC verification fails, THE React Frontend SHALL display an error indicating share metadata tampering and refuse to proceed with decryption
15. WHEN accessing a share, THE Cortex System SHALL validate that the timestamp nonce is within the share expiration window to prevent attackers from extending share lifetime
16. WHEN a recipient provides the share password, THE React Frontend SHALL derive the share encryption key using Argon2id with the salt from the URL fragment
17. WHEN the share encryption key is derived, THE React Frontend SHALL unwrap the DEK and decrypt the item locally
18. THE Cortex System SHALL never receive, store, or have access to the share password, share encryption key, wrapped DEK, salt, or HMAC key
19. THE React Frontend SHALL warn users that share URLs should not be shortened using URL shorteners (which leak share existence to third parties)
20. THE React Frontend SHALL support an alternative share access method where users enter share ID and password separately (for cases where full URL is truncated)
21. THE system documentation SHALL note that share metadata replay protection relies on server-side expiration checking as the source of truth, with timestamp nonces providing additional defense against replay attacks

### 3.18 Share Permission Control

**Requirement ID:** REQ-18

**User Story:** As a user, I want to control sharing permissions and optionally set expiration, so that I can limit access to my shared content.

#### Acceptance Criteria

1. WHEN creating a share, THE React Frontend SHALL allow the user to optionally specify a time-limited expiration (TTL is not required)
2. WHERE a share has an expiration set AND the expiration time has passed, THE Cortex System SHALL reject access requests and return an expiration error
3. WHEN a share password is provided, THE React Frontend SHALL require a minimum length of 16 characters
4. WHEN validating share password strength, THE React Frontend SHALL use an entropy estimator (such as zxcvbn) to calculate the estimated entropy rather than relying solely on character class requirements
5. WHEN calculating password entropy, THE React Frontend SHALL require a minimum estimated entropy of 80 bits regardless of password length or character composition
6. WHEN a share password fails entropy requirements, THE React Frontend SHALL provide clear user feedback displaying "Password strength: X bits (minimum 80 required)" with actionable guidance
7. WHEN a recipient enters an incorrect password, THE React Frontend SHALL display a generic error message and prompt for the correct password without revealing whether the share exists
8. WHEN a user revokes a share, THE Cortex System SHALL mark the share identifier as invalid and reject future access attempts
9. THE Cortex System SHALL implement server-side rate limiting on share access attempts (maximum 5 attempts per IP address per share ID per hour) to prevent brute-force attacks
10. WHEN rate limit is exceeded, THE Cortex System SHALL return HTTP 429 with a Retry-After header and log the attempt for security monitoring
11. THE React Frontend SHALL implement client-side exponential backoff after 3 failed password attempts to improve user experience and reduce server load (this is a UX improvement, not a security layer)
12. WHEN a share is revoked, THE user documentation SHALL clearly state that recipients who downloaded files before revocation can still decrypt them (true revocation requires re-encryption with new DEK)
13. THE React Frontend SHALL validate share password entropy at creation time only; entropy is not re-validated when recipients access shares
14. THE React Frontend SHALL NOT block share access based on updated entropy calculations that differ from creation-time validation

### 3.20 Automatic Key Rotation

**Requirement ID:** REQ-20

**User Story:** As a user, I want my vault encryption keys to be automatically rotated efficiently, so that I maintain strong security over time without re-uploading all my files.

#### Acceptance Criteria

1. WHEN 90 days have elapsed since the last key rotation, THE React Frontend SHALL initiate automatic vault key rotation
2. WHEN key rotation begins, THE React Frontend SHALL generate a new KEK from the vault master key using HKDF with an incremented version context parameter
3. WHEN key rotation begins, THE React Frontend SHALL store rotation state in IndexedDB with values: NOT_STARTED, IN_PROGRESS, PAUSED, COMPLETED, FAILED
4. WHEN key rotation is in progress, THE React Frontend SHALL store rotation progress in IndexedDB including vault ID, old KEK version, new KEK version, and completed items list to enable recovery from interruptions
5. IF the browser crashes or network fails during rotation, THE React Frontend SHALL resume rotation on next login by validating both old and new KEKs are still accessible and continuing from the last checkpoint
6. IF rotation encounters unrecoverable errors, THE React Frontend SHALL provide a "rollback" option to mark rotation as failed and continue using the old KEK
7. WHEN rotation has not completed within 7 days of starting, THE React Frontend SHALL auto-pause rotation and prompt the user to resume or rollback
8. WHEN rotating keys, THE React Frontend SHALL download only the wrapped DEKs from the Cortex System (not file content) for bandwidth efficiency
9. WHEN re-wrapping DEKs, THE React Frontend SHALL unwrap each DEK with the old KEK and wrap it with the new KEK without decrypting or re-encrypting file content
10. WHEN DEKs are re-wrapped, THE React Frontend SHALL upload the new wrapped DEKs to the Cortex System
11. WHILE key rotation is in progress, THE React Frontend SHALL maintain access to data using both old and new KEKs during the transition period
12. WHEN key rotation completes, THE React Frontend SHALL update the locally stored key version and overwrite the old KEK buffer with zeros before dereferencing
13. WHILE key rotation is in progress, THE React Frontend SHALL block share creation operations (shares must use the new KEK only)
14. WHILE key rotation is in progress, new file uploads SHALL use the new KEK for wrapping DEKs
15. WHILE key rotation is in progress, in-progress downloads SHALL complete using the KEK version that matches the file's DEK version
16. WHEN a multipart upload is initiated during key rotation, THE React Frontend SHALL capture the current KEK version at upload initiation
17. WHEN a multipart upload completes during or after key rotation, THE React Frontend SHALL verify the captured KEK version is still available before wrapping the DEK
18. IF the captured KEK version is no longer available due to rotation rollback, THE React Frontend SHALL abort the upload and prompt the user to retry
19. THE Cortex System SHALL enforce that only one key rotation can be in progress per vault at a time
20. WHEN key rotation is initiated, THE Cortex System SHALL acquire a rotation lock in the DynamoDB Vaults table using optimistic locking (conditional write on rotationState)
21. WHEN a second device attempts rotation while one is in progress, THE Cortex System SHALL reject the request and inform the user that rotation is already in progress on another device
22. THE Cortex System SHALL auto-expire rotation locks after 7 days to prevent permanent lock-out

### 3.21 Password Security Requirements

**Requirement ID:** REQ-21

**User Story:** As a user, I want strong password requirements and breach detection for both my account and vault passwords, so that my account and data remain secure against common attacks.

#### Acceptance Criteria

1. WHEN a user creates an account password or vault password, THE React Frontend SHALL require a minimum length of 12 characters
2. WHEN a user creates an account password or vault password, THE React Frontend SHALL require inclusion of uppercase letters, lowercase letters, numbers, and special characters
3. WHEN a user creates or changes an account password or vault password, THE React Frontend SHALL validate the password against known breach databases
4. WHEN a breached password is detected, THE React Frontend SHALL reject the password and prompt the user to choose a different password
5. WHERE a user enables two-factor authentication, THE Cortex System SHALL require a second authentication factor for account access

### 3.19 Account Recovery

**Requirement ID:** REQ-19

**User Story:** As a user, I want multiple recovery options for my account, so that I can regain access if I lose my account password.

#### Acceptance Criteria

1. WHEN a user completes account setup, THE Cortex System SHALL generate 10 account recovery codes and display them once
2. WHEN a user loses access to their account, THE Cortex System SHALL allow authentication using one of the account recovery codes
3. WHEN an account recovery code is used, THE Cortex System SHALL invalidate that specific code to prevent reuse
4. WHERE a user enables two-factor authentication, THE Cortex System SHALL provide backup codes for 2FA recovery
5. WHEN account recovery is successful, THE React Frontend SHALL prompt the user to set a new account password

### 3.22 Vault Salt Management and Integrity Protection

**Requirement ID:** REQ-22

**User Story:** As a user, I want the system to store my vault salt securely with integrity protection, so that I can derive the same keys across devices while detecting any tampering attempts.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE Cortex System SHALL generate a unique vault salt using a cryptographically secure random number generator
2. WHEN a vault salt is generated, THE Cortex System SHALL store it in the DynamoDB Table associated with the vault
3. WHEN a user first derives their vault master key from their vault password, THE React Frontend SHALL compute an HMAC over the vault salt using a key derived from the vault password via HKDF with context "cortex-salt-hmac-v1"
4. WHEN the vault salt HMAC is computed, THE React Frontend SHALL store it locally for integrity verification on subsequent accesses
5. WHEN a user accesses their vault from any device, THE Cortex System SHALL provide the vault salt to enable key derivation
6. WHEN the vault salt is retrieved, THE React Frontend SHALL verify the HMAC to detect any tampering with the salt using constant-time comparison
7. IF vault salt HMAC verification fails, THEN THE React Frontend SHALL display a security warning and refuse to proceed with key derivation
8. IF vault salt HMAC verification fails, THEN THE React Frontend SHALL provide a "reset salt HMAC" option that requires re-authentication with both account password and vault password to re-establish trust
9. WHEN a user initiates salt HMAC reset, THE React Frontend SHALL re-compute the HMAC using the newly re-authenticated vault password and update the locally stored HMAC
10. THE Cortex System SHALL ensure each vault salt is unique and never reused across vaults
11. THE Cortex System SHALL treat the vault salt as non-secret information that can be stored and transmitted without encryption
12. THE React Frontend SHALL document the recovery procedure for HMAC verification failures, including scenarios where legitimate salt changes occur (e.g., account recovery from backup)

### 3.23 Password Change Management

**Requirement ID:** REQ-23

**User Story:** As a user, I want to change my account password without re-encrypting my entire vault, so that I can update my credentials efficiently.

#### Acceptance Criteria

1. WHEN a user changes their account password, THE Cortex System SHALL update the account authentication credentials in AWS Cognito without affecting the vault encryption keys
2. WHEN an account password is changed, THE React Frontend SHALL authenticate with AWS Cognito using the new account password
3. WHEN a user changes their vault password, THE React Frontend SHALL derive a new vault master key and KEK from the new vault password and the existing vault salt using Argon2id
4. WHEN a new KEK is derived from vault password change, THE React Frontend SHALL generate it with an incremented version number using HKDF with updated version context (e.g., "cortex-kek-v2")
5. WHEN vault password change begins, THE React Frontend SHALL store the KEK version alongside each wrapped DEK in DynamoDB to track which version was used for wrapping
6. WHEN re-wrapping DEKs during vault password change, THE React Frontend SHALL implement progress tracking in IndexedDB storing vault ID, old KEK version, new KEK version, and completed items list
7. IF vault password change process is interrupted (network failure, browser crash), THE React Frontend SHALL resume from the last checkpoint using the progress tracking data
8. WHEN vault password change is in progress, THE React Frontend SHALL maintain dual-KEK access allowing both old and new KEKs to unwrap files during the transition period
9. WHEN a wrapped DEK is accessed during vault password change, THE React Frontend SHALL check the DEK's version metadata to determine whether to use the old or new KEK for unwrapping
10. WHILE vault password change is processing, THE React Frontend SHALL perform DEK re-wrapping in configurable batches to manage memory usage and minimize user disruption
11. WHEN vault password change completes successfully, THE React Frontend SHALL clear the old KEK from memory and update the local encrypted key storage with the new KEK version

### 3.24 Multi-Type Item Storage

**Requirement ID:** REQ-24

**User Story:** As a user, I want to store different types of data (media, notes, tasks, events) in my vault, so that I can manage all my information in one secure place.

#### Acceptance Criteria

1. WHEN a user creates an item, THE React Frontend SHALL support itemType: MEDIA, NOTE, TASK, EVENT
2. WHEN storing items, THE Cortex System SHALL use a unified Items table for all types
3. WHEN querying items, THE Cortex System SHALL support filtering by itemType
4. WHEN encrypting items, THE React Frontend SHALL encrypt type-specific content as JSON blobs using the appropriate encryption key
5. THE Cortex System SHALL maintain referential integrity for all item types

### 3.25 Privacy-Preserving Date Queries

**Requirement ID:** REQ-25

**User Story:** As a user, I want to query tasks and events by date without revealing exact times to the server, so that my schedule remains private.

#### Acceptance Criteria

1. WHEN a user creates a task or event with a date, THE React Frontend SHALL generate an encrypted date bucket representing a 15-minute time window
2. WHEN storing date-based items, THE Cortex System SHALL store both encryptedExactTime and plaintext timeBucket
3. WHEN querying by date, THE Cortex System SHALL use timeBucket for server-side filtering
4. WHEN results are returned, THE React Frontend SHALL decrypt exact times and filter locally for precise matching
5. THE Cortex System SHALL never have access to exact unencrypted times

### 3.26 Push Notifications

**Requirement ID:** REQ-26

**User Story:** As a user, I want to receive push notifications for my tasks and events, so that I don't miss important reminders even when the app is closed.

#### Acceptance Criteria

1. WHEN a user creates a task/event with a reminder, THE Client Application SHALL create a notification schedule with encrypted payload
2. WHEN storing notification schedules, THE Cortex System SHALL store encryptedPayload, encryptedExactTime, and timeBucket
3. WHEN a notification is due, THE Cortex System SHALL send push notifications via AWS SNS with encrypted payloads
4. WHEN receiving a notification, THE Client Application SHALL decrypt the payload locally before displaying
5. THE Cortex System SHALL never have access to plaintext notification content
6. WHEN notification delivery fails, THE notification processor SHALL retry up to 3 times with exponential backoff (5 minutes, 15 minutes, 45 minutes)
7. WHEN SNS returns a permanent failure (EndpointDisabled, InvalidParameter), THE notification processor SHALL mark the device token as invalid and SHALL NOT retry
8. WHEN all retry attempts are exhausted, THE notification processor SHALL move the notification to a dead-letter state and notify the user on next app access
9. THE Cortex System SHALL distinguish between transient failures (network errors, throttling) that warrant retry and permanent failures (expired tokens, invalid endpoints) that do not
10. WHEN a user creates a recurring task or event with a reminder, THE React Frontend SHALL expand the recurrence rule into individual notification schedules for the next 90 days
11. WHEN the pre-generated notification window approaches within 7 days of its end, THE React Frontend SHALL generate the next batch of notification schedules
12. WHEN a recurring event is modified or deleted, THE React Frontend SHALL update or cancel all associated future notification schedules

### 3.27 Real-Time Sync

**Requirement ID:** REQ-27

**User Story:** As a user, I want my changes to sync across devices in real-time, so that I always see the latest data.

#### Acceptance Criteria

1. WHEN a user modifies an item, THE Cortex System SHALL notify other connected devices via WebSocket
2. WHEN receiving a sync notification, THE React Frontend SHALL fetch updated encrypted data
3. WHEN conflicts occur, THE React Frontend SHALL use last-write-wins resolution based on version numbers
4. THE Cortex System SHALL send only metadata in sync notifications without content
5. THE React Frontend SHALL decrypt and merge changes locally
6. THE Cortex System SHALL enforce a maximum of 10 concurrent WebSocket connections per vault
7. WHEN a new connection is established and the limit is exceeded, THE Cortex System SHALL gracefully terminate the oldest connection
8. THE Cortex System SHALL log excessive connection attempts for security monitoring

### 3.28 Envelope Encryption for Media Files

**Requirement ID:** REQ-28

**User Story:** As a user, I want each of my media files to be encrypted with a unique key, so that compromise of one file's key does not affect other files and key rotation is efficient.

#### Acceptance Criteria

1. WHEN a user initiates a media file upload, THE React Frontend SHALL generate a unique 256-bit DEK using a cryptographically secure random number generator
2. WHEN a DEK is generated, THE React Frontend SHALL encrypt the file content using ChaCha20-Poly1305 with the DEK
3. WHEN the file is encrypted, THE React Frontend SHALL wrap the DEK using ChaCha20-Poly1305 with the vault's KEK
4. WHEN a file upload completes, THE React Frontend SHALL send the wrapped DEK to the Cortex System for storage alongside the file metadata
5. THE React Frontend SHALL never reuse a DEK across multiple files
6. THE Cortex System SHALL store wrapped DEKs in the DynamoDB Items table without decryption capability
7. THE React Frontend SHALL document that ChaCha20-Poly1305 does not provide key commitment, meaning an attacker with ciphertext could potentially find two different DEKs that both decrypt to valid plaintexts
8. THE React Frontend SHALL document that the risk of key commitment attacks is low in Cortex's context because an attacker would need to replace both the ciphertext AND the wrapped DEK
9. WHERE key binding is desired for additional security, THE React Frontend MAY compute HMAC(DEK, file_id) and store it alongside the wrapped DEK metadata to bind the DEK to a specific file and prevent key substitution attacks
10. IF HMAC(DEK, file_id) binding is implemented, THE React Frontend SHALL verify the HMAC during unwrapping to ensure the DEK has not been substituted with a different key
11. THE React Frontend SHALL use a documented binary format for wrapped DEKs that includes version byte, timestamp, nonce, encrypted DEK, and authentication tag
12. THE system documentation SHALL specify endianness (big-endian) and field sizes for the wrapped DEK format

### 3.29 Envelope Encryption Decryption

**Requirement ID:** REQ-29

**User Story:** As a user, I want to decrypt my envelope-encrypted files seamlessly, so that I can access my content securely from any device.

#### Acceptance Criteria

1. WHEN a user requests to download a media file, THE Cortex System SHALL return the wrapped DEK along with the file metadata
2. WHEN the wrapped DEK is retrieved, THE React Frontend SHALL unwrap it using the vault's KEK
3. WHEN the DEK is unwrapped, THE React Frontend SHALL use it to decrypt the file content downloaded from S3
4. IF the wrapped DEK cannot be unwrapped, THEN THE React Frontend SHALL return a specific error code indicating the failure type
5. WHEN unwrapping fails due to authentication tag verification, THE React Frontend SHALL return error code CORRUPTED_DEK or AUTHENTICATION_FAILED to distinguish between data corruption and wrong KEK
6. WHEN unwrapping fails due to KEK version mismatch during rotation, THE React Frontend SHALL return error code WRONG_KEK_VERSION with user message "Key rotation in progress, try again in a few minutes"
7. WHEN unwrapping fails due to malformed wrapped DEK structure, THE React Frontend SHALL return error code CORRUPTED_DEK with user message indicating unrecoverable data corruption
8. WHEN CORRUPTED_DEK error occurs, THE React Frontend SHALL allow the user to mark the file as corrupted, delete it, or report the issue for investigation
9. WHEN WRONG_KEK_VERSION error occurs, THE React Frontend SHALL inform the user to wait for key rotation completion and retry the operation
10. THE React Frontend SHALL log unwrapping failures (without key material) to enable monitoring of data corruption rates and KEK version mismatches
11. WHEN decryption completes successfully, THE React Frontend SHALL overwrite the unwrapped DEK buffer with zeros before dereferencing (best-effort memory clearing)
12. THE React Frontend SHALL use TypedArray (Uint8Array) for all key material to enable explicit zeroing
13. WHERE available, THE React Frontend SHALL prefer Web Crypto API (crypto.subtle) for key operations as it may provide better memory handling

### 3.30 Efficient Key Rotation with Envelope Encryption

**Requirement ID:** REQ-30

**User Story:** As a user, I want key rotation to be fast and bandwidth-efficient, so that I can maintain security without re-uploading all my files.

#### Acceptance Criteria

1. WHEN key rotation is triggered, THE React Frontend SHALL generate a new KEK from the vault master key using HKDF with an incremented version
2. WHEN rotating keys, THE React Frontend SHALL download only the wrapped DEKs from the Cortex System, not the file content
3. WHEN re-wrapping DEKs, THE React Frontend SHALL unwrap each DEK with the old KEK and wrap it with the new KEK
4. WHEN a DEK is re-wrapped, THE React Frontend SHALL upload the new wrapped DEK to the Cortex System
5. WHILE key rotation is in progress, THE React Frontend SHALL maintain access to files using both old and new KEKs
6. WHEN key rotation completes for all files, THE Cortex System SHALL have updated wrapped DEK records with the new versions

### 3.31 Enhanced File Sharing with Envelope Encryption

**Requirement ID:** REQ-31

**User Story:** As a user, I want to share files securely with a password, so that only recipients who know the password can access my shared content.

#### Acceptance Criteria

1. WHEN a user creates a share for a media file, THE React Frontend SHALL require a share password
2. WHEN a share password is provided, THE React Frontend SHALL derive a share encryption key from the password and a random salt using Argon2id
3. WHEN the share encryption key is derived, THE React Frontend SHALL unwrap the file's DEK using the vault's KEK and wrap it with the share encryption key
4. WHEN a share is created, THE React Frontend SHALL embed the password-wrapped DEK and salt in the share URL
5. THE Cortex System SHALL NOT store any key material (DEK, wrapped DEK, share key, or salt) on the server
6. WHEN a recipient accesses a shared file, THE React Frontend SHALL prompt for the share password and derive the share encryption key to unwrap the DEK
7. THE original file's vault-wrapped DEK SHALL remain unaffected by share creation

### 3.32 DEK Versioning and Downgrade Protection

**Requirement ID:** REQ-32

**User Story:** As a user, I want my file encryption keys to be versioned and protected against downgrade attacks, so that the system can handle key format changes gracefully while maintaining security.

#### Acceptance Criteria

1. WHEN wrapping a DEK, THE React Frontend SHALL include a version identifier in the wrapped DEK metadata
2. WHEN storing a wrapped DEK, THE Cortex System SHALL store the DEK version alongside the wrapped DEK in the Items table
3. WHEN unwrapping a DEK, THE React Frontend SHALL check the version identifier and use the appropriate unwrapping algorithm
4. IF an unsupported DEK version is encountered, THEN THE React Frontend SHALL return a version error with guidance
5. THE React Frontend SHALL maintain a list of deprecated or insecure DEK wrapping versions
6. WHEN encountering a DEK with a deprecated version, THE React Frontend SHALL refuse to unwrap it and prompt the user to migrate
7. WHEN a deprecated version is encountered, THE React Frontend SHALL provide a migration path to re-wrap the DEK with the current version
8. THE React Frontend SHALL support reading DEKs wrapped with any previously supported version that is not marked as deprecated
9. THE React Frontend SHALL use constant-time comparison when verifying DEK authentication tags to prevent timing attacks

### 3.33 Batch Key Rotation

**Requirement ID:** REQ-33

**User Story:** As a user with many files, I want key rotation to process files in batches, so that rotation completes reliably without overwhelming my device.

#### Acceptance Criteria

1. WHEN key rotation begins, THE React Frontend SHALL query the Cortex System for all wrapped DEKs in the vault
2. WHEN processing DEKs, THE React Frontend SHALL re-wrap them in configurable batch sizes with a recommended default of 100-500 DEKs per batch to manage memory usage
3. WHILE batch processing, THE React Frontend SHALL monitor browser heap memory usage and pause rotation automatically if memory usage exceeds 80% of available heap
4. WHILE batch processing, THE React Frontend SHALL report progress to the user interface showing total items, processed items, and estimated remaining time
5. WHEN a batch completes processing, THE React Frontend SHALL immediately clear processed DEK buffers from memory before proceeding to the next batch
6. IF a batch fails, THEN THE React Frontend SHALL retry the failed batch with exponential backoff before proceeding
7. IF a batch fails after 3 retry attempts, THE React Frontend SHALL pause rotation and prompt the user to resolve the issue or rollback
8. WHEN all batches complete, THE React Frontend SHALL update the vault's key version in local storage
9. THE React Frontend SHALL allow pausing and resuming key rotation for large vaults, storing progress state in IndexedDB
10. WHEN rotation is paused, THE React Frontend SHALL provide clear indication to the user that rotation is incomplete and dual-KEK access is still active
11. THE React Frontend SHALL track rotation progress using cursor-based pagination (last processed item sort key) rather than storing complete lists of processed item IDs, to avoid exceeding IndexedDB storage quotas for large vaults
12. WHEN re-wrapping a DEK during key rotation, THE React Frontend SHALL use conditional DynamoDB updates (ConditionExpression on dekVersion) to ensure idempotent writes
13. WHEN a conditional update fails because the DEK was already re-wrapped, THE React Frontend SHALL skip that item and continue with the next

### 3.34 Secure Key Zeroization on Logout

**Requirement ID:** REQ-34

**User Story:** As a user, I want all encryption keys to be securely cleared from memory when I log out, so that my keys cannot be recovered from memory after my session ends.

#### Acceptance Criteria

1. WHEN a user initiates logout, THE React Frontend SHALL overwrite all key material buffers (vault master key, KEK, all derived keys, and any cached DEKs) with cryptographically random data before dereferencing
2. WHEN key buffers are zeroized, THE React Frontend SHALL perform the overwrite operation at least twice (first with zeros, then with random data) to reduce potential for memory recovery
3. WHEN logout is initiated, THE React Frontend SHALL clear all encrypted key storage from browser local storage and session storage
4. WHEN logout completes, THE React Frontend SHALL explicitly delete all IndexedDB entries containing encrypted keys
5. WHEN a user closes the browser or tab unexpectedly, THE React Frontend SHALL use beforeunload event handlers to attempt best-effort key zeroization
6. THE React Frontend SHALL document that complete memory clearing cannot be guaranteed in JavaScript environments due to garbage collection and memory management limitations
7. WHERE available, THE React Frontend SHALL prefer Web Crypto API (crypto.subtle) non-extractable keys to minimize key exposure in JavaScript-accessible memory
8. WHEN session timeout occurs, THE React Frontend SHALL perform the same key zeroization process as explicit logout

### 3.35 DEK Version Deployment Safety

**Requirement ID:** REQ-35

**User Story:** As a user, I want new DEK versions to be deployed safely with rollback support, so that bugs in new encryption versions do not cause data loss.

#### Acceptance Criteria

1. New DEK versions SHALL be deployed as SUPPORTED (readable) for a minimum of 30 days before becoming CURRENT (used for new wrapping)
2. Rollback to a previous DEK version deployment SHALL NOT cause data loss for files wrapped with the new version
3. THE React Frontend SHALL maintain backward compatibility with all non-deprecated DEK versions

## 4. Non-Functional Requirements

### 4.1 Performance Requirements

**REQ-NFR-1: Upload Performance**
- Media files up to 5MB SHALL upload within 10 seconds on a 10 Mbps connection
- Media files exceeding 100MB SHALL support multipart upload with minimum 5MB part size
- The system SHALL support concurrent uploads of up to 5 files simultaneously

**REQ-NFR-2: Query Performance**
- Media list queries SHALL return results within 2 seconds for collections up to 10,000 items
- Tag search queries SHALL return results within 3 seconds
- Pagination SHALL support page sizes from 10 to 100 items

**REQ-NFR-3: Key Derivation Performance**
- Vault master key derivation using Argon2id SHALL complete within 5 seconds on modern client devices
- HKDF key derivation SHALL complete within 100 milliseconds

### 4.2 Security Requirements

**REQ-NFR-4: Encryption Standards**
- All client-side encryption SHALL use ChaCha20-Poly1305 with 256-bit keys
- Key derivation SHALL use Argon2id with 64MB memory, 3 iterations, and 4 parallelism
- Derived keys SHALL use HKDF with SHA-256

**REQ-NFR-5: Authentication**
- All API requests SHALL be authenticated using AWS SigV4
- Authentication tokens SHALL expire after 1 hour
- Refresh tokens SHALL be valid for 30 days

**REQ-NFR-6: Data Protection**
- All data in transit SHALL use TLS 1.3 or higher
- S3 objects SHALL use server-side encryption (AES-256)
- Presigned URLs SHALL expire after 15 minutes

### 4.3 Scalability Requirements

**REQ-NFR-7: User Capacity**
- The system SHALL support at least 100,000 concurrent users
- Each user SHALL be able to store up to 1TB of encrypted data
- The system SHALL support up to 1 million items per vault

**REQ-NFR-8: Infrastructure Scaling**
- Lambda functions SHALL auto-scale based on request volume
- DynamoDB tables SHALL use on-demand billing or auto-scaling
- S3 SHALL handle unlimited storage capacity

### 4.4 Availability Requirements

**REQ-NFR-9: Uptime**
- The system SHALL maintain 99.9% uptime (excluding planned maintenance)
- Planned maintenance windows SHALL not exceed 4 hours per month
- The system SHALL recover from failures within 15 minutes

**REQ-NFR-10: Data Durability**
- S3 SHALL provide 99.999999999% (11 nines) durability
- DynamoDB SHALL provide 99.999999999% (11 nines) durability
- Backup and recovery procedures SHALL be tested quarterly

### 4.5 Usability Requirements

**REQ-NFR-11: React Frontend**
- The React frontend SHALL provide clear feedback during upload/download operations
- Error messages SHALL be user-friendly and actionable
- The vault password setup process SHALL include strength indicators and guidance

**REQ-NFR-12: Documentation**
- API documentation SHALL be generated from Smithy models
- User documentation SHALL explain the two-password model clearly
- Recovery procedures SHALL be documented with step-by-step instructions

### 4.6 Compliance Requirements

**REQ-NFR-13: Privacy Compliance**
- The system SHALL comply with GDPR requirements for data privacy
- Users SHALL be able to export all their data in a portable format
- Users SHALL be able to delete all their data permanently

**REQ-NFR-14: Audit Logging**
- All authentication attempts SHALL be logged
- All data access operations SHALL be logged (without plaintext data)
- Logs SHALL be retained for at least 90 days

## 5. Constraints and Assumptions

### 5.1 Technical Constraints

- The system MUST run on AWS infrastructure
- Lambda functions MUST be written in Python 3.11 or higher
- Client-side encryption MUST use ChaCha20-Poly1305
- API definitions MUST use Smithy models

### 5.2 Business Constraints

- The system MUST maintain zero-knowledge architecture
- Service administrators MUST NOT have access to unencrypted user data
- The two-password model (account password and vault password) MUST be maintained

### 5.3 Assumptions

- Users have access to modern web browsers capable of running React applications and performing client-side encryption
- Users have reliable internet connectivity for uploads and downloads
- Users will securely store their vault recovery keys offline
- Users understand the difference between account password and vault password

## 6. Dependencies

### 6.1 External Dependencies

- AWS Services: Lambda, API Gateway, S3, DynamoDB, Cognito, CloudWatch, SNS
- Client Libraries: @noble/ciphers, @noble/hashes, argon2-browser, bip39
- Python Libraries: aws-lambda-powertools, pydantic, boto3, hypothesis

### 6.2 Internal Dependencies

- Smithy API model definitions must be completed before Lambda implementation
- CDK infrastructure must be deployed before integration testing
- Client-side encryption library must be completed before end-to-end testing

## 7. Future Enhancements

The following features are out of scope for the initial release but may be considered for future versions:

- User-to-user sharing with public key encryption
- Collaborative editing of notes and documents
- Advanced search with full-text indexing (encrypted)
- Mobile applications for iOS and Android
- Desktop applications for Windows, macOS, and Linux
- Two-factor authentication (2FA) for account access
- Biometric authentication for vault access
- Automated backup scheduling
- Version history for files and notes
- Trash/recycle bin with recovery period
