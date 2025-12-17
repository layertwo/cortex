# Requirements Document

## Introduction

Cortex is a zero-knowledge cloud-based file storage and backup solution that prioritizes user privacy through client-side encryption. The system runs on AWS infrastructure using serverless technologies (Lambda, API Gateway) and provides secure, encrypted storage where the service provider has no knowledge of the content being stored. Cortex enables users to safely backup any type of file while maintaining complete control over their data privacy through a vault-based architecture that separates account authentication from data encryption.

## Glossary

- **Cortex System**: The complete cloud-based storage solution including API, storage, and database components
- **Client Application**: The frontend application that users interact with to upload and manage their files
- **Zero-Knowledge Architecture**: A design where the service provider cannot access or decrypt user data
- **File**: Any type of file uploaded by a user to their vault
- **Encryption Key**: A cryptographic key generated and managed by the client for encrypting files
- **Metadata**: Information about files such as filename, size, upload date, and MIME type (stored encrypted)
- **User**: An authenticated individual using the Cortex System
- **Upload Session**: A temporary context for uploading one or more files
- **S3 Bucket**: AWS Simple Storage Service container for storing encrypted media
- **DynamoDB Table**: AWS NoSQL database for storing encrypted metadata and user information
- **Lambda Function**: AWS serverless compute function handling API requests
- **API Gateway**: AWS service providing RESTful API endpoints
- **Smithy Model**: Interface definition language describing the API service contract
- **Multipart Upload**: S3 feature for uploading large files in chunks
- **Presigned URL**: Time-limited URL for direct S3 upload access
- **Tag**: A label or keyword associated with a file for organization and search
- **Content Analysis**: Optional client-side analysis to generate tags or metadata from file content
- **Encrypted Tag**: A tag that has been encrypted client-side before storage
- **Administrator**: A person with operational access to the Cortex System infrastructure
- **Collection**: A user-defined grouping of files such as a folder or category
- **Collection Metadata**: Information about a collection including name, description, and creation date
- **File-Collection Association**: A relationship linking a file to one or more collections
- **OIDC**: OpenID Connect, an identity layer on top of OAuth 2.0 for authentication
- **Cognito**: AWS service for user authentication and authorization
- **SigV4**: AWS Signature Version 4, the signing process for authenticating AWS API requests
- **Scoped Credentials**: Temporary AWS credentials with limited permissions specific to a user's resources
- **Account Password**: The password used to authenticate with the Cortex System and access the user account
- **Vault Password**: A separate password used exclusively for encrypting and decrypting the vault's master key
- **Vault**: A logical container holding all of a user's encrypted media, metadata, and collections
- **Vault Master Key**: The primary 256-bit encryption key derived from the vault password using Argon2id
- **Key Derivation**: The process of generating encryption keys from a password using Argon2id with specific parameters
- **HKDF**: HMAC-based Key Derivation Function used to derive multiple keys from the vault master key
- **Data Encryption Key**: A key derived from the vault master key specifically for encrypting file content
- **Metadata Encryption Key**: A key derived from the vault master key specifically for encrypting metadata
- **Device Registration Key**: A key derived from the vault master key for enabling multi-device access
- **Auth Key**: A key derived from the account password for authenticating with the server
- **Vault Salt**: A unique random value per vault stored on server for vault key derivation
- **Account Salt**: A unique random value per user account stored on server for authentication key derivation
- **Argon2id**: A memory-hard key derivation function resistant to GPU and side-channel attacks
- **ChaCha20-Poly1305**: An authenticated encryption algorithm providing confidentiality and integrity
- **Device**: A client application instance used to access the Cortex System
- **Key Recovery**: The process of deriving vault encryption keys on a new device using the vault password and vault salt
- **Local Key Storage**: Encrypted storage of vault keys on the client device only
- **Share Key**: A temporary encryption key generated for sharing specific files
- **Public Sharing**: Sharing files via URL containing the share key
- **User-to-User Sharing**: Sharing files by encrypting share keys with recipient's public key
- **Device Public Key**: A public key associated with a device for encrypted communication
- **Device Private Key**: A private key stored securely on a device for decryption
- **Key Rotation**: The periodic process of generating new encryption keys and re-encrypting data
- **Recovery Code**: A backup code provided at signup for account recovery

