# Requirements Document

## Introduction

Cortex is a zero-knowledge cloud-based photo and video backup solution that prioritizes user privacy through client-side encryption. The system runs on AWS infrastructure using serverless technologies (Lambda, API Gateway) and provides secure, encrypted storage where the service provider has no knowledge of the content being stored. Similar to services like Ente and Immich, Cortex enables users to safely backup their media while maintaining complete control over their data privacy.

## Glossary

- **Cortex System**: The complete cloud-based backup solution including API, storage, and database components
- **Client Application**: The frontend application that users interact with to upload and manage their media
- **Zero-Knowledge Architecture**: A design where the service provider cannot access or decrypt user data
- **Media Item**: A photo or video file uploaded by a user
- **Encryption Key**: A cryptographic key generated and managed by the client for encrypting media
- **Metadata**: Information about media items such as filename, size, upload date (stored encrypted)
- **User**: An authenticated individual using the Cortex System
- **Upload Session**: A temporary context for uploading one or more media items
- **S3 Bucket**: AWS Simple Storage Service container for storing encrypted media
- **DynamoDB Table**: AWS NoSQL database for storing encrypted metadata and user information
- **Lambda Function**: AWS serverless compute function handling API requests
- **API Gateway**: AWS service providing RESTful API endpoints
- **Smithy Model**: Interface definition language describing the API service contract
- **Multipart Upload**: S3 feature for uploading large files in chunks
- **Presigned URL**: Time-limited URL for direct S3 upload access
- **Tag**: A label or keyword associated with a media item for organization and search
- **Image Recognition**: Machine learning-based analysis to identify content in photos
- **Encrypted Tag**: A tag that has been encrypted client-side before storage
- **Administrator**: A person with operational access to the Cortex System infrastructure
- **Collection**: A user-defined grouping of media items such as an album or folder
- **Collection Metadata**: Information about a collection including name, description, and creation date
- **Media-Collection Association**: A relationship linking a media item to one or more collections
- **OIDC**: OpenID Connect, an identity layer on top of OAuth 2.0 for authentication
- **Cognito**: AWS service for user authentication and authorization
- **SigV4**: AWS Signature Version 4, the signing process for authenticating AWS API requests
- **Scoped Credentials**: Temporary AWS credentials with limited permissions specific to a user's resources
- **Master Key**: The primary encryption key used to encrypt user data
- **Key Derivation**: The process of generating encryption keys from a user password or passphrase
- **Encrypted Key Bundle**: A user's master key encrypted with a password-derived key for storage
- **Device**: A client application instance used to access the Cortex System
- **Key Recovery**: The process of obtaining encryption keys on a new device

## Requirements

### Requirement 1

**User Story:** As a user, I want to securely upload my photos and videos to cloud storage, so that I can backup my media without the service provider accessing my content.

#### Acceptance Criteria

1. WHEN a user initiates an upload, THE Client Application SHALL encrypt the media item using client-side encryption before transmission
2. WHEN encrypted media is transmitted, THE Cortex System SHALL store the encrypted data in the S3 Bucket without decryption
3. WHEN media is stored, THE Cortex System SHALL use S3 server-side encryption for additional security layer
4. WHEN a user uploads a media item, THE Cortex System SHALL generate a presigned URL for direct S3 upload to optimize transfer speed
5. WHERE a media item exceeds 100MB, THE Cortex System SHALL support multipart upload for efficient large file handling

### Requirement 2

**User Story:** As a user, I want to manage metadata about my media, so that I can organize and retrieve my backups effectively while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user uploads a media item, THE Client Application SHALL encrypt all metadata including filename, file size, and timestamps before sending to the Cortex System
2. WHEN encrypted metadata is received, THE Cortex System SHALL store it in the DynamoDB Table without decryption
3. WHEN a user requests their media list, THE Cortex System SHALL return encrypted metadata that only the Client Application can decrypt
4. WHEN storing metadata, THE Cortex System SHALL associate each media item with the user identifier without exposing content details
5. THE Cortex System SHALL maintain referential integrity between DynamoDB Table entries and S3 Bucket objects

### Requirement 3

**User Story:** As a user, I want to authenticate securely with the service, so that only I can access my encrypted backups.

