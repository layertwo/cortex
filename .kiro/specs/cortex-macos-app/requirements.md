# Requirements Document: Cortex macOS Native Application

## Introduction

The Cortex macOS Native Application is a privacy-first media backup client that provides a native macOS user experience for the Cortex zero-knowledge backup system. The application maintains strict client-side encryption, ensuring all sensitive data is encrypted before transmission to the backend. It integrates with macOS features including the file system, keychain, and system notifications while providing seamless interaction with the existing Cortex API.

## Glossary

- **Cortex_API**: The existing AWS Lambda-based REST API that handles vault operations, item management, and sharing
- **macOS_App**: The native Swift/SwiftUI application running on macOS
- **Account_Password**: User credential for AWS Cognito authentication, can be changed without re-encrypting vault data
- **Vault_Password**: User credential exclusively for deriving vault encryption keys, never transmitted to server
- **Vault_Master_Key**: 256-bit key derived from Vault_Password using Argon2id
- **Encryption_Engine**: Client-side component implementing ChaCha20-Poly1305, Argon2id, and HKDF
- **Item**: Generic term for any content stored in Cortex (MEDIA, NOTE, TASK, EVENT)
- **Collection**: User-created grouping of items
- **Share**: Time-limited, optionally password-protected link to an item
- **Keychain**: macOS secure storage for sensitive credentials

## Requirements

### Requirement 1: Application Architecture and Setup

**User Story:** As a developer, I want a well-structured native macOS application, so that the codebase is maintainable and follows Swift/SwiftUI best practices.

#### Acceptance Criteria

1. THE macOS_App SHALL be implemented using Swift 5.9+ and SwiftUI
2. THE macOS_App SHALL target macOS 13.0 (Ventura) or later
3. THE macOS_App SHALL use Swift Package Manager for dependency management
4. THE macOS_App SHALL follow MVVM architecture pattern with clear separation of concerns
5. THE macOS_App SHALL organize code into modules: UI, Networking, Encryption, Storage, Models

### Requirement 2: Client-Side Encryption Implementation

**User Story:** As a security-conscious user, I want all my data encrypted on my device before upload, so that the server never has access to my unencrypted content.

#### Acceptance Criteria

1. THE Encryption_Engine SHALL implement ChaCha20-Poly1305 with 256-bit keys, 96-bit nonces, and 128-bit authentication tags
2. WHEN deriving the Vault_Master_Key, THE Encryption_Engine SHALL use Argon2id with 64MB memory, 3 iterations, and 4 parallelism
3. THE Encryption_Engine SHALL use HKDF to derive multiple keys from Vault_Master_Key with contexts: "cortex-data-encryption-v1", "cortex-metadata-encryption-v1", "cortex-share-key-derivation-v1"
4. THE Encryption_Engine SHALL generate cryptographically random 96-bit nonces for each encryption operation
5. THE Encryption_Engine SHALL encrypt all item metadata (filenames, dates, locations) before transmission
6. THE Encryption_Engine SHALL use deterministic HMAC-SHA256 for tag encryption to enable server-side search
7. WHEN encrypting items, THE Encryption_Engine SHALL never transmit unencrypted data to the server
8. THE Encryption_Engine SHALL implement encryption and decryption operations asynchronously to avoid blocking the UI

### Requirement 3: Two-Password Security Model

**User Story:** As a user, I want separate account and vault passwords, so that I can change my account credentials without re-encrypting all my data.

#### Acceptance Criteria

1. WHEN creating an account, THE macOS_App SHALL prompt for both Account_Password and Vault_Password
2. THE macOS_App SHALL use Account_Password exclusively for Cognito authentication
3. THE macOS_App SHALL use Vault_Password exclusively for deriving encryption keys
4. THE macOS_App SHALL never transmit Vault_Password to the server
5. WHEN changing Account_Password, THE macOS_App SHALL not require re-encryption of vault data
6. THE macOS_App SHALL validate Account_Password meets minimum requirements: 12 characters, uppercase, lowercase, numbers, special characters
7. THE macOS_App SHALL validate Vault_Password meets minimum requirements: 12 characters, uppercase, lowercase, numbers, special characters
8. THE macOS_App SHALL check passwords against Have I Been Pwned API using k-anonymity model (SHA-1 hash, first 5 characters)

### Requirement 4: Keychain Integration

**User Story:** As a user, I want my credentials securely stored in macOS Keychain, so that I don't have to re-enter them every time I use the app.

#### Acceptance Criteria