## Requirements

### Requirement 1

**User Story:** As a user, I want to securely upload my files to cloud storage, so that I can backup my data without the service provider accessing my content.

#### Acceptance Criteria

1. WHEN a user initiates an upload, THE Client Application SHALL encrypt the file using ChaCha20-Poly1305 with the data encryption key before transmission
2. WHEN encrypted data is transmitted, THE Cortex System SHALL store the encrypted data in the S3 Bucket without decryption
3. WHEN data is stored, THE Cortex System SHALL use S3 server-side encryption for additional security layer
4. WHEN a user uploads a file, THE Cortex System SHALL generate a presigned URL for direct S3 upload to optimize transfer speed
5. WHERE a file exceeds 5MB, THE Cortex System SHALL support S3 multipart upload for efficient large file handling

### Requirement 2

**User Story:** As a user, I want to manage metadata about my files, so that I can organize and retrieve my backups effectively while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user uploads a file, THE Client Application SHALL encrypt all metadata including filename, file size, MIME type, and timestamps using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN encrypted metadata is received, THE Cortex System SHALL store it in the DynamoDB Table without decryption
3. WHEN a user requests their file list, THE Cortex System SHALL return encrypted metadata that only the Client Application can decrypt
4. WHEN storing metadata, THE Cortex System SHALL associate each file with the user identifier and vault identifier without exposing content details
5. THE Cortex System SHALL maintain referential integrity between DynamoDB Table entries and S3 Bucket objects

### Requirement 3

**User Story:** As a user, I want to authenticate securely with the service using my account password, so that only I can access my encrypted backups.

#### Acceptance Criteria

1. WHEN a user attempts to access the Cortex System, THE Cortex System SHALL authenticate the user through AWS Cognito using the account password
2. WHEN authentication succeeds, THE Cortex System SHALL issue temporary scoped credentials using AWS SigV4 for API requests
3. WHEN scoped credentials are issued, THE Cortex System SHALL limit permissions to only the user's own resources in S3 and DynamoDB
4. WHEN a user makes an API request, THE API Gateway SHALL validate SigV4 signatures before routing to Lambda Functions
5. WHEN credential validation fails, THE Cortex System SHALL reject the request and return an authentication error
6. THE Cortex System SHALL ensure that vault encryption keys never leave the Client Application and are never transmitted to or stored by the service

### Requirement 4

**User Story:** As a user, I want to retrieve and download my backed-up files, so that I can restore my data when needed.

#### Acceptance Criteria

1. WHEN a user requests a file, THE Cortex System SHALL generate a presigned URL for direct S3 download
2. WHEN a user downloads encrypted data, THE Client Application SHALL decrypt the content using the vault's data encryption key
3. WHEN generating download URLs, THE Cortex System SHALL verify user ownership of the requested file
4. WHEN a download request is unauthorized, THE Cortex System SHALL reject the request and return an authorization error
5. THE Cortex System SHALL set presigned URL expiration to 15 minutes to limit exposure window

### Requirement 5

**User Story:** As a user, I want to delete my backed-up files, so that I can manage my storage and remove content I no longer need.

#### Acceptance Criteria

1. WHEN a user requests deletion of a file, THE Cortex System SHALL verify user ownership before proceeding
2. WHEN deletion is authorized, THE Cortex System SHALL remove the encrypted object from the S3 Bucket
3. WHEN an S3 object is deleted, THE Cortex System SHALL remove the corresponding metadata entry from the DynamoDB Table
4. WHEN deletion operations fail, THE Cortex System SHALL maintain consistency between the S3 Bucket and DynamoDB Table
5. THE Cortex System SHALL return confirmation of successful deletion to the Client Application

### Requirement 6

**User Story:** As a system operator, I want the service to run on AWS serverless infrastructure, so that it scales automatically and minimizes operational overhead.

#### Acceptance Criteria

