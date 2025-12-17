---
inclusion: always
---

# Cortex: Zero-Knowledge Media Backup System

Cortex is a privacy-first photo and video backup solution where all encryption happens client-side. The backend never has access to unencrypted user data, metadata, or encryption keys.

## Critical Architecture Constraints

**Zero-Knowledge Enforcement:**
- Backend MUST NEVER receive or process unencrypted user data
- All encryption/decryption operations happen exclusively on client devices
- Metadata (filenames, dates, locations), tags, and collections are encrypted before transmission
- Server only stores encrypted blobs and cannot decrypt them

**Data Flow Pattern:**
- Client encrypts data → Client uploads directly to S3 via presigned URL → Server stores encrypted metadata in DynamoDB
- Client requests presigned URL → Client downloads from S3 → Client decrypts locally
- Lambda functions only handle presigned URL generation and encrypted metadata operations

**Two-Password Security Model:**
- **Account Password**: Used for AWS Cognito authentication, can be changed without re-encrypting vault data
- **Vault Password**: Used exclusively for deriving vault encryption keys, never transmitted to server
- Separation allows flexible credential management without expensive re-encryption
- Vault password + server-stored vault salt → Argon2id → Vault master key (256-bit)
- HKDF derives multiple keys from vault master key: data encryption key, metadata encryption key, share key derivation key

**Key Management:**
- Vault master key derived from vault password using Argon2id (64MB memory, 3 iterations, 4 parallelism)
- Vault salt stored on server (non-secret, enables multi-device key derivation)
- Keys never transmitted to or stored on backend
- Multi-device support via vault password + vault salt (derive same keys on any device)
- Vault recovery key (BIP39 mnemonic) enables vault password reset without re-encryption
- Account recovery codes (10 per user) enable account password reset
- Automatic key rotation every 90 days with background re-encryption

## Feature Scope

**Core Capabilities:**
- Photo and video backup with client-side ChaCha20-Poly1305 encryption
- Encrypted metadata storage (filename, size, upload date, MIME type)
- Tag-based organization with deterministic encryption for searchability
- Collection management for grouping media (collection names encrypted)
- Multi-device access using vault password + vault salt for key derivation
- Dual recovery system: account recovery codes (10 per user) and vault recovery key (BIP39 mnemonic)
- File sharing with unique share keys, optional password protection, expiration, and revocation
- Automatic key rotation every 90 days with background re-encryption
- Password strength validation and breach detection (Have I Been Pwned API)
- Optional local content analysis for tag generation (TensorFlow Lite, Core ML, ONNX)

**Performance Optimizations:**
- Direct client-to-S3 transfers using presigned URLs (bypass Lambda for data transfer)
- S3 multipart upload for files >5MB (minimum part size, up to 10,000 parts)
- S3 Transfer Acceleration for global users
- Lazy-load metadata with pagination
- Concurrent uploads with configurable limits based on network conditions

## User Experience Principles

- Seamless backup: Users should not notice encryption overhead
- Fast retrieval: Presigned URLs enable direct S3 downloads
- Cross-device: Encrypted key bundles allow access from any device
- Privacy transparency: Users understand their data is truly private

## Security Boundaries

- Cognito provides authentication and user identity
- IAM policies scoped to Cognito identity pool enforce user-level isolation
- S3 bucket policies require encryption at rest (AES-256)
- API Gateway validates JWT tokens before Lambda invocation
- CloudTrail logs all API access for audit purposes

## What Backend Can/Cannot Do

**Backend CAN:**
- Generate presigned S3 URLs for authenticated users
- Store and retrieve encrypted metadata, tags, and collections
- Manage user accounts and authentication (account password only)
- Store vault salts for key derivation (non-secret information)
- Store account recovery code hashes (SHA-256)
- Track storage quotas and usage
- Provide encrypted search/filter on encrypted metadata fields
- Manage file sharing metadata (expiration, revocation status, access counts)
- Validate share access without accessing share keys

**Backend CANNOT:**
- Decrypt user photos, videos, or metadata
- Access vault encryption keys, vault password, or vault recovery key
- View file contents, filenames, or tags in plaintext
- Perform server-side image processing or analysis
- Access share keys (embedded in URLs, never stored on server)
- Determine content type, subject matter, or organizational structure
- Re-derive vault master key (requires vault password which server never receives)

## File Sharing Model

**Share Key Architecture:**
- Each shared file gets unique 256-bit share key derived from share key derivation key + file ID
- Share key embedded in URL fragment (never sent to server)
- Server stores only share metadata: expiration, password protection flag, revocation status
- Anonymous access supported (no authentication required for share recipients)

**Share Features:**
- Time-limited expiration with server-side validation
- Optional password protection (double-encrypt share key with password-derived key)
- Revocation by owner (server blocks access even with valid share key)
- Access tracking (count and last accessed timestamp)
- Share URLs format: `https://cortex.example.com/share/{shareId}#{base64(shareKey)}`

## Password Management

**Two Separate Passwords:**
- **Account Password**: Authenticates with AWS Cognito, managed by Cognito password policies
- **Vault Password**: Derives vault encryption keys, never transmitted to server

**Password Requirements (both types):**
- Minimum 12 characters
- Must include: uppercase, lowercase, numbers, special characters
- Breach detection via Have I Been Pwned API (k-anonymity model)
- No maximum length restriction

**Password Changes:**
- Account password change: Updates Cognito credentials only, no vault re-encryption needed
- Vault password change: Derives new vault master key, triggers background re-encryption of all vault data

## Recovery Mechanisms

**Account Recovery:**
- 10 recovery codes generated at signup (16 characters each, format: XXXX-XXXX-XXXX-XXXX)
- Codes hashed with SHA-256 before server storage
- One-time use (invalidated after successful recovery)
- Enables account password reset

**Vault Recovery:**
- Vault recovery key (BIP39 mnemonic, 12-24 words) derived from vault master key
- Displayed once at vault creation with secure offline storage guidance
- Never transmitted to or stored by server
- Enables vault password reset without re-encrypting data
- Re-derives vault master key directly from recovery key

## Key Rotation

**Automatic Rotation:**
- Triggered every 90 days since last rotation
- Client-side monitoring of key age
- Manual rotation available via user settings

**Rotation Process:**
- Generate new derived keys from vault master key using updated HKDF context
- Background re-encryption of all vault files in batches
- Dual-key access during transition (old keys for reading, new keys for writing)
- Update metadata with new key version
- Complete when all data re-encrypted with new keys
