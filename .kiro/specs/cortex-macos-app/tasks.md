# Implementation Tasks: Cortex macOS Native Application

## Phase 1: Project Setup and Foundation

### 1. Project Initialization
**References:** Requirement 1 (Application Architecture and Setup)

- [ ] 1.1 Create Xcode project for macOS application targeting macOS 13.0+
- [ ] 1.2 Configure Swift Package Manager with Package.swift
- [ ] 1.3 Add required dependencies: CryptoKit, CryptoSwift, Argon2Swift
- [ ] 1.4 Set up project structure following MVVM architecture (App/, UI/, Services/, Core/, Models/, Utilities/, Resources/)
- [ ] 1.5 Configure Info.plist with required permissions (file access, notifications, keychain)
- [ ] 1.6 Create .gitignore for Xcode and Swift projects

### 2. Core Data Models
**References:** Design Document - Data Models section

- [ ] 2.1 Implement User model with Identifiable and Codable conformance
- [ ] 2.2 Implement Vault model with vaultSalt property
- [ ] 2.3 Implement Item model with ItemType enum (MEDIA, NOTE, TASK, EVENT)
- [ ] 2.4 Implement ItemMetadata model with Location support
- [ ] 2.5 Implement Collection and CollectionMetadata models
- [ ] 2.6 Implement Share model with expiration and access tracking
- [ ] 2.7 Implement EncryptedData and EncryptedMetadata models
- [ ] 2.8 Implement UploadTask model with UploadStatus enum
- [ ] 2.9 Implement UploadProgress and DownloadProgress models

### 3. Utilities and Extensions
**References:** Requirement 19 (Error Handling and Logging)

- [ ] 3.1 Create Data+Extensions.swift with hex encoding/decoding and base64 utilities
- [ ] 3.2 Create String+Extensions.swift with validation helpers
- [ ] 3.3 Create Date+Extensions.swift with ISO8601 formatting
- [ ] 3.4 Create Constants.swift with API endpoints, encryption contexts, and configuration values
- [ ] 3.5 Create Logger.swift with structured logging (exclude sensitive data)
- [ ] 3.6 Create custom error types (CortexError enum with cases for network, encryption, auth, storage)

## Phase 2: Encryption Engine

### 4. Key Derivation Implementation
**References:** Requirement 2 (Client-Side Encryption Implementation)

- [ ] 4.1 Implement KeyDerivation.swift with Argon2id integration (64MB memory, 3 iterations, 4 parallelism)
- [ ] 4.2 Implement deriveVaultMasterKey function using Argon2Swift
- [ ] 4.3 Implement HKDF-based key derivation for data encryption key (context: "cortex-data-encryption-v1")
- [ ] 4.4 Implement HKDF-based key derivation for metadata encryption key (context: "cortex-metadata-encryption-v1")
- [ ] 4.5 Implement HKDF-based key derivation for share key (context: "cortex-share-key-derivation-v1")
- [ ] 4.6 Create VaultKeys struct to hold derived keys

### 5. ChaCha20-Poly1305 Encryption
**References:** Requirement 2 (Client-Side Encryption Implementation)

- [ ] 5.1 Implement ChaCha20Poly1305.swift using CryptoKit's ChaChaPoly
- [ ] 5.2 Implement encrypt function with 256-bit keys, 96-bit nonces, 128-bit tags
- [ ] 5.3 Implement decrypt function with authentication tag verification
- [ ] 5.4 Implement generateNonce function using SecRandomCopyBytes
- [ ] 5.5 Add error handling for encryption/decryption failures

### 6. Tag Encryption and EncryptionEngine
**References:** Requirement 2 (Client-Side Encryption Implementation), Requirement 11 (Tag Management)

- [ ] 6.1 Implement TagEncryption.swift with deterministic HMAC-SHA256
- [ ] 6.2 Implement tag normalization (lowercase) before encryption
- [ ] 6.3 Create EncryptionEngine actor combining all encryption operations
- [ ] 6.4 Implement async encrypt/decrypt methods in EncryptionEngine
- [ ] 6.5 Add thread-safety using Swift actor model
- [ ] 6.6 Write unit tests for encryption round-trip property

## Phase 3: Keychain and Storage

### 7. Keychain Manager
**References:** Requirement 4 (Keychain Integration)