1. THE Cortex System SHALL implement all API endpoints using AWS Lambda Functions written in Python
2. THE Cortex System SHALL expose API endpoints through AWS API Gateway with RESTful design
3. THE Cortex System SHALL define the API contract using a Smithy Model for service specification
4. WHEN API requests are received, THE API Gateway SHALL route them to appropriate Lambda Functions based on the Smithy Model
5. THE Cortex System SHALL use DynamoDB Table for all metadata storage with appropriate indexes for query performance

### Requirement 7

**User Story:** As a user, I want fast upload speeds for my files, so that I can efficiently backup large file collections.

#### Acceptance Criteria

1. WHEN uploading files, THE Cortex System SHALL provide presigned URLs for direct client-to-S3 upload bypassing Lambda Function
2. WHEN a presigned URL is generated, THE Lambda Function SHALL configure it with 15-minute expiration for upload performance
3. WHERE network conditions support concurrent operations, THE Client Application SHALL upload multiple files concurrently
4. WHERE a file exceeds 100MB, THE Cortex System SHALL support S3 multipart upload with minimum 5MB part size
5. THE Cortex System SHALL configure S3 Bucket with transfer acceleration for improved global upload speeds

### Requirement 8

**User Story:** As a developer, I want a well-defined API, so that I can build client applications that interact with the backup service.

#### Acceptance Criteria

1. THE Cortex System SHALL provide a Smithy Model defining all API operations, inputs, and outputs
2. THE Cortex System SHALL expose API endpoints for upload initiation, metadata management, download, and deletion operations
3. WHEN API errors occur, THE Cortex System SHALL return structured error responses with appropriate HTTP status codes
4. THE Cortex System SHALL version the API to allow backward-compatible evolution
5. THE Cortex System SHALL provide API documentation generated from the Smithy Model

### Requirement 9

**User Story:** As a security-conscious user, I want the system to maintain zero-knowledge architecture, so that I can trust that my private data remains private.

#### Acceptance Criteria

1. THE Client Application SHALL generate and manage all vault encryption keys locally without server involvement
2. THE Cortex System SHALL never receive, store, or have access to unencrypted file content or metadata
3. THE Cortex System SHALL never receive or store vault encryption keys in plaintext form
4. WHEN processing requests, THE Lambda Functions SHALL operate only on encrypted data without decryption capability
5. THE Cortex System SHALL store all data in encrypted form in both the S3 Bucket and DynamoDB Table

### Requirement 10

**User Story:** As a user, I want to list my backed-up files, so that I can see what content I have stored in the service.

#### Acceptance Criteria

1. WHEN a user requests their file list, THE Cortex System SHALL query the DynamoDB Table for items associated with the user's vault
2. WHEN returning file lists, THE Cortex System SHALL support pagination for efficient handling of large collections
3. WHEN a file list is returned, THE Cortex System SHALL include encrypted metadata for each item
4. THE Cortex System SHALL allow filtering and sorting of file lists based on encrypted timestamp fields
5. WHEN list queries execute, THE Cortex System SHALL use DynamoDB indexes to optimize query performance

### Requirement 11

**User Story:** As a user, I want to tag and categorize my files, so that I can organize and search my backups effectively while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user adds tags to a file, THE Client Application SHALL encrypt each tag using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN encrypted tags are received, THE Cortex System SHALL store them in the DynamoDB Table without decryption
3. WHEN a user searches by tag, THE Client Application SHALL encrypt the search term using the metadata encryption key before querying the Cortex System
4. WHEN the Cortex System processes tag queries, THE Lambda Function SHALL match encrypted tags without accessing plaintext tag values
5. WHERE the Client Application supports content analysis, THE Client Application SHALL perform analysis locally on the device to generate suggested tags

### Requirement 12

**User Story:** As a user, I want to organize my files into collections, so that I can group related files while maintaining privacy about my organizational structure.

#### Acceptance Criteria

1. WHEN a user creates a collection, THE Client Application SHALL encrypt the collection metadata using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN encrypted collection metadata is received, THE Cortex System SHALL store it in the DynamoDB Table without decryption
3. WHEN a user adds a file to a collection, THE Cortex System SHALL store the encrypted file-collection association
4. WHEN a user requests a collection, THE Cortex System SHALL return encrypted collection metadata and associated files
5. THE Cortex System SHALL support a file belonging to multiple collections simultaneously