1. WHEN a user successfully authenticates, THE macOS_App SHALL store Account_Password in Keychain with appropriate access controls
2. THE macOS_App SHALL store Vault_Password in Keychain with appropriate access controls
3. THE macOS_App SHALL store Cognito tokens (access, refresh, ID) in Keychain
4. THE macOS_App SHALL use Keychain access control flags to require device authentication for sensitive operations
5. WHEN the app launches, THE macOS_App SHALL attempt to retrieve credentials from Keychain for automatic login
6. WHEN a user logs out, THE macOS_App SHALL remove all credentials from Keychain
7. THE macOS_App SHALL handle Keychain errors gracefully and prompt for manual credential entry when needed

### Requirement 5: Authentication and Session Management

**User Story:** As a user, I want to securely authenticate with my account, so that I can access my encrypted vault.

#### Acceptance Criteria

1. WHEN a user enters credentials, THE macOS_App SHALL authenticate with Cognito using Account_Password
2. WHEN authentication succeeds, THE macOS_App SHALL retrieve vault salt from Cortex_API
3. WHEN vault salt is retrieved, THE macOS_App SHALL derive Vault_Master_Key using Vault_Password and vault salt
4. THE macOS_App SHALL automatically refresh Cognito tokens before expiration
5. WHEN token refresh fails, THE macOS_App SHALL prompt for re-authentication
6. THE macOS_App SHALL maintain session state across app restarts using Keychain-stored tokens
7. WHEN network connectivity is lost, THE macOS_App SHALL queue operations and retry when connectivity is restored

### Requirement 6: File System Integration

**User Story:** As a user, I want to backup any files from my Mac, so that I can protect documents, videos, and other important files.

#### Acceptance Criteria

1. THE macOS_App SHALL support drag-and-drop of files and folders onto the app window
2. THE macOS_App SHALL provide a file picker for selecting files to backup
3. THE macOS_App SHALL support backing up files of any type (not just photos/videos)
4. WHEN a folder is selected, THE macOS_App SHALL recursively backup all files within it
5. THE macOS_App SHALL preserve file metadata (name, creation date, modification date, file type)
6. THE macOS_App SHALL handle large files using multipart upload (5MB minimum part size)
7. THE macOS_App SHALL display upload progress for each file with percentage and estimated time remaining

### Requirement 7: Media Upload Flow

**User Story:** As a user, I want to upload media to my vault, so that my files are backed up securely.

#### Acceptance Criteria

1. WHEN a user initiates upload, THE macOS_App SHALL encrypt the file content locally
2. WHEN encryption completes, THE macOS_App SHALL call POST /v1/items/upload/init to get a presigned S3 URL
3. WHEN presigned URL is received, THE macOS_App SHALL upload encrypted content directly to S3
4. WHEN S3 upload completes, THE macOS_App SHALL call POST /v1/items/upload/complete with encrypted metadata
5. THE macOS_App SHALL support concurrent uploads with configurable maximum (default: 3)
6. THE macOS_App SHALL support pause and resume for uploads
7. WHEN upload fails, THE macOS_App SHALL retry with exponential backoff (max 3 retries)
8. THE macOS_App SHALL display upload queue with status for each item (pending, uploading, completed, failed)

### Requirement 8: Media Download and Viewing

**User Story:** As a user, I want to view and download my backed-up media, so that I can access my files when needed.

#### Acceptance Criteria

1. WHEN a user requests to view an item, THE macOS_App SHALL call GET /v1/items/{id}/download to get a presigned S3 URL
2. WHEN presigned URL is received, THE macOS_App SHALL download encrypted content from S3
3. WHEN download completes, THE macOS_App SHALL decrypt the content locally
4. WHEN decryption completes, THE macOS_App SHALL display the media in a native viewer
5. THE macOS_App SHALL support Quick Look for previewing media without full download
6. THE macOS_App SHALL cache decrypted thumbnails locally for faster browsing
7. WHEN a user exports an item, THE macOS_App SHALL save the decrypted file to a user-selected location
8. THE macOS_App SHALL support batch download and export of multiple items

### Requirement 9: Item Management

**User Story:** As a user, I want to organize and manage my backed-up items, so that I can find and work with my files efficiently.

#### Acceptance Criteria

1. THE macOS_App SHALL display a grid view of all items with thumbnails
2. THE macOS_App SHALL support filtering items by type (MEDIA, NOTE, TASK, EVENT)
3. THE macOS_App SHALL support sorting items by date, name, or size
4. THE macOS_App SHALL support searching items by encrypted tags
5. WHEN a user deletes an item, THE macOS_App SHALL call DELETE /v1/items/{id} and remove it from local cache
6. THE macOS_App SHALL support editing item metadata (tags, notes)
7. THE macOS_App SHALL display item details including size, upload date, and encrypted metadata
8. THE macOS_App SHALL implement infinite scrolling or pagination for large item lists

### Requirement 10: Collections Management

**User Story:** As a user, I want to organize items into collections, so that I can group related content together.

#### Acceptance Criteria