- [ ] 7.1 Implement KeychainManager actor using Security framework
- [ ] 7.2 Implement saveAccountPassword with kSecAttrAccessibleWhenUnlockedThisDeviceOnly
- [ ] 7.3 Implement getAccountPassword with proper error handling
- [ ] 7.4 Implement saveVaultPassword with device-only access control
- [ ] 7.5 Implement getVaultPassword with proper error handling
- [ ] 7.6 Implement saveTokens for Cognito tokens (access, refresh, ID)
- [ ] 7.7 Implement getTokens with proper error handling
- [ ] 7.8 Implement deleteAllCredentials for logout
- [ ] 7.9 Add keychain error handling and logging (exclude sensitive data)

### 8. Local Storage and Cache
**References:** Requirement 18 (Offline Support), Requirement 20 (Performance)

- [ ] 8.1 Implement StorageManager actor for persistent storage
- [ ] 8.2 Implement CacheManager with LRU eviction policy
- [ ] 8.3 Implement ThumbnailCache with configurable size limit
- [ ] 8.4 Implement upload queue persistence using FileManager
- [ ] 8.5 Implement cached metadata storage for offline viewing
- [ ] 8.6 Add cache clearing functionality

## Phase 4: Networking Layer

### 9. API Client Foundation
**References:** Design Document - APIClient interface

- [ ] 9.1 Create APIEndpoints.swift with all endpoint URLs
- [ ] 9.2 Create APIRequest protocol for request configuration
- [ ] 9.3 Create APIResponse protocol for response parsing
- [ ] 9.4 Implement APIClient actor using URLSession with async/await
- [ ] 9.5 Add request logging (exclude sensitive data)
- [ ] 9.6 Add response logging with error details

### 10. Authentication API Methods
**References:** Requirement 5 (Authentication and Session Management)

- [ ] 10.1 Implement login method with Cognito authentication
- [ ] 10.2 Implement refreshToken method with automatic retry
- [ ] 10.3 Implement automatic token refresh on 401 responses
- [ ] 10.4 Implement recoverAccount method with recovery code
- [ ] 10.5 Add token expiration tracking and proactive refresh

### 11. Vault API Methods
**References:** Design Document - APIClient interface

- [ ] 11.1 Implement createVault method with vault salt upload
- [ ] 11.2 Implement getVaultSalt method for key derivation

### 12. Item API Methods
**References:** Requirement 7 (Media Upload Flow), Requirement 8 (Media Download)

- [ ] 12.1 Implement initializeUpload method to get presigned S3 URL
- [ ] 12.2 Implement completeUpload method with encrypted metadata
- [ ] 12.3 Implement listItems method with pagination support
- [ ] 12.4 Implement getItem method for item details
- [ ] 12.5 Implement getDownloadURL method for presigned S3 URL
- [ ] 12.6 Implement deleteItem method

### 13. Collection and Share API Methods
**References:** Requirement 10 (Collections), Requirement 12 (Sharing)

- [ ] 13.1 Implement createCollection method with encrypted metadata
- [ ] 13.2 Implement listCollections method
- [ ] 13.3 Implement addItemToCollection method
- [ ] 13.4 Implement removeItemFromCollection method
- [ ] 13.5 Implement createShare method with expiration and password options
- [ ] 13.6 Implement revokeShare method

### 14. Tag Search and Recovery API Methods
**References:** Requirement 11 (Tag Management), Requirement 13 (Account Recovery)

- [ ] 14.1 Implement searchByTag method with encrypted tag parameter
- [ ] 14.2 Implement generateRecoveryCodes method

### 15. S3 Operations
**References:** Requirement 7 (Media Upload Flow), Requirement 8 (Media Download)

- [ ] 15.1 Implement uploadToS3 with presigned URL and progress tracking
- [ ] 15.2 Implement downloadFromS3 with presigned URL and progress tracking
- [ ] 15.3 Add multipart upload support for files >5MB
- [ ] 15.4 Implement retry logic with exponential backoff (max 3 retries)

## Phase 5: Service Layer

### 16. AuthService
**References:** Requirement 5 (Authentication), Requirement 3 (Two-Password Model)

- [ ] 16.1 Implement AuthService actor with APIClient and KeychainManager dependencies
- [ ] 16.2 Implement login method handling both account and vault passwords
- [ ] 16.3 Implement logout method clearing keychain and memory
- [ ] 16.4 Implement refreshSession method with automatic token refresh
- [ ] 16.5 Implement recoverAccount method
- [ ] 16.6 Implement changeAccountPassword method
- [ ] 16.7 Implement getCurrentUser method with session state
- [ ] 16.8 Add Combine publishers for authentication state changes

