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

## 3. Functional Requirements

### 3.1 Media Upload and Storage

**Requirement ID:** REQ-1

**User Story:** As a user, I want to securely upload my media files to cloud storage, so that I can backup my data without the service provider accessing my content.

#### Acceptance Criteria

1. WHEN a user initiates a media upload, THE React Frontend SHALL encrypt the file using ChaCha20-Poly1305 with the data encryption key before transmission
2. WHEN encrypted data is transmitted, THE Cortex System SHALL store the encrypted data in the S3 Bucket without decryption
3. WHEN data is stored, THE Cortex System SHALL use S3 server-side encryption for additional security layer
4. WHEN a user uploads a media file, THE Cortex System SHALL generate a presigned URL for direct S3 upload to optimize transfer speed
5. WHERE a media file exceeds 5MB, THE Cortex System SHALL support S3 multipart upload for efficient large file handling

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

1. WHEN a user requests a media item, THE Cortex System SHALL generate a presigned URL for direct S3 download
2. WHEN a user downloads encrypted data, THE React Frontend SHALL decrypt the content using the vault's appropriate encryption key
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
2. WHEN a vault master key is derived, THE React Frontend SHALL use HKDF to derive data encryption key and metadata encryption key from the vault master key
3. WHEN derived keys are generated, THE React Frontend SHALL store them encrypted locally in the browser using browser-specific encryption
4. WHEN a user accesses the vault from a new device, THE React Frontend SHALL prompt for the vault password and retrieve the vault salt from the Cortex System
5. WHEN the vault salt is retrieved, THE React Frontend SHALL derive the vault master key and all derived keys locally using the vault password
6. THE Cortex System SHALL never receive, store, or have access to the vault master key or any derived keys

### 3.15 Vault Recovery

**Requirement ID:** REQ-15

**User Story:** As a user, I want to recover my vault encryption keys if I forget my vault password, so that I do not permanently lose access to my encrypted backups.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE React Frontend SHALL generate a vault recovery key derived from the vault master key
2. WHEN a vault recovery key is generated, THE React Frontend SHALL display it to the user once for secure offline storage
3. WHEN a user forgets their vault password, THE React Frontend SHALL allow vault access using the vault recovery key to re-derive the vault master key
4. WHEN vault recovery key is used, THE React Frontend SHALL allow the user to set a new vault password
5. THE Cortex System SHALL never receive, store, or have access to the vault recovery key

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

**User Story:** As a user, I want to share specific items with others via public links, so that I can give access to selected content without compromising my entire vault.

#### Acceptance Criteria

1. WHEN a user initiates item sharing, THE React Frontend SHALL generate a unique share key for the specific item
2. WHEN a share key is generated, THE React Frontend SHALL create a share URL containing the item identifier and base64-encoded share key
3. WHEN creating a public share, THE Cortex System SHALL store only the item identifier and share metadata without access to the share key
4. WHEN a recipient accesses a share URL, THE React Frontend SHALL extract the share key from the URL and use it to decrypt the item locally
5. THE Cortex System SHALL allow anonymous access to items via share identifier without requiring authentication

### 3.18 Share Permission Control

**Requirement ID:** REQ-18

**User Story:** As a user, I want to control sharing permissions and expiration, so that I can limit access to my shared content.

#### Acceptance Criteria

1. WHEN creating a share, THE React Frontend SHALL allow the user to specify time-limited expiration
2. WHEN a share has expired, THE Cortex System SHALL reject access requests and return an expiration error
3. WHERE a user enables password protection, THE React Frontend SHALL derive an additional encryption key from the password and double-encrypt the share key in the URL
4. WHEN a password-protected share is accessed, THE React Frontend SHALL prompt for the password before decrypting the share key
5. WHEN a user revokes a share, THE Cortex System SHALL mark the share identifier as invalid and reject future access attempts

### 3.20 Automatic Key Rotation

**Requirement ID:** REQ-20

**User Story:** As a user, I want my vault encryption keys to be automatically rotated, so that I maintain strong security over time without manual intervention.

#### Acceptance Criteria

1. WHEN 90 days have elapsed since the last key rotation, THE React Frontend SHALL initiate automatic vault key rotation
2. WHEN key rotation begins, THE React Frontend SHALL generate new derived keys from the vault master key using HKDF with updated context parameters
3. WHEN new keys are generated, THE React Frontend SHALL re-encrypt all vault data in the background using the new data encryption key
4. WHEN re-encryption completes, THE React Frontend SHALL update the locally stored encrypted key bundle with the new key material
5. WHILE key rotation is in progress, THE React Frontend SHALL maintain access to data encrypted with both old and new keys during the transition period

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

### 3.22 Vault Salt Management

**Requirement ID:** REQ-22

**User Story:** As a user, I want the system to store my vault salt securely, so that I can derive the same keys across devices while maintaining security.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE Cortex System SHALL generate a unique vault salt using a cryptographically secure random number generator
2. WHEN a vault salt is generated, THE Cortex System SHALL store it in the DynamoDB Table associated with the vault
3. WHEN a user accesses their vault from any device, THE Cortex System SHALL provide the vault salt to enable key derivation
4. THE Cortex System SHALL ensure each vault salt is unique and never reused across vaults
5. THE Cortex System SHALL treat the vault salt as non-secret information that can be stored and transmitted without encryption

### 3.23 Password Change Management

**Requirement ID:** REQ-23

**User Story:** As a user, I want to change my account password without re-encrypting my entire vault, so that I can update my credentials efficiently.

#### Acceptance Criteria

1. WHEN a user changes their account password, THE Cortex System SHALL update the account authentication credentials in AWS Cognito without affecting the vault encryption keys
2. WHEN an account password is changed, THE React Frontend SHALL authenticate with AWS Cognito using the new account password
3. WHEN a user changes their vault password, THE React Frontend SHALL derive a new vault master key from the new vault password and the existing vault salt using Argon2id
4. WHEN a new vault master key is derived, THE React Frontend SHALL re-encrypt all vault data and metadata with keys derived from the new vault master key
5. WHILE vault password change is processing, THE React Frontend SHALL perform re-encryption in the background to minimize user disruption

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

### 3.27 Real-Time Sync

**Requirement ID:** REQ-27

**User Story:** As a user, I want my changes to sync across devices in real-time, so that I always see the latest data.

#### Acceptance Criteria

1. WHEN a user modifies an item, THE Cortex System SHALL notify other connected devices via WebSocket
2. WHEN receiving a sync notification, THE React Frontend SHALL fetch updated encrypted data
3. WHEN conflicts occur, THE React Frontend SHALL use last-write-wins resolution based on version numbers
4. THE Cortex System SHALL send only metadata in sync notifications without content
5. THE React Frontend SHALL decrypt and merge changes locally

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