1. WHEN a user creates a collection, THE macOS_App SHALL call POST /v1/collections with encrypted metadata
2. THE macOS_App SHALL display all collections in a sidebar or dedicated view
3. WHEN a user adds items to a collection, THE macOS_App SHALL call POST /v1/collections/{id}/items
4. WHEN a user removes items from a collection, THE macOS_App SHALL call DELETE /v1/collections/{id}/items/{itemId}
5. THE macOS_App SHALL support drag-and-drop to add items to collections
6. THE macOS_App SHALL display collection item count and total size
7. WHEN a user deletes a collection, THE macOS_App SHALL call DELETE /v1/collections/{id} without deleting the items
8. THE macOS_App SHALL support renaming collections by updating encrypted metadata

### Requirement 11: Tag Management and Search

**User Story:** As a user, I want to tag and search my items, so that I can quickly find specific content.

#### Acceptance Criteria

1. WHEN a user adds a tag to an item, THE macOS_App SHALL encrypt the tag using deterministic HMAC-SHA256
2. THE macOS_App SHALL normalize tags to lowercase before encryption
3. WHEN a user searches by tag, THE macOS_App SHALL encrypt the search term and call GET /v1/tags/search
4. THE macOS_App SHALL display tag suggestions based on previously used tags
5. THE macOS_App SHALL support multiple tags per item
6. THE macOS_App SHALL display a tag cloud or list showing all used tags
7. WHEN a user clicks a tag, THE macOS_App SHALL filter items to show only those with that tag
8. THE macOS_App SHALL support tag autocomplete while typing

### Requirement 12: Sharing Functionality

**User Story:** As a user, I want to share items with others via secure links, so that I can collaborate without compromising security.

#### Acceptance Criteria

1. WHEN a user shares an item, THE macOS_App SHALL call POST /v1/shares to create a share
2. THE macOS_App SHALL generate a share URL containing the share ID and embedded share key
3. THE macOS_App SHALL support optional password protection for shares
4. THE macOS_App SHALL support setting expiration time for shares (1 hour, 1 day, 1 week, 1 month, never)
5. WHEN a share is created, THE macOS_App SHALL copy the share URL to clipboard
6. THE macOS_App SHALL display a list of active shares with access count and expiration
7. WHEN a user revokes a share, THE macOS_App SHALL call DELETE /v1/shares/{id}
8. THE macOS_App SHALL support viewing share analytics (access count, last accessed time)

### Requirement 13: Account Recovery

**User Story:** As a user, I want to recover my account if I forget my password, so that I don't lose access to my data.

#### Acceptance Criteria

1. WHEN a user sets up account recovery, THE macOS_App SHALL call POST /v1/recovery/codes to generate 10 recovery codes
2. THE macOS_App SHALL display recovery codes in format XXXX-XXXX-XXXX-XXXX
3. THE macOS_App SHALL prompt user to save recovery codes securely offline
4. THE macOS_App SHALL allow printing or exporting recovery codes to a file
5. WHEN a user initiates account recovery, THE macOS_App SHALL call POST /v1/auth/recover with a recovery code
6. THE macOS_App SHALL mark used recovery codes as invalid after successful recovery
7. THE macOS_App SHALL display remaining valid recovery codes count
8. THE macOS_App SHALL support regenerating recovery codes (invalidates old codes)

### Requirement 14: Vault Recovery

**User Story:** As a user, I want to recover my vault if I forget my vault password, so that I can regain access to my encrypted data.

#### Acceptance Criteria

1. WHEN a user creates a vault, THE macOS_App SHALL generate a BIP39 mnemonic (12-24 words) as vault recovery key
2. THE macOS_App SHALL display the vault recovery key once with clear warnings about secure storage
3. THE macOS_App SHALL never transmit the vault recovery key to the server
4. THE macOS_App SHALL allow user to copy or export vault recovery key
5. WHEN a user initiates vault recovery, THE macOS_App SHALL prompt for vault recovery key
6. WHEN vault recovery key is entered, THE macOS_App SHALL derive the Vault_Master_Key from the mnemonic
7. THE macOS_App SHALL validate vault recovery key by attempting to decrypt a test item
8. WHEN vault recovery succeeds, THE macOS_App SHALL prompt user to set a new Vault_Password

### Requirement 15: Menu Bar Integration

**User Story:** As a user, I want quick access to Cortex from the menu bar, so that I can backup files without opening the full app.

#### Acceptance Criteria

1. THE macOS_App SHALL display an icon in the macOS menu bar
2. WHEN the menu bar icon is clicked, THE macOS_App SHALL display a dropdown menu
3. THE menu bar dropdown SHALL show recent uploads and current upload progress
4. THE menu bar dropdown SHALL provide quick actions: Upload Files, Open App, Preferences, Quit
5. THE macOS_App SHALL support drag-and-drop of files onto the menu bar icon for quick upload
6. THE macOS_App SHALL display upload progress in the menu bar icon (percentage or animated indicator)
7. THE macOS_App SHALL support running as a menu bar-only app without a dock icon (user preference)