### 17. Password Validation
**References:** Requirement 3 (Two-Password Security Model)

- [ ] 17.1 Create PasswordValidator.swift with validation rules
- [ ] 17.2 Implement password strength validation (12+ chars, uppercase, lowercase, numbers, special)
- [ ] 17.3 Implement Have I Been Pwned API integration using k-anonymity
- [ ] 17.4 Implement SHA-1 hashing and prefix matching
- [ ] 17.5 Create PasswordValidationResult model with error cases

### 18. VaultService
**References:** Requirement 14 (Vault Recovery)

- [ ] 18.1 Implement VaultService actor with EncryptionEngine and APIClient
- [ ] 18.2 Implement createVault method with salt generation
- [ ] 18.3 Implement getVault method
- [ ] 18.4 Implement deriveVaultKeys method using EncryptionEngine
- [ ] 18.5 Implement generateVaultRecoveryKey using BIP39 mnemonic
- [ ] 18.6 Implement recoverVaultWithRecoveryKey method
- [ ] 18.7 Add in-memory key caching (never persist keys)

### 19. UploadService
**References:** Requirement 7 (Media Upload Flow)

- [ ] 19.1 Implement UploadService actor with dependencies
- [ ] 19.2 Implement queueUpload method with file validation
- [ ] 19.3 Implement startUpload method with encryption step
- [ ] 19.4 Implement upload orchestration (encrypt → init → S3 upload → complete)
- [ ] 19.5 Implement pauseUpload and resumeUpload methods
- [ ] 19.6 Implement cancelUpload method
- [ ] 19.7 Implement retryUpload with exponential backoff
- [ ] 19.8 Implement concurrent upload limit (default: 3)
- [ ] 19.9 Add progress tracking with Combine publishers
- [ ] 19.10 Implement persistent queue using StorageManager

### 20. DownloadService
**References:** Requirement 8 (Media Download and Viewing)

- [ ] 20.1 Implement DownloadService actor with dependencies
- [ ] 20.2 Implement downloadItem method (get URL → download → decrypt)
- [ ] 20.3 Implement downloadThumbnail method with caching
- [ ] 20.4 Implement getCachedThumbnail method
- [ ] 20.5 Implement thumbnail generation for images and videos
- [ ] 20.6 Implement progress tracking with Combine publishers
- [ ] 20.7 Implement cancelDownload method

### 21. ItemService
**References:** Requirement 9 (Item Management)

- [ ] 21.1 Implement ItemService actor with dependencies
- [ ] 21.2 Implement listItems method with filtering and sorting
- [ ] 21.3 Implement getItem method with metadata decryption
- [ ] 21.4 Implement deleteItem method
- [ ] 21.5 Implement updateItemMetadata method with re-encryption
- [ ] 21.6 Implement searchByTag method with tag encryption

### 22. CollectionService
**References:** Requirement 10 (Collections Management)

- [ ] 22.1 Implement CollectionService actor with dependencies
- [ ] 22.2 Implement createCollection method with metadata encryption
- [ ] 22.3 Implement listCollections method
- [ ] 22.4 Implement addItemToCollection method
- [ ] 22.5 Implement removeItemFromCollection method
- [ ] 22.6 Implement deleteCollection method
- [ ] 22.7 Implement updateCollection method with re-encryption

### 23. ShareService
**References:** Requirement 12 (Sharing Functionality)

- [ ] 23.1 Implement ShareService actor with dependencies
- [ ] 23.2 Implement createShare method with share key generation
- [ ] 23.3 Implement share URL generation with embedded key
- [ ] 23.4 Implement listShares method
- [ ] 23.5 Implement revokeShare method
- [ ] 23.6 Implement share analytics retrieval

### 24. RecoveryService
**References:** Requirement 13 (Account Recovery), Requirement 14 (Vault Recovery)

- [ ] 24.1 Implement RecoveryService actor with dependencies
- [ ] 24.2 Implement generateRecoveryCodes method (10 codes, format: XXXX-XXXX-XXXX-XXXX)
- [ ] 24.3 Implement validateRecoveryCode method
- [ ] 24.4 Implement recovery code display and export functionality

## Phase 6: ViewModels

### 25. AuthViewModel
**References:** Requirement 5 (Authentication)