### Requirement 13

**User Story:** As a user, I want to manage my collections, so that I can update, rename, and delete organizational structures as my needs change.

#### Acceptance Criteria

1. WHEN a user updates collection metadata, THE Client Application SHALL encrypt the new metadata using ChaCha20-Poly1305 with the metadata encryption key before sending to the Cortex System
2. WHEN a user removes a file from a collection, THE Cortex System SHALL delete the file-collection association while preserving the file
3. WHEN a user deletes a collection, THE Cortex System SHALL remove the collection metadata and all associated file-collection associations
4. WHEN a collection is deleted, THE Cortex System SHALL preserve all files that were in the collection
5. WHEN a user lists their collections, THE Cortex System SHALL return all encrypted collection metadata with file counts

### Requirement 14

**User Story:** As a user, I want to access my encrypted vault from multiple devices using my vault password, so that I can view and manage my files from any of my devices.

#### Acceptance Criteria

1. WHEN a user first creates a vault, THE Client Application SHALL derive a vault master key from the vault password and vault salt using Argon2id with 64MB memory, 3 iterations, and 4 parallelism
2. WHEN a vault master key is derived, THE Client Application SHALL use HKDF to derive data encryption key and metadata encryption key from the vault master key
3. WHEN derived keys are generated, THE Client Application SHALL store them encrypted locally on the device using device-specific encryption
4. WHEN a user accesses the vault from a new device, THE Client Application SHALL prompt for the vault password and retrieve the vault salt from the Cortex System
5. WHEN the vault salt is retrieved, THE Client Application SHALL derive the vault master key and all derived keys locally using the vault password
6. THE Cortex System SHALL never receive, store, or have access to the vault master key or any derived keys

### Requirement 15

**User Story:** As a user, I want to recover my vault encryption keys if I forget my vault password, so that I do not permanently lose access to my encrypted backups.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE Client Application SHALL generate a vault recovery key derived from the vault master key
2. WHEN a vault recovery key is generated, THE Client Application SHALL display it to the user once for secure offline storage
3. WHEN a user forgets their vault password, THE Client Application SHALL allow vault access using the vault recovery key to re-derive the vault master key
4. WHEN vault recovery key is used, THE Client Application SHALL allow the user to set a new vault password
5. THE Cortex System SHALL never receive, store, or have access to the vault recovery key

### Requirement 16

**User Story:** As a user, I want assurance that service administrators cannot access my data, so that I can trust the service with my private files.

#### Acceptance Criteria

1. THE Cortex System SHALL ensure that Administrators with AWS console access cannot decrypt stored files
2. THE Cortex System SHALL ensure that Administrators cannot decrypt metadata, tags, or collection information stored in the DynamoDB Table
3. THE Cortex System SHALL ensure that Administrators cannot determine the content type, subject matter, or organizational structure of stored files
4. THE Cortex System SHALL ensure that Administrators cannot access vault encryption keys as they are never transmitted to or stored by the server
5. WHEN Administrators access system logs, THE Cortex System SHALL ensure logs contain no plaintext user data or content information

### Requirement 17

**User Story:** As a user, I want to share specific files with others via public links, so that I can give access to selected files without compromising my entire vault.

#### Acceptance Criteria

1. WHEN a user initiates file sharing, THE Client Application SHALL generate a unique share key for the specific file
2. WHEN a share key is generated, THE Client Application SHALL create a share URL containing the file identifier and base64-encoded share key
3. WHEN creating a public share, THE Cortex System SHALL store only the file identifier and share metadata without access to the share key
4. WHEN a recipient accesses a share URL, THE Client Application SHALL extract the share key from the URL and use it to decrypt the file locally
5. THE Cortex System SHALL allow anonymous access to files via share identifier without requiring authentication

### Requirement 18

**User Story:** As a user, I want to control sharing permissions and expiration, so that I can limit access to my shared files.

#### Acceptance Criteria