### Requirement 16: Notifications

**User Story:** As a user, I want to receive notifications about upload status, so that I know when my backups are complete.

#### Acceptance Criteria

1. WHEN an upload completes successfully, THE macOS_App SHALL display a system notification
2. WHEN an upload fails, THE macOS_App SHALL display a system notification with error details
3. WHEN all queued uploads complete, THE macOS_App SHALL display a summary notification
4. THE macOS_App SHALL request notification permissions on first launch
5. THE macOS_App SHALL support disabling notifications in preferences
6. THE macOS_App SHALL support notification actions (e.g., "View Item", "Retry Upload")
7. WHEN a notification is clicked, THE macOS_App SHALL open the app and navigate to the relevant item

### Requirement 17: Preferences and Settings

**User Story:** As a user, I want to configure app behavior, so that it works the way I prefer.

#### Acceptance Criteria

1. THE macOS_App SHALL provide a preferences window accessible via menu or keyboard shortcut
2. THE macOS_App SHALL support configuring maximum concurrent uploads (1-10)
3. THE macOS_App SHALL support configuring watched folders for automatic backup
4. THE macOS_App SHALL support configuring notification preferences
5. THE macOS_App SHALL support configuring cache size limit for thumbnails
6. THE macOS_App SHALL support configuring whether to run as menu bar-only app
7. THE macOS_App SHALL support viewing storage usage (total items, total size, by type)
8. THE macOS_App SHALL support clearing local cache

### Requirement 18: Offline Support

**User Story:** As a user, I want the app to work offline, so that I can queue uploads and view cached content without internet.

#### Acceptance Criteria

1. WHEN network connectivity is unavailable, THE macOS_App SHALL queue upload operations
2. WHEN network connectivity is restored, THE macOS_App SHALL automatically process queued operations
3. THE macOS_App SHALL cache decrypted thumbnails for offline browsing
4. THE macOS_App SHALL cache item metadata for offline viewing
5. THE macOS_App SHALL display network status indicator in the UI
6. WHEN offline, THE macOS_App SHALL disable operations that require network (download, share, search)
7. THE macOS_App SHALL persist upload queue across app restarts
8. THE macOS_App SHALL support viewing and managing queued uploads while offline

### Requirement 19: Error Handling and Logging

**User Story:** As a developer, I want comprehensive error handling and logging, so that I can diagnose and fix issues.

#### Acceptance Criteria

1. THE macOS_App SHALL log all API requests and responses (excluding sensitive data)
2. THE macOS_App SHALL log encryption/decryption operations (excluding keys and plaintext)
3. THE macOS_App SHALL never log Account_Password, Vault_Password, encryption keys, or unencrypted content
4. WHEN an error occurs, THE macOS_App SHALL display user-friendly error messages
5. THE macOS_App SHALL provide detailed error information in logs for debugging
6. THE macOS_App SHALL support exporting logs for troubleshooting
7. THE macOS_App SHALL implement crash reporting with user consent
8. THE macOS_App SHALL handle API errors gracefully with appropriate retry logic

### Requirement 20: Performance and Optimization

**User Story:** As a user, I want the app to be fast and responsive, so that I can work efficiently.

#### Acceptance Criteria

1. THE macOS_App SHALL load and display the item list within 2 seconds on launch
2. THE macOS_App SHALL render thumbnails progressively as they load
3. THE macOS_App SHALL implement lazy loading for large item lists
4. THE macOS_App SHALL perform encryption/decryption operations on background threads
5. THE macOS_App SHALL cache API responses with appropriate TTL (5 minutes for item lists)
6. THE macOS_App SHALL implement efficient memory management for large media files
7. THE macOS_App SHALL support hardware-accelerated video decoding for playback
8. THE macOS_App SHALL minimize battery impact by throttling background operations

### Requirement 21: Accessibility

**User Story:** As a user with accessibility needs, I want the app to support assistive technologies, so that I can use it effectively.

#### Acceptance Criteria

1. THE macOS_App SHALL support VoiceOver with descriptive labels for all UI elements
2. THE macOS_App SHALL support keyboard navigation for all functionality
3. THE macOS_App SHALL support system font size preferences
4. THE macOS_App SHALL provide sufficient color contrast for text and UI elements
5. THE macOS_App SHALL support reduced motion preferences
6. THE macOS_App SHALL provide alternative text for all images and icons
7. THE macOS_App SHALL support system appearance (light/dark mode)
8. THE macOS_App SHALL follow Apple Human Interface Guidelines for accessibility