- [ ] 25.1 Create AuthViewModel as ObservableObject
- [ ] 25.2 Implement @Published properties for auth state
- [ ] 25.3 Implement login method calling AuthService
- [ ] 25.4 Implement logout method
- [ ] 25.5 Implement password validation integration
- [ ] 25.6 Implement error handling and user-friendly messages
- [ ] 25.7 Add loading states for async operations

### 26. VaultViewModel
**References:** Requirement 14 (Vault Recovery)

- [ ] 26.1 Create VaultViewModel as ObservableObject
- [ ] 26.2 Implement @Published properties for vault state
- [ ] 26.3 Implement createVault method
- [ ] 26.4 Implement vault recovery key generation and display
- [ ] 26.5 Implement vault recovery flow

### 27. ItemViewModel
**References:** Requirement 9 (Item Management)

- [ ] 27.1 Create ItemViewModel as ObservableObject
- [ ] 27.2 Implement @Published properties for items list
- [ ] 27.3 Implement loadItems method with pagination
- [ ] 27.4 Implement filtering by type (MEDIA, NOTE, TASK, EVENT)
- [ ] 27.5 Implement sorting (date, name, size)
- [ ] 27.6 Implement search by tag
- [ ] 27.7 Implement deleteItem method
- [ ] 27.8 Implement updateItem method

### 28. CollectionViewModel
**References:** Requirement 10 (Collections Management)

- [ ] 28.1 Create CollectionViewModel as ObservableObject
- [ ] 28.2 Implement @Published properties for collections list
- [ ] 28.3 Implement createCollection method
- [ ] 28.4 Implement addItemToCollection method
- [ ] 28.5 Implement removeItemFromCollection method
- [ ] 28.6 Implement deleteCollection method

### 29. UploadViewModel
**References:** Requirement 7 (Media Upload Flow)

- [ ] 29.1 Create UploadViewModel as ObservableObject
- [ ] 29.2 Implement @Published properties for upload queue
- [ ] 29.3 Implement queueUpload method
- [ ] 29.4 Implement upload progress tracking
- [ ] 29.5 Implement pause/resume/cancel operations
- [ ] 29.6 Implement retry failed uploads
- [ ] 29.7 Subscribe to UploadService progress publishers

### 30. SettingsViewModel
**References:** Requirement 17 (Preferences and Settings)

- [ ] 30.1 Create SettingsViewModel as ObservableObject
- [ ] 30.2 Implement @Published properties for settings
- [ ] 30.3 Implement UserDefaults persistence for preferences
- [ ] 30.4 Implement concurrent upload limit configuration
- [ ] 30.5 Implement notification preferences
- [ ] 30.6 Implement cache size limit configuration
- [ ] 30.7 Implement storage usage calculation

## Phase 7: User Interface - Authentication

### 31. Authentication Views
**References:** Requirement 5 (Authentication), Requirement 3 (Two-Password Model)

- [ ] 31.1 Create LoginView.swift with email and password fields
- [ ] 31.2 Implement two-password input (account password and vault password)
- [ ] 31.3 Add password visibility toggles
- [ ] 31.4 Create SignUpView.swift with account creation flow
- [ ] 31.5 Implement password strength indicator
- [ ] 31.6 Implement breach detection feedback
- [ ] 31.7 Create RecoveryView.swift for account recovery
- [ ] 31.8 Add loading states and error messages
- [ ] 31.9 Implement keyboard shortcuts and accessibility

## Phase 8: User Interface - Main Application

### 32. Main Application Structure
**References:** Requirement 1 (Application Architecture)

- [ ] 32.1 Create CortexMacOSApp.swift as app entry point
- [ ] 32.2 Create AppDelegate.swift for app lifecycle
- [ ] 32.3 Create MainView.swift with NavigationSplitView
- [ ] 32.4 Create SidebarView.swift with navigation options
- [ ] 32.5 Create ContentView.swift as main content container
- [ ] 32.6 Implement navigation state management

### 33. Item Views
**References:** Requirement 9 (Item Management), Requirement 8 (Media Download)

- [ ] 33.1 Create ItemGridView.swift with LazyVGrid layout
- [ ] 33.2 Implement thumbnail loading with ThumbnailView component
- [ ] 33.3 Implement infinite scrolling/pagination
- [ ] 33.4 Create ItemDetailView.swift with metadata display
- [ ] 33.5 Create ItemViewerView.swift for media viewing
- [ ] 33.6 Implement Quick Look integration
- [ ] 33.7 Add item filtering and sorting controls
- [ ] 33.8 Add search bar with tag search