1. WHEN creating a share, THE Client Application SHALL allow the user to specify time-limited expiration
2. WHEN a share has expired, THE Cortex System SHALL reject access requests and return an expiration error
3. WHERE a user enables password protection, THE Client Application SHALL derive an additional encryption key from the password and double-encrypt the share key in the URL
4. WHEN a password-protected share is accessed, THE Client Application SHALL prompt for the password before decrypting the share key
5. WHEN a user revokes a share, THE Cortex System SHALL mark the share identifier as invalid and reject future access attempts

### Requirement 20

**User Story:** As a user, I want my vault encryption keys to be automatically rotated, so that I maintain strong security over time without manual intervention.

#### Acceptance Criteria

1. WHEN 90 days have elapsed since the last key rotation, THE Client Application SHALL initiate automatic vault key rotation
2. WHEN key rotation begins, THE Client Application SHALL generate new derived keys from the vault master key using HKDF with updated context parameters
3. WHEN new keys are generated, THE Client Application SHALL re-encrypt all vault data in the background using the new data encryption key
4. WHEN re-encryption completes, THE Client Application SHALL update the locally stored encrypted key bundle with the new key material
5. WHILE key rotation is in progress, THE Client Application SHALL maintain access to data encrypted with both old and new keys during the transition period

### Requirement 21

**User Story:** As a user, I want strong password requirements and breach detection for both my account and vault passwords, so that my account and data remain secure against common attacks.

#### Acceptance Criteria

1. WHEN a user creates an account password or vault password, THE Client Application SHALL require a minimum length of 12 characters
2. WHEN a user creates an account password or vault password, THE Client Application SHALL require inclusion of uppercase letters, lowercase letters, numbers, and special characters
3. WHEN a user creates or changes an account password or vault password, THE Client Application SHALL validate the password against known breach databases
4. WHEN a breached password is detected, THE Client Application SHALL reject the password and prompt the user to choose a different password
5. WHERE a user enables two-factor authentication, THE Cortex System SHALL require a second authentication factor for account access

### Requirement 19

**User Story:** As a user, I want multiple recovery options for my account, so that I can regain access if I lose my account password.

#### Acceptance Criteria

1. WHEN a user completes account setup, THE Cortex System SHALL generate 10 account recovery codes and display them once
2. WHEN a user loses access to their account, THE Cortex System SHALL allow authentication using one of the account recovery codes
3. WHEN an account recovery code is used, THE Cortex System SHALL invalidate that specific code to prevent reuse
4. WHERE a user enables two-factor authentication, THE Cortex System SHALL provide backup codes for 2FA recovery
5. WHEN account recovery is successful, THE Client Application SHALL prompt the user to set a new account password

### Requirement 22

**User Story:** As a user, I want the system to store my vault salt securely, so that I can derive the same keys across devices while maintaining security.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE Cortex System SHALL generate a unique vault salt using a cryptographically secure random number generator
2. WHEN a vault salt is generated, THE Cortex System SHALL store it in the DynamoDB Table associated with the vault
3. WHEN a user accesses their vault from any device, THE Cortex System SHALL provide the vault salt to enable key derivation
4. THE Cortex System SHALL ensure each vault salt is unique and never reused across vaults
5. THE Cortex System SHALL treat the vault salt as non-secret information that can be stored and transmitted without encryption

### Requirement 23

**User Story:** As a user, I want to change my account password without re-encrypting my entire vault, so that I can update my credentials efficiently.

#### Acceptance Criteria

1. WHEN a user changes their account password, THE Cortex System SHALL update the account authentication credentials in AWS Cognito without affecting the vault encryption keys
2. WHEN an account password is changed, THE Client Application SHALL authenticate with AWS Cognito using the new account password
3. WHEN a user changes their vault password, THE Client Application SHALL derive a new vault master key from the new vault password and the existing vault salt using Argon2id
4. WHEN a new vault master key is derived, THE Client Application SHALL re-encrypt all vault data and metadata with keys derived from the new vault master key
5. WHILE vault password change is processing, THE Client Application SHALL perform re-encryption in the background to minimize user disruption
