# File Sharing System Design

**Task:** 17 (subtasks 17.1-17.5)
**Date:** 2026-02-06
**Status:** Approved

## Overview

Password-protected file sharing with envelope encryption. The server never sees key material - all cryptographic operations happen in the frontend. Recipients access shared files using only the share password, without needing the vault password.

## Architecture

### Data Flow

**Creator (share creation):**
1. Enter share password → derive share encryption key (Argon2id) and HMAC key (HKDF)
2. Unwrap file's DEK using vault KEK → re-wrap DEK with share encryption key
3. POST metadata-only request to backend (no key material)
4. Construct share URL with wrapped DEK, salt, and HMAC in URL fragment (never sent to server)

**Recipient (share access):**
1. Open share URL → extract blob from fragment
2. Fetch share metadata from server (shareId, expiresAt, downloadUrl)
3. Enter share password → verify HMAC over metadata → derive share key → unwrap DEK
4. Download encrypted file via presigned URL → decrypt with DEK

### Components

| Component | Path | Purpose |
|-----------|------|---------|
| Share encryption | `packages/encryption/src/lib/share-encryption.ts` | Key derivation, DEK wrapping, HMAC |
| Share service | `lambda/src/api/services/share_service.py` | Business logic, rate limiting |
| Share routes | `lambda/src/api/routes/shares.py` | HTTP handlers (replace stubs) |
| Pydantic models | `lambda/src/shared/models.py` | Request/response validation |
| Property test | `packages/encryption/tests/property/test_share_encryption.test.ts` | Share round-trip property |
| Frontend | `packages/web/src/` | Share creation and access UI |

## Encryption Design

### Key Derivation Chain

```
share_password + share_salt (16 bytes random)
    → Argon2id(64MB, 3 iterations, 4 parallelism)
    → share_master_key (32 bytes)

share_master_key
    → HKDF-SHA256(context: "cortex-share-key-v1")
    → share_encryption_key (32 bytes)  [wraps DEK]

share_master_key
    → HKDF-SHA256(context: "cortex-share-hmac-v1")
    → hmac_key (32 bytes)  [signs metadata]
```

### DEK Re-wrapping

- Unwrap file's DEK using vault's KEK (existing `unwrapDek()`)
- Re-wrap DEK using share encryption key (existing `wrapDek()` with share key)
- Zero original DEK immediately after re-wrapping

### HMAC Metadata Binding

- `HMAC-SHA256(hmac_key, shareId || expiresAt)`
- Binds URL fragment to server-side metadata
- Prevents share ID swapping attacks
- Verified client-side with constant-time comparison

### Share Password Requirements

- Minimum 16 characters
- Minimum 80 bits entropy

## URL Format

### Share URL

```
https://app.cortex.dev/s/{shareId}#{base64url_blob}
```

Blob is base64url-encoded binary (opaque, no parameter names visible):

```
[version(1)][salt(16)][wrappedDek(65)][hmac(32)] = 114 bytes → ~152 chars base64url
```

### Alternative Access

For truncated URLs: navigate to `/s`, enter share ID and password manually.

## Data Model

### DynamoDB Shares Table

**Share metadata row:**

```
PK: SHARE#{shareId}
SK: METADATA
shareId: str
itemId: str
vaultId: str
userId: str
createdAt: int          (Unix epoch)
expiresAt: int          (Unix epoch, optional)
isRevoked: bool         (default false)
accessCount: int        (default 0)
lastAccessedAt: int     (Unix epoch, optional)
ttl: int                (DynamoDB TTL attribute)
```

**Rate limit row (same table):**

```
PK: SHARE#{shareId}
SK: RATE#{ipAddress}
attemptCount: int
windowStart: int        (Unix epoch, hourly window)
ttl: int                (windowStart + 7200)
```

### TTL Strategy

| Scenario | TTL Value |
|----------|-----------|
| Expiring share | `expiresAt + 86400` (24h grace) |
| No expiration | No TTL attribute |
| Revoked share | `revokedAt + 604800` (7 days for audit) |
| Rate limit row | `windowStart + 7200` (2h after window) |

## Rate Limiting

Three layers:

1. **API Gateway throttling** - Infrastructure-level abuse prevention on `GET /v1/shares/{shareId}`
2. **Server-side per-share tracking** - DynamoDB `RATE#{ip}` rows, max 5 attempts per IP per share per hour, HTTP 429 with Retry-After
3. **Client-side exponential backoff** - After 3 failed decryption attempts in browser

## Service Layer

### ShareService

```python
class ShareService:
    def create_share(user_id, request) -> CreateShareResponse
        # Verify user owns the item (query items table)
        # Generate UUID shareId
        # Store metadata (no key material)
        # Set TTL if expiresAt provided
        # Return shareId, createdAt, expiresAt

    def get_share(share_id, client_ip) -> GetShareResponse
        # Check rate limit for IP + shareId
        # Fetch share metadata
        # Check revoked → ShareRevokedError
        # Check expired → ShareExpiredError
        # Generate presigned S3 download URL
        # Increment access count, update lastAccessedAt
        # Return metadata + download URL

    def revoke_share(user_id, share_id) -> RevokeShareResponse
        # Verify user owns the share
        # Set isRevoked = True, set TTL (7 days)
        # Return confirmation

    def check_rate_limit(share_id, client_ip) -> None
        # Query RATE#{ip} row for current hour window
        # If count >= 5: raise HTTP 429 with Retry-After
        # Otherwise: increment count
```

## Frontend

### Share Encryption Module

`packages/encryption/src/lib/share-encryption.ts`:

```typescript
deriveShareKeys(password, salt) → {encryptionKey, hmacKey}
computeShareHmac(hmacKey, shareId, expiresAt?) → Uint8Array
verifyShareHmac(hmacKey, shareId, expiresAt, expectedHmac) → boolean
encodeShareBlob(version, salt, wrappedDek, hmac) → string  // base64url
decodeShareBlob(blob) → {version, salt, wrappedDek, hmac}
validateSharePasswordStrength(password) → {valid, score, feedback}
```

### Share Creation UI

1. User selects file → clicks "Share"
2. Share dialog: password input (strength meter), expiration picker, URL shortener warning
3. On submit: derive keys, re-wrap DEK, POST metadata, construct URL
4. Display URL with copy button + fallback share ID

### Share Access UI

1. Open URL → extract shareId from path, blob from fragment
2. Fetch metadata from server
3. Prompt for password → verify HMAC → derive key → unwrap DEK
4. Download and decrypt file → trigger browser download
5. Zero DEK from memory

## Property Test

**Property 20: Share keys enable file access without vault password**

Validates: encrypt file with vault KEK → create share (re-wrap DEK) → access share with only share password → decrypt matches original. 50 property test runs.