### 34. Collection Views
**References:** Requirement 10 (Collections Management)

- [ ] 34.1 Create CollectionListView.swift with collection cards
- [ ] 34.2 Create CollectionDetailView.swift showing collection items
- [ ] 34.3 Implement drag-and-drop to add items to collections
- [ ] 34.4 Add collection creation dialog
- [ ] 34.5 Add collection editing and deletion

### 35. Upload Views
**References:** Requirement 7 (Media Upload Flow), Requirement 6 (File System Integration)

- [ ] 35.1 Create UploadQueueView.swift showing queued uploads
- [ ] 35.2 Create UploadProgressView.swift with progress bars
- [ ] 35.3 Implement drag-and-drop file upload
- [ ] 35.4 Implement file picker integration
- [ ] 35.5 Add upload status indicators (pending, uploading, completed, failed)
- [ ] 35.6 Add pause/resume/cancel buttons
- [ ] 35.7 Add retry failed uploads button

### 36. Settings Views
**References:** Requirement 17 (Preferences and Settings)

- [ ] 36.1 Create PreferencesView.swift with tabs
- [ ] 36.2 Implement General preferences tab
- [ ] 36.3 Implement Upload preferences tab (concurrent uploads)
- [ ] 36.4 Implement Notifications preferences tab
- [ ] 36.5 Implement Storage preferences tab (cache management)
- [ ] 36.6 Implement Account preferences tab
- [ ] 36.7 Add storage usage visualization

### 37. Reusable Components
**References:** Requirement 21 (Accessibility), Requirement 20 (Performance)

- [ ] 37.1 Create LoadingView.swift with progress indicator
- [ ] 37.2 Create ErrorView.swift with retry button
- [ ] 37.3 Create ThumbnailView.swift with async image loading
- [ ] 37.4 Implement placeholder images for loading states
- [ ] 37.5 Add VoiceOver labels for all components
- [ ] 37.6 Implement keyboard navigation support

## Phase 9: Menu Bar Integration

### 38. Menu Bar Application
**References:** Requirement 15 (Menu Bar Integration)

- [ ] 38.1 Create MenuBarView.swift with NSStatusItem
- [ ] 38.2 Implement menu bar icon with upload progress indicator
- [ ] 38.3 Create dropdown menu with recent uploads
- [ ] 38.4 Add quick actions (Upload Files, Open App, Preferences, Quit)
- [ ] 38.5 Implement drag-and-drop onto menu bar icon
- [ ] 38.6 Add preference for menu bar-only mode (hide dock icon)
- [ ] 38.7 Implement menu bar icon animations for upload progress

## Phase 10: Notifications and System Integration

### 39. Notification System
**References:** Requirement 16 (Notifications)

- [ ] 39.1 Request notification permissions on first launch
- [ ] 39.2 Implement upload completion notifications
- [ ] 39.3 Implement upload failure notifications with error details
- [ ] 39.4 Implement batch upload completion summary
- [ ] 39.5 Add notification actions (View Item, Retry Upload)
- [ ] 39.6 Implement notification click handling
- [ ] 39.7 Add notification preferences integration

### 40. File System Integration
**References:** Requirement 6 (File System Integration)

- [ ] 40.1 Implement NSOpenPanel for file selection
- [ ] 40.2 Implement drag-and-drop using NSView.registerForDraggedTypes
- [ ] 40.3 Implement recursive folder upload
- [ ] 40.4 Extract and preserve file metadata (creation date, modification date)
- [ ] 40.5 Implement file type detection
- [ ] 40.6 Add file size validation

## Phase 11: Offline Support and Error Handling

### 41. Offline Support
**References:** Requirement 18 (Offline Support)

- [ ] 41.1 Implement network connectivity monitoring using NWPathMonitor
- [ ] 41.2 Add network status indicator in UI
- [ ] 41.3 Implement operation queueing when offline
- [ ] 41.4 Implement automatic retry when connectivity restored
- [ ] 41.5 Persist upload queue across app restarts
- [ ] 41.6 Disable network-dependent features when offline
- [ ] 41.7 Show cached content when offline

### 42. Error Handling and Logging
**References:** Requirement 19 (Error Handling and Logging)