#### Acceptance Criteria

1. WHEN a user attempts to access the Cortex System, THE Cortex System SHALL authenticate the user through AWS Cognito with OIDC support
2. WHEN authentication succeeds, THE Cortex System SHALL issue temporary scoped credentials using AWS SigV4 for API requests
3. WHEN scoped credentials are issued, THE Cortex System SHALL limit permissions to only the user's own resources in S3 and DynamoDB
4. WHEN a user makes an API request, THE API Gateway SHALL validate SigV4 signatures before routing to Lambda Functions
5. WHEN credential validation fails, THE Cortex System SHALL reject the request and return an authentication error
6. THE Cortex System SHALL ensure that encryption keys never leave the Client Application and are never transmitted to or stored by the service

### Requirement 4

**User Story:** As a user, I want to retrieve and download my backed-up media, so that I can restore my photos and videos when needed.

#### Acceptance Criteria

1. WHEN a user requests a media item, THE Cortex System SHALL generate a presigned URL for direct S3 download
2. WHEN a user downloads encrypted media, THE Client Application SHALL decrypt the content using the user's encryption key
3. WHEN generating download URLs, THE Cortex System SHALL verify user ownership of the requested media item
4. WHEN a download request is unauthorized, THE Cortex System SHALL reject the request and return an authorization error
5. THE Cortex System SHALL set presigned URL expiration to 15 minutes to limit exposure window

### Requirement 5

**User Story:** As a user, I want to delete my backed-up media, so that I can manage my storage and remove content I no longer need.

#### Acceptance Criteria

1. WHEN a user requests deletion of a media item, THE Cortex System SHALL verify user ownership before proceeding
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

**User Story:** As a user, I want fast upload speeds for my media, so that I can efficiently backup large photo and video collections.

#### Acceptance Criteria

1. WHEN uploading media, THE Cortex System SHALL provide presigned URLs for direct client-to-S3 upload bypassing Lambda
2. WHEN a presigned URL is generated, THE Lambda Function SHALL configure it for optimized upload performance
3. WHERE network conditions allow, THE Client Application SHALL upload multiple media items concurrently
4. WHEN uploading large files, THE Cortex System SHALL support S3 multipart upload with minimum 5MB part size
5. THE Cortex System SHALL configure S3 Bucket with transfer acceleration when available for improved global upload speeds

### Requirement 8

**User Story:** As a developer, I want a well-defined API, so that I can build client applications that interact with the backup service.

#### Acceptance Criteria

1. THE Cortex System SHALL provide a Smithy Model defining all API operations, inputs, and outputs
2. THE Cortex System SHALL expose API endpoints for upload initiation, metadata management, download, and deletion operations
3. WHEN API errors occur, THE Cortex System SHALL return structured error responses with appropriate HTTP status codes
4. THE Cortex System SHALL version the API to allow backward-compatible evolution
5. THE Cortex System SHALL provide API documentation generated from the Smithy Model

### Requirement 9

**User Story:** As a security-conscious user, I want the system to maintain zero-knowledge architecture, so that I can trust that my private media remains private.

#### Acceptance Criteria

1. THE Client Application SHALL generate and manage all encryption keys locally without server involvement
2. THE Cortex System SHALL never receive, store, or have access to unencrypted media content or metadata
3. THE Cortex System SHALL never receive or store user encryption keys
4. WHEN processing requests, THE Lambda Functions SHALL operate only on encrypted data without decryption capability
5. THE Cortex System SHALL store all data in encrypted form in both the S3 Bucket and DynamoDB Table

### Requirement 10

**User Story:** As a user, I want to list my backed-up media, so that I can see what content I have stored in the service.

#### Acceptance Criteria

1. WHEN a user requests their media list, THE Cortex System SHALL query the DynamoDB Table for items associated with the user
2. WHEN returning media lists, THE Cortex System SHALL support pagination for efficient handling of large collections
3. WHEN a media list is returned, THE Cortex System SHALL include encrypted metadata for each item
4. THE Cortex System SHALL allow filtering and sorting of media lists based on encrypted timestamp fields
5. WHEN list queries execute, THE Cortex System SHALL use DynamoDB indexes to optimize query performance