- [ ] 42.1 Implement comprehensive error handling in all services
- [ ] 42.2 Create user-friendly error messages for all error types
- [ ] 42.3 Implement error logging with context (exclude sensitive data)
- [ ] 42.4 Add log export functionality
- [ ] 42.5 Implement crash reporting with user consent
- [ ] 42.6 Add retry logic for transient errors
- [ ] 42.7 Implement error recovery suggestions in UI

## Phase 12: Performance Optimization

### 43. Performance Enhancements
**References:** Requirement 20 (Performance and Optimization)

- [ ] 43.1 Implement lazy loading for item lists
- [ ] 43.2 Optimize thumbnail generation and caching
- [ ] 43.3 Implement background thread encryption/decryption
- [ ] 43.4 Add API response caching with 5-minute TTL
- [ ] 43.5 Implement efficient memory management for large files
- [ ] 43.6 Add hardware-accelerated video decoding
- [ ] 43.7 Optimize battery usage by throttling background operations
- [ ] 43.8 Measure and optimize app launch time (<2 seconds)

## Phase 13: Accessibility

### 44. Accessibility Implementation
**References:** Requirement 21 (Accessibility)

- [ ] 44.1 Add VoiceOver labels to all UI elements
- [ ] 44.2 Implement full keyboard navigation
- [ ] 44.3 Support Dynamic Type for font scaling
- [ ] 44.4 Ensure color contrast meets WCAG AA standards
- [ ] 44.5 Implement reduced motion support
- [ ] 44.6 Add alternative text for all images and icons
- [ ] 44.7 Support system appearance (light/dark mode)
- [ ] 44.8 Test with VoiceOver and keyboard-only navigation

## Phase 14: Testing

### 45. Unit Tests
**References:** Requirement 19 (Error Handling and Logging)

- [ ] 45.1 Write unit tests for EncryptionEngine (encryption round-trip)
- [ ] 45.2 Write unit tests for KeyDerivation (deterministic output)
- [ ] 45.3 Write unit tests for TagEncryption (deterministic output)
- [ ] 45.4 Write unit tests for PasswordValidator
- [ ] 45.5 Write unit tests for all service layer methods
- [ ] 45.6 Write unit tests for ViewModels
- [ ] 45.7 Achieve >80% code coverage

### 46. Integration Tests
**References:** All requirements

- [ ] 46.1 Write integration tests for authentication flow
- [ ] 46.2 Write integration tests for upload flow (mock S3)
- [ ] 46.3 Write integration tests for download flow (mock S3)
- [ ] 46.4 Write integration tests for collection management
- [ ] 46.5 Write integration tests for sharing functionality
- [ ] 46.6 Write integration tests for offline support

### 47. Property-Based Tests
**References:** Design Document - Correctness Properties

- [ ] 47.1 Write property test: Encryption round-trip preserves content
- [ ] 47.2 Write property test: Key derivation is deterministic
- [ ] 47.3 Write property test: Tag encryption is deterministic
- [ ] 47.4 Write property test: Password validation consistency
- [ ] 47.5 Write property test: Upload queue persistence
- [ ] 47.6 Write property test: Metadata encryption/decryption round-trip

### 48. UI Tests
**References:** Requirement 21 (Accessibility)

- [ ] 48.1 Write UI tests for login flow
- [ ] 48.2 Write UI tests for file upload via drag-and-drop
- [ ] 48.3 Write UI tests for item browsing and filtering
- [ ] 48.4 Write UI tests for collection management
- [ ] 48.5 Write UI tests for settings changes
- [ ] 48.6 Write UI tests for keyboard navigation
- [ ] 48.7 Write UI tests for VoiceOver compatibility

## Phase 15: Documentation and Polish

### 49. Documentation
**References:** All requirements

- [ ] 49.1 Write README.md with setup instructions
- [ ] 49.2 Document API client usage
- [ ] 49.3 Document encryption implementation
- [ ] 49.4 Create user guide for two-password model
- [ ] 49.5 Document recovery procedures
- [ ] 49.6 Add inline code documentation
- [ ] 49.7 Create troubleshooting guide

### 50. Final Polish
**References:** Requirement 20 (Performance), Requirement 21 (Accessibility)

- [ ] 50.1 Optimize app icon and assets
- [ ] 50.2 Implement app onboarding flow
- [ ] 50.3 Add tooltips and help text
- [ ] 50.4 Perform final accessibility audit
- [ ] 50.5 Perform final performance audit
- [ ] 50.6 Test on multiple macOS versions (13.0+)
- [ ] 50.7 Prepare for App Store submission (if applicable)