### Requirement 11

**User Story:** As a user, I want to tag and categorize my media using image recognition, so that I can organize and search my backups effectively while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user uploads a media item, THE Client Application SHALL perform image recognition locally to generate tags
2. WHEN tags are generated, THE Client Application SHALL encrypt each tag before sending to the Cortex System
3. WHEN encrypted tags are received, THE Cortex System SHALL store them in the DynamoDB Table without decryption
4. WHEN a user searches by tag, THE Client Application SHALL encrypt the search term before querying the Cortex System
5. WHEN the Cortex System processes tag queries, THE Lambda Function SHALL match encrypted tags without accessing plaintext values

### Requirement 12

**User Story:** As a user, I want to organize my media into collections, so that I can group related photos and videos while maintaining privacy about my organizational structure.

#### Acceptance Criteria

1. WHEN a user creates a collection, THE Client Application SHALL encrypt the collection metadata before sending to the Cortex System
2. WHEN encrypted collection metadata is received, THE Cortex System SHALL store it in the DynamoDB Table without decryption
3. WHEN a user adds a media item to a collection, THE Cortex System SHALL store the encrypted media-collection association
4. WHEN a user requests a collection, THE Cortex System SHALL return encrypted collection metadata and associated media items
5. THE Cortex System SHALL support a media item belonging to multiple collections simultaneously

### Requirement 13

**User Story:** As a user, I want to manage my collections, so that I can update, rename, and delete organizational structures as my needs change.

#### Acceptance Criteria

1. WHEN a user updates collection metadata, THE Client Application SHALL encrypt the new metadata before sending to the Cortex System
2. WHEN a user removes a media item from a collection, THE Cortex System SHALL delete the media-collection association while preserving the media item
3. WHEN a user deletes a collection, THE Cortex System SHALL remove the collection metadata and all associated media-collection associations
4. WHEN a collection is deleted, THE Cortex System SHALL preserve all media items that were in the collection
5. WHEN a user lists their collections, THE Cortex System SHALL return all encrypted collection metadata with item counts

### Requirement 14

**User Story:** As a user, I want to access my encrypted backups from multiple devices, so that I can view and manage my media from any of my devices.

#### Acceptance Criteria

1. WHEN a user first sets up the Client Application, THE Client Application SHALL derive a master key from a user-provided password using key derivation
2. WHEN a master key is generated, THE Client Application SHALL encrypt the master key with a password-derived key to create an encrypted key bundle
3. WHEN an encrypted key bundle is created, THE Cortex System SHALL store it in the DynamoDB Table without access to the plaintext master key
4. WHEN a user logs in from a new device, THE Client Application SHALL retrieve the encrypted key bundle from the Cortex System
5. WHEN an encrypted key bundle is retrieved, THE Client Application SHALL decrypt it using the user's password to obtain the master key

### Requirement 15

**User Story:** As a user, I want to recover my encryption keys if I forget my password, so that I do not permanently lose access to my encrypted backups.

#### Acceptance Criteria

1. WHEN a user sets up their account, THE Client Application SHALL generate a recovery key for key recovery purposes
2. WHEN a recovery key is generated, THE Client Application SHALL display it to the user for secure offline storage
3. WHEN a user forgets their password, THE Client Application SHALL allow key recovery using the recovery key
4. WHEN recovery key authentication succeeds, THE Client Application SHALL allow the user to set a new password and re-encrypt the key bundle
5. THE Cortex System SHALL never have access to the recovery key in plaintext form

### Requirement 16

**User Story:** As a user, I want assurance that service administrators cannot access my data, so that I can trust the service with my private media.

#### Acceptance Criteria

1. THE Cortex System SHALL ensure that Administrators with AWS console access cannot decrypt stored media items
2. THE Cortex System SHALL ensure that Administrators cannot decrypt metadata, tags, or collection information stored in the DynamoDB Table
3. THE Cortex System SHALL ensure that Administrators cannot determine the content type, subject matter, or organizational structure of stored media
4. THE Cortex System SHALL ensure that Administrators cannot decrypt encrypted key bundles without the user's password
5. WHEN Administrators access system logs, THE Cortex System SHALL ensure logs contain no plaintext user data or content information
