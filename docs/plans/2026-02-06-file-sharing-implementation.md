# File Sharing System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement password-protected file sharing with envelope encryption, where the server never sees key material and recipients access shared files using only the share password.

**Architecture:** Frontend encryption library handles key derivation (Argon2id + HKDF), DEK re-wrapping, HMAC metadata binding, and blob encoding. Backend stores only share metadata (never keys) in DynamoDB with TTL for cleanup. Three-layer rate limiting: API Gateway throttling, server-side per-share/IP tracking, client-side exponential backoff.

**Tech Stack:** TypeScript (@noble/ciphers, @noble/hashes, argon2id, fast-check), Python 3.11 (Lambda Powertools, Pydantic, boto3), React 19, DynamoDB, S3

**Design doc:** `docs/plans/2026-02-06-file-sharing-design.md`

---

## Task 0: Fix CDK ↔ Lambda Environment Variable Mismatches

CDK sets `DATA_TABLE`, `SHARES_TABLE`, `BUCKET_NAME` but Lambda service provider reads `ITEMS_TABLE_NAME` / `SHARES_TABLE_NAME` / `FILES_BUCKET_NAME` etc. The `dataTable` in CDK is a single table used for vaults, items, collections, and recovery (single-table design), but the Python service provider reads 4 separate env vars for it.

**Files:**
- Modify: `cdk/lib/stacks/service.ts` (lines 222-228) - add all env vars
- Modify: `lambda/src/environment/service_provider.py` - no change needed (it already reads the correct names)

### Step 1: Update CDK Lambda environment variables

In `cdk/lib/stacks/service.ts`, replace the environment block in `createApiHandler()` (lines 222-232):

```typescript
            environment: {
                STAGE: this.props.stage.stageType,
                // Single data table serves as vaults, items, collections, and recovery table
                VAULTS_TABLE_NAME: this.dataTable.tableName,
                ITEMS_TABLE_NAME: this.dataTable.tableName,
                COLLECTIONS_TABLE_NAME: this.dataTable.tableName,
                RECOVERY_TABLE_NAME: this.dataTable.tableName,
                // Separate shares table for anonymous access security isolation
                SHARES_TABLE_NAME: this.sharesTable.tableName,
                FILES_BUCKET_NAME: this.bucket.bucketName,
                COGNITO_USER_POOL_ID: this.props.userPool.userPoolId,
                COGNITO_USER_POOL_CLIENT_ID: this.props.userPoolClient.userPoolClientId,
                POWERTOOLS_SERVICE_NAME: "cortex-api",
                POWERTOOLS_METRICS_NAMESPACE: "Cortex",
                LOG_LEVEL: "INFO",
            },
```

### Step 2: Update service_provider to match Cognito env var name

In `lambda/src/environment/service_provider.py`, the `auth_service` property (line 104) already reads `COGNITO_USER_POOL_ID` which now matches. Verify no other mismatches exist.

### Step 3: Run all existing tests

Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest -v`
Expected: All tests PASS (tests use fixture env vars, not CDK env vars)

Run: `cd /Users/lcmessen/cortex/cdk && npx cdk synth --quiet`
Expected: Successful synthesis

### Step 4: Commit

```bash
git add cdk/lib/stacks/service.ts
git commit -m "fix: align CDK Lambda env vars with service provider expectations"
```

---

## Task 1: Share Encryption Module

**Files:**
- Create: `packages/encryption/src/lib/share-encryption.ts`
- Modify: `packages/encryption/src/index.ts`

### Step 1: Write the failing tests

Create `packages/encryption/tests/unit/test_share_encryption.test.ts`:

```typescript
import {
  deriveShareKeys,
  computeShareHmac,
  verifyShareHmac,
  encodeShareBlob,
  decodeShareBlob,
} from '../../src/lib/share-encryption';

describe('Share Encryption', () => {
  const password = 'test-share-password-16chars!';
  const salt = new Uint8Array(16).fill(42);

  describe('deriveShareKeys', () => {
    test('derives 32-byte encryption key and 32-byte HMAC key', async () => {
      const { encryptionKey, hmacKey } = await deriveShareKeys(password, salt);
      expect(encryptionKey.length).toBe(32);
      expect(hmacKey.length).toBe(32);
    });

    test('same password + salt produces same keys', async () => {
      const keys1 = await deriveShareKeys(password, salt);
      const keys2 = await deriveShareKeys(password, salt);
      expect(keys1.encryptionKey).toEqual(keys2.encryptionKey);
      expect(keys1.hmacKey).toEqual(keys2.hmacKey);
    });

    test('different passwords produce different keys', async () => {
      const keys1 = await deriveShareKeys(password, salt);
      const keys2 = await deriveShareKeys('different-password-16chars!', salt);
      expect(keys1.encryptionKey).not.toEqual(keys2.encryptionKey);
    });

    test('different salts produce different keys', async () => {
      const salt2 = new Uint8Array(16).fill(99);
      const keys1 = await deriveShareKeys(password, salt);
      const keys2 = await deriveShareKeys(password, salt2);
      expect(keys1.encryptionKey).not.toEqual(keys2.encryptionKey);
    });

    test('encryption key differs from HMAC key', async () => {
      const { encryptionKey, hmacKey } = await deriveShareKeys(password, salt);
      expect(encryptionKey).not.toEqual(hmacKey);
    });
  });

  describe('computeShareHmac / verifyShareHmac', () => {
    test('compute returns 32-byte HMAC', async () => {
      const { hmacKey } = await deriveShareKeys(password, salt);
      const mac = computeShareHmac(hmacKey, 'share-123', 1700000000);
      expect(mac.length).toBe(32);
    });

    test('verify returns true for matching HMAC', async () => {
      const { hmacKey } = await deriveShareKeys(password, salt);
      const mac = computeShareHmac(hmacKey, 'share-123', 1700000000);
      expect(verifyShareHmac(hmacKey, 'share-123', 1700000000, mac)).toBe(true);
    });

    test('verify returns false for wrong shareId', async () => {
      const { hmacKey } = await deriveShareKeys(password, salt);
      const mac = computeShareHmac(hmacKey, 'share-123', 1700000000);
      expect(verifyShareHmac(hmacKey, 'share-456', 1700000000, mac)).toBe(false);
    });

    test('verify returns false for wrong expiresAt', async () => {
      const { hmacKey } = await deriveShareKeys(password, salt);
      const mac = computeShareHmac(hmacKey, 'share-123', 1700000000);
      expect(verifyShareHmac(hmacKey, 'share-123', 1700099999, mac)).toBe(false);
    });

    test('handles undefined expiresAt', async () => {
      const { hmacKey } = await deriveShareKeys(password, salt);
      const mac = computeShareHmac(hmacKey, 'share-123', undefined);
      expect(verifyShareHmac(hmacKey, 'share-123', undefined, mac)).toBe(true);
    });
  });

  describe('encodeShareBlob / decodeShareBlob', () => {
    test('round-trip preserves data', () => {
      const version = 1;
      const wrappedDek = new Uint8Array(65).fill(7);
      const hmacVal = new Uint8Array(32).fill(8);

      const encoded = encodeShareBlob(version, salt, wrappedDek, hmacVal);
      const decoded = decodeShareBlob(encoded);

      expect(decoded.version).toBe(version);
      expect(decoded.salt).toEqual(salt);
      expect(decoded.wrappedDek).toEqual(wrappedDek);
      expect(decoded.hmac).toEqual(hmacVal);
    });

    test('encoded blob is base64url string', () => {
      const encoded = encodeShareBlob(1, salt, new Uint8Array(65), new Uint8Array(32));
      // base64url: no +, /, or = padding
      expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
    });

    test('blob is 114 bytes raw (152 chars base64url)', () => {
      const encoded = encodeShareBlob(1, salt, new Uint8Array(65), new Uint8Array(32));
      // 114 bytes = ceil(114 * 4/3) = 152 chars base64url (no padding)
      expect(encoded.length).toBe(152);
    });

    test('throws on invalid blob', () => {
      expect(() => decodeShareBlob('short')).toThrow();
    });
  });
});
```

### Step 2: Run tests to verify they fail

Run: `cd /Users/lcmessen/cortex && npx --workspace=packages/encryption jest tests/unit/test_share_encryption.test.ts`
Expected: FAIL with "Cannot find module '../../src/lib/share-encryption'"

### Step 3: Write share-encryption.ts implementation

Create `packages/encryption/src/lib/share-encryption.ts`:

```typescript
/**
 * Share Encryption Module
 *
 * Handles key derivation, HMAC computation, and blob encoding for
 * password-protected file sharing. The server never sees key material.
 *
 * Key derivation chain:
 *   share_password + salt → Argon2id → share_master_key
 *   share_master_key → HKDF("cortex-share-key-v1") → encryption_key
 *   share_master_key → HKDF("cortex-share-hmac-v1") → hmac_key
 *
 * Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.10, 17.11, 31.1-31.6
 */

import { hkdf } from '@noble/hashes/hkdf';
import { sha256 } from '@noble/hashes/sha2';
import { hmac } from '@noble/hashes/hmac';
import { initArgon2idLoader } from 'argon2id';

const SHARE_BLOB_VERSION = 0x01;
const SALT_SIZE = 16;
const WRAPPED_DEK_SIZE = 65;
const HMAC_SIZE = 32;
const BLOB_SIZE = 1 + SALT_SIZE + WRAPPED_DEK_SIZE + HMAC_SIZE; // 114

const ARGON2_PARAMS = {
  memorySize: 65536, // 64MB in KB
  passes: 3,
  parallelism: 4,
  tagLength: 32,
};

const HKDF_SALT_ENCRYPTION = new TextEncoder().encode('cortex-salt-share-enc-v1');
const HKDF_SALT_HMAC = new TextEncoder().encode('cortex-salt-share-hmac-v1');
const HKDF_CONTEXT_ENCRYPTION = new TextEncoder().encode('cortex-share-key-v1');
const HKDF_CONTEXT_HMAC = new TextEncoder().encode('cortex-share-hmac-v1');

let argon2idInstance: ((params: {
  password: Uint8Array;
  salt: Uint8Array;
  parallelism: number;
  passes: number;
  memorySize: number;
  tagLength: number;
}) => Uint8Array) | null = null;

async function getArgon2id() {
  if (!argon2idInstance) {
    const loader = await initArgon2idLoader();
    argon2idInstance = await loader();
  }
  return argon2idInstance;
}

export interface ShareKeys {
  encryptionKey: Uint8Array;
  hmacKey: Uint8Array;
}

/**
 * Derive share encryption key and HMAC key from a share password and salt.
 *
 * @param password - The share password (16+ chars, 80+ bits entropy)
 * @param salt - Random 16-byte salt
 * @returns ShareKeys with 32-byte encryptionKey and 32-byte hmacKey
 */
export async function deriveShareKeys(password: string, salt: Uint8Array): Promise<ShareKeys> {
  if (salt.length !== SALT_SIZE) {
    throw new Error(`Invalid salt size: expected ${SALT_SIZE} bytes, got ${salt.length}`);
  }

  const argon2id = await getArgon2id();
  const passwordBytes = new TextEncoder().encode(password);

  const masterKey = argon2id({
    password: passwordBytes,
    salt,
    ...ARGON2_PARAMS,
  });

  const encryptionKey = hkdf(sha256, masterKey, HKDF_SALT_ENCRYPTION, HKDF_CONTEXT_ENCRYPTION, 32);
  const hmacKey = hkdf(sha256, masterKey, HKDF_SALT_HMAC, HKDF_CONTEXT_HMAC, 32);

  masterKey.fill(0);

  return { encryptionKey, hmacKey };
}

/**
 * Compute HMAC-SHA256 over share metadata.
 * Binds the URL fragment to server-side metadata to prevent share ID swapping.
 *
 * @param hmacKey - 32-byte HMAC key from deriveShareKeys
 * @param shareId - The share identifier
 * @param expiresAt - Optional expiration timestamp (Unix epoch)
 * @returns 32-byte HMAC
 */
export function computeShareHmac(
  hmacKey: Uint8Array,
  shareId: string,
  expiresAt?: number
): Uint8Array {
  const expiresStr = expiresAt !== undefined ? String(expiresAt) : '';
  const message = new TextEncoder().encode(shareId + '|' + expiresStr);
  return hmac(sha256, hmacKey, message);
}

/**
 * Verify HMAC over share metadata using constant-time comparison.
 *
 * @param hmacKey - 32-byte HMAC key
 * @param shareId - The share identifier
 * @param expiresAt - Expiration timestamp from server
 * @param expectedHmac - HMAC from URL fragment
 * @returns true if HMAC matches
 */
export function verifyShareHmac(
  hmacKey: Uint8Array,
  shareId: string,
  expiresAt: number | undefined,
  expectedHmac: Uint8Array
): boolean {
  const computed = computeShareHmac(hmacKey, shareId, expiresAt);

  if (computed.length !== expectedHmac.length) return false;

  let diff = 0;
  for (let i = 0; i < computed.length; i++) {
    diff |= computed[i] ^ expectedHmac[i];
  }
  return diff === 0;
}

/**
 * Encode share data into a base64url blob for the URL fragment.
 * Format: [version(1)][salt(16)][wrappedDek(65)][hmac(32)] = 114 bytes
 *
 * @returns base64url-encoded string (~152 chars)
 */
export function encodeShareBlob(
  version: number,
  salt: Uint8Array,
  wrappedDek: Uint8Array,
  hmacVal: Uint8Array
): string {
  if (salt.length !== SALT_SIZE) throw new Error(`Invalid salt size: ${salt.length}`);
  if (wrappedDek.length !== WRAPPED_DEK_SIZE) throw new Error(`Invalid wrappedDek size: ${wrappedDek.length}`);
  if (hmacVal.length !== HMAC_SIZE) throw new Error(`Invalid HMAC size: ${hmacVal.length}`);

  const blob = new Uint8Array(BLOB_SIZE);
  let offset = 0;

  blob[offset] = version;
  offset += 1;

  blob.set(salt, offset);
  offset += SALT_SIZE;

  blob.set(wrappedDek, offset);
  offset += WRAPPED_DEK_SIZE;

  blob.set(hmacVal, offset);

  return uint8ArrayToBase64url(blob);
}

/**
 * Decode a base64url blob from the URL fragment.
 *
 * @param encoded - base64url-encoded string
 * @returns Decoded share data
 */
export function decodeShareBlob(encoded: string): {
  version: number;
  salt: Uint8Array;
  wrappedDek: Uint8Array;
  hmac: Uint8Array;
} {
  const blob = base64urlToUint8Array(encoded);

  if (blob.length !== BLOB_SIZE) {
    throw new Error(`Invalid share blob size: expected ${BLOB_SIZE} bytes, got ${blob.length}`);
  }

  let offset = 0;

  const version = blob[offset];
  offset += 1;

  const salt = blob.slice(offset, offset + SALT_SIZE);
  offset += SALT_SIZE;

  const wrappedDek = blob.slice(offset, offset + WRAPPED_DEK_SIZE);
  offset += WRAPPED_DEK_SIZE;

  const hmacVal = blob.slice(offset, offset + HMAC_SIZE);

  return { version, salt, wrappedDek, hmac: hmacVal };
}

// --- base64url helpers ---

function uint8ArrayToBase64url(bytes: Uint8Array): string {
  const binary = String.fromCharCode(...bytes);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlToUint8Array(str: string): Uint8Array {
  const base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  return new Uint8Array([...binary].map(c => c.charCodeAt(0)));
}
```

### Step 4: Add exports to index.ts

Modify `packages/encryption/src/index.ts` - add at the end:

```typescript
// Export share encryption functions
export {
  deriveShareKeys,
  computeShareHmac,
  verifyShareHmac,
  encodeShareBlob,
  decodeShareBlob,
  type ShareKeys,
} from './lib/share-encryption';
```

### Step 5: Run tests to verify they pass

Run: `cd /Users/lcmessen/cortex && npx --workspace=packages/encryption jest tests/unit/test_share_encryption.test.ts`
Expected: All tests PASS

### Step 6: Commit

```bash
git add packages/encryption/src/lib/share-encryption.ts packages/encryption/src/index.ts packages/encryption/tests/unit/test_share_encryption.test.ts
git commit -m "feat: add share encryption module with key derivation and blob encoding"
```

---

## Task 2: Share Service Layer (Python)

**Files:**
- Create: `lambda/src/api/services/share_service.py`
- Modify: `lambda/src/shared/models.py` (add request/response models)

### Step 1: Add Pydantic models for share requests/responses

Modify `lambda/src/shared/models.py`. Add before the `ErrorResponse` class (around line 636):

```python
# ============================================================================
# Share Request/Response Models
# ============================================================================


class CreateShareRequest(BaseModel):
    """Request model for creating a share."""

    item_id: str = Field(..., description="Item to share")
    expires_at: Optional[int] = Field(default=None, description="Expiration timestamp (Unix epoch)")


class CreateShareResponse(BaseModel):
    """Response model for share creation."""

    share_id: str = Field(..., description="Share identifier")
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")
    expires_at: Optional[int] = Field(default=None, description="Expiration timestamp")


class GetShareResponse(BaseModel):
    """Response model for share access."""

    share_id: str = Field(..., description="Share identifier")
    item_id: str = Field(..., description="Item identifier")
    download_url: str = Field(..., description="Presigned S3 download URL")
    url_expires_at: int = Field(..., description="URL expiration (Unix epoch)")
    expires_at: Optional[int] = Field(default=None, description="Share expiration (Unix epoch)")


class RevokeShareResponse(BaseModel):
    """Response model for share revocation."""

    message: str = Field(..., description="Confirmation message")
    revoked_at: int = Field(..., description="Revocation timestamp (Unix epoch)")
```

Also update `DynamoDBShareItem` to add the `ttl` field. Around line 607, change:

```python
class DynamoDBShareItem(BaseModel):
    """DynamoDB item model for shares."""

    PK: str = Field(..., description="Partition key: SHARE#{shareId}")
    SK: str = Field(..., description="Sort key: METADATA")
    share_id: str = Field(..., description="Share identifier")
    item_id: str = Field(..., description="Item identifier")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="Owner user identifier")
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")
    expires_at: Optional[int] = Field(default=None, description="Expiration timestamp (Unix epoch)")
    is_revoked: bool = Field(default=False, description="Revocation flag")
    access_count: int = Field(default=0, description="Access counter")
    last_accessed_at: Optional[int] = Field(default=None, description="Last access timestamp")
    ttl: Optional[int] = Field(default=None, description="DynamoDB TTL for auto-cleanup")
```

Note: the existing model uses `file_id` but the Smithy model and design doc use `item_id`. Change the field name from `file_id` to `item_id` to match. Also change `is_password_protected` to be removed since the server doesn't need to know this (password handling is entirely client-side).

### Step 2: Write the failing tests for ShareService

Create `lambda/tests/unit/services/test_share_service.py`:

```python
"""
Unit tests for share service layer.
"""

import json
import time
import uuid
from unittest.mock import patch

import pytest
from botocore.stub import ANY

from src.api.services.share_service import ShareService
from src.shared.models import CreateShareRequest


class TestCreateShare:
    """Test suite for ShareService.create_share."""

    def test_create_share_success(self, share_service, dynamodb_stubber):
        """Create share stores metadata and returns share ID."""
        user_id = "test-user-123"
        item_id = "test-item-456"
        vault_id = "test-vault-789"

        # Stub get_item for item lookup
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/{vault_id}/{item_id}"},
                    "upload_status": {"S": "COMPLETE"},
                    "encrypted_metadata": {"B": b"encrypted"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        # Stub put_item for share creation
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {"TableName": "test-shares-table", "Item": ANY, "ConditionExpression": ANY},
        )

        request = CreateShareRequest(item_id=item_id)
        response = share_service.create_share(user_id, request)

        assert response.share_id is not None
        assert len(response.share_id) > 0
        assert response.created_at > 0

    def test_create_share_with_expiration(self, share_service, dynamodb_stubber):
        """Create share with expiration sets TTL."""
        user_id = "test-user-123"
        item_id = "test-item-456"
        vault_id = "test-vault-789"
        expires_at = int(time.time()) + 86400  # 1 day from now

        # Stub get_item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/{vault_id}/{item_id}"},
                    "upload_status": {"S": "COMPLETE"},
                    "encrypted_metadata": {"B": b"encrypted"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        # Stub put_item
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {"TableName": "test-shares-table", "Item": ANY, "ConditionExpression": ANY},
        )

        request = CreateShareRequest(item_id=item_id, expires_at=expires_at)
        response = share_service.create_share(user_id, request)

        assert response.expires_at == expires_at

    def test_create_share_item_not_found(self, share_service, dynamodb_stubber):
        """Create share fails if item doesn't exist."""
        user_id = "test-user-123"

        # Stub get_item returns empty
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-items-table", "Key": ANY},
        )

        request = CreateShareRequest(item_id="nonexistent")
        with pytest.raises(Exception, match="not found"):
            share_service.create_share(user_id, request)

    def test_create_share_wrong_owner(self, share_service, dynamodb_stubber):
        """Create share fails if user doesn't own the item."""
        user_id = "test-user-123"
        item_id = "test-item-456"

        # Stub get_item - different user owns the item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": "vault"},
                    "user_id": {"S": "other-user"},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": "key"},
                    "upload_status": {"S": "COMPLETE"},
                    "encrypted_metadata": {"B": b"encrypted"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        request = CreateShareRequest(item_id=item_id)
        with pytest.raises(Exception, match="not found"):
            share_service.create_share(user_id, request)


class TestGetShare:
    """Test suite for ShareService.get_share."""

    def test_get_share_success(self, share_service, dynamodb_stubber, s3_stubber):
        """Get share returns metadata and download URL."""
        share_id = "test-share-123"
        item_id = "test-item-456"
        vault_id = "test-vault-789"
        client_ip = "1.2.3.4"

        # Stub rate limit check (get_item returns no existing rate row)
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-shares-table", "Key": ANY},
        )

        # Stub rate limit put (create/update rate row)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {"TableName": "test-shares-table", "Item": ANY},
        )

        # Stub get share metadata
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": "owner"},
                    "created_at": {"N": str(int(time.time()))},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        # Stub get item (to find s3_key)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": "owner"},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/{vault_id}/{item_id}"},
                    "upload_status": {"S": "COMPLETE"},
                    "encrypted_metadata": {"B": b"encrypted"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        # Stub update access count
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        response = share_service.get_share(share_id, client_ip)

        assert response.share_id == share_id
        assert response.item_id == item_id
        assert response.download_url is not None
        assert response.url_expires_at > 0

    def test_get_share_revoked(self, share_service, dynamodb_stubber):
        """Get revoked share raises error."""
        share_id = "test-share-123"
        client_ip = "1.2.3.4"

        # Stub rate limit check
        dynamodb_stubber.add_response("get_item", {}, {"TableName": "test-shares-table", "Key": ANY})
        dynamodb_stubber.add_response("put_item", {}, {"TableName": "test-shares-table", "Item": ANY})

        # Stub get share metadata - revoked
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item"},
                    "vault_id": {"S": "vault"},
                    "user_id": {"S": "owner"},
                    "created_at": {"N": str(int(time.time()))},
                    "is_revoked": {"BOOL": True},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        with pytest.raises(Exception, match="revoked"):
            share_service.get_share(share_id, client_ip)

    def test_get_share_expired(self, share_service, dynamodb_stubber):
        """Get expired share raises error."""
        share_id = "test-share-123"
        client_ip = "1.2.3.4"

        # Stub rate limit check
        dynamodb_stubber.add_response("get_item", {}, {"TableName": "test-shares-table", "Key": ANY})
        dynamodb_stubber.add_response("put_item", {}, {"TableName": "test-shares-table", "Item": ANY})

        # Stub get share metadata - expired
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item"},
                    "vault_id": {"S": "vault"},
                    "user_id": {"S": "owner"},
                    "created_at": {"N": str(int(time.time()) - 86400)},
                    "expires_at": {"N": str(int(time.time()) - 3600)},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        with pytest.raises(Exception, match="expired"):
            share_service.get_share(share_id, client_ip)


class TestRevokeShare:
    """Test suite for ShareService.revoke_share."""

    def test_revoke_share_success(self, share_service, dynamodb_stubber):
        """Revoke share sets is_revoked and TTL."""
        share_id = "test-share-123"
        user_id = "test-user-123"

        # Stub get share metadata
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item"},
                    "vault_id": {"S": "vault"},
                    "user_id": {"S": user_id},
                    "created_at": {"N": str(int(time.time()))},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        # Stub update item (set revoked + TTL)
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        response = share_service.revoke_share(user_id, share_id)

        assert response.message == "Share revoked successfully"
        assert response.revoked_at > 0

    def test_revoke_share_wrong_owner(self, share_service, dynamodb_stubber):
        """Revoke share fails if user doesn't own it."""
        share_id = "test-share-123"

        # Stub get share metadata - different owner
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item"},
                    "vault_id": {"S": "vault"},
                    "user_id": {"S": "other-user"},
                    "created_at": {"N": str(int(time.time()))},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        with pytest.raises(Exception, match="not found"):
            share_service.revoke_share("test-user-123", share_id)
```

### Step 3: Add share_service fixture to conftest.py

Modify `lambda/tests/conftest.py` - add import and fixture:

```python
from src.api.services.share_service import ShareService

@pytest.fixture
def share_service(boto_session, shares_table_name, items_table_name, files_bucket_name):
    """Create a ShareService instance for testing."""
    return ShareService(
        session=boto_session,
        shares_table_name=shares_table_name,
        items_table_name=items_table_name,
        s3_bucket_name=files_bucket_name,
    )
```

### Step 4: Run tests to verify they fail

Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest tests/unit/services/test_share_service.py -v`
Expected: FAIL with "No module named 'src.api.services.share_service'"

### Step 5: Write ShareService implementation

Create `lambda/src/api/services/share_service.py`:

```python
"""
Share service layer for Cortex API.

This module implements business logic for file sharing operations including
share creation, access, revocation, and rate limiting.

Requirements: 17.3, 17.4, 17.5, 18.1, 18.2, 18.5, 18.6, 18.7, 18.9, 31.5
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceError,
)

from src.shared.models import (
    CreateShareRequest,
    CreateShareResponse,
    GetShareResponse,
    RevokeShareResponse,
)
from src.shared.repository import DynamoDBRepository, S3Repository, build_s3_key

logger = Logger(child=True)

PRESIGNED_URL_EXPIRATION = 900  # 15 minutes
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
TTL_GRACE_PERIOD = 86400  # 24 hours after expiration
TTL_REVOKED_CLEANUP = 604800  # 7 days after revocation
TTL_RATE_LIMIT_CLEANUP = 7200  # 2 hours after window


class ShareRevokedError(ServiceError):
    """Share has been revoked."""

    def __init__(self, msg: str = "Share has been revoked"):
        super().__init__(status_code=410, msg=msg)


class ShareExpiredError(ServiceError):
    """Share has expired."""

    def __init__(self, msg: str = "Share has expired"):
        super().__init__(status_code=410, msg=msg)


class RateLimitExceededError(ServiceError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(status_code=429, msg="Rate limit exceeded")


class ShareService:
    """Service layer for share operations."""

    def __init__(
        self,
        session: boto3.Session,
        shares_table_name: str,
        items_table_name: str,
        s3_bucket_name: str,
    ):
        self.shares_repo = DynamoDBRepository(session, shares_table_name)
        self.items_repo = DynamoDBRepository(session, items_table_name)
        self.s3_repo = S3Repository(session, s3_bucket_name)

    def create_share(self, user_id: str, request: CreateShareRequest) -> CreateShareResponse:
        """
        Create a share for a file.

        Verifies the user owns the item, then stores share metadata.
        No key material is stored server-side.

        Args:
            user_id: Authenticated user ID
            request: Share creation request

        Returns:
            CreateShareResponse with share_id and timestamps

        Raises:
            NotFoundError: If item not found or user doesn't own it
            BadRequestError: If item is not a MEDIA type or upload incomplete
        """
        # Verify item exists and user owns it
        item = self.items_repo.get_item({"PK": f"ITEM#{request.item_id}"})

        if not item:
            raise NotFoundError("Item not found")

        if item["user_id"] != user_id:
            raise NotFoundError("Item not found")

        if item.get("item_type") != "MEDIA":
            raise BadRequestError("Only MEDIA items can be shared")

        if item.get("upload_status") == "PENDING":
            raise BadRequestError("Item upload not yet complete")

        share_id = str(uuid.uuid4())
        now = int(time.time())

        share_item = {
            "PK": f"SHARE#{share_id}",
            "SK": "METADATA",
            "share_id": share_id,
            "item_id": request.item_id,
            "vault_id": item["vault_id"],
            "user_id": user_id,
            "created_at": now,
            "is_revoked": False,
            "access_count": 0,
        }

        if request.expires_at is not None:
            share_item["expires_at"] = request.expires_at
            share_item["ttl"] = request.expires_at + TTL_GRACE_PERIOD

        # Conditional write to prevent duplicate share IDs
        self.shares_repo.put_item(
            share_item,
            condition_expression="attribute_not_exists(PK)",
        )

        logger.info(
            "Share created",
            extra={
                "share_id": share_id,
                "item_id": request.item_id,
                "user_id": user_id,
                "has_expiration": request.expires_at is not None,
            },
        )

        return CreateShareResponse(
            share_id=share_id,
            created_at=now,
            expires_at=request.expires_at,
        )

    def get_share(self, share_id: str, client_ip: str) -> GetShareResponse:
        """
        Access a shared file (anonymous).

        Checks rate limits, validates share state, generates presigned URL.

        Args:
            share_id: Share identifier
            client_ip: Client IP address for rate limiting

        Returns:
            GetShareResponse with metadata and download URL

        Raises:
            NotFoundError: If share not found
            ShareRevokedError: If share has been revoked
            ShareExpiredError: If share has expired
            RateLimitExceededError: If rate limit exceeded
        """
        # Check rate limit
        self._check_rate_limit(share_id, client_ip)

        # Fetch share metadata
        share = self.shares_repo.get_item({
            "PK": f"SHARE#{share_id}",
            "SK": "METADATA",
        })

        if not share:
            raise NotFoundError("Share not found")

        # Check if revoked
        if share.get("is_revoked", False):
            raise ShareRevokedError()

        # Check if expired
        expires_at = share.get("expires_at")
        if expires_at is not None and int(expires_at) < int(time.time()):
            raise ShareExpiredError()

        # Get item to find S3 key
        item_id = share["item_id"]
        item = self.items_repo.get_item({"PK": f"ITEM#{item_id}"})

        if not item:
            logger.error("Shared item not found", extra={"share_id": share_id, "item_id": item_id})
            raise NotFoundError("Shared file no longer available")

        # Generate presigned download URL
        s3_key = item["s3_key"]
        download_url = self.s3_repo.generate_download_url(s3_key, PRESIGNED_URL_EXPIRATION)

        now = int(time.time())
        url_expires_at = now + PRESIGNED_URL_EXPIRATION

        # Update access count (best-effort, don't fail on this)
        try:
            self.shares_repo.update_item_conditional(
                key={"PK": f"SHARE#{share_id}", "SK": "METADATA"},
                update_expression="SET access_count = access_count + :inc, last_accessed_at = :now",
                condition_expression="attribute_exists(PK)",
                expression_attribute_values={":inc": 1, ":now": now},
            )
        except Exception:
            logger.warning("Failed to update access count", extra={"share_id": share_id})

        logger.info(
            "Share accessed",
            extra={
                "share_id": share_id,
                "item_id": item_id,
                "client_ip": client_ip,
            },
        )

        return GetShareResponse(
            share_id=share_id,
            item_id=item_id,
            download_url=download_url,
            url_expires_at=url_expires_at,
            expires_at=int(expires_at) if expires_at is not None else None,
        )

    def revoke_share(self, user_id: str, share_id: str) -> RevokeShareResponse:
        """
        Revoke a share.

        Sets the share as revoked and schedules TTL cleanup.

        Args:
            user_id: Authenticated user ID
            share_id: Share to revoke

        Returns:
            RevokeShareResponse with confirmation

        Raises:
            NotFoundError: If share not found or user doesn't own it
        """
        share = self.shares_repo.get_item({
            "PK": f"SHARE#{share_id}",
            "SK": "METADATA",
        })

        if not share:
            raise NotFoundError("Share not found")

        if share["user_id"] != user_id:
            raise NotFoundError("Share not found")

        now = int(time.time())

        self.shares_repo.update_item_conditional(
            key={"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            update_expression="SET is_revoked = :revoked, revoked_at = :now, #ttl_attr = :ttl",
            condition_expression="attribute_exists(PK)",
            expression_attribute_values={
                ":revoked": True,
                ":now": now,
                ":ttl": now + TTL_REVOKED_CLEANUP,
            },
            expression_attribute_names={"#ttl_attr": "ttl"},
        )

        logger.info(
            "Share revoked",
            extra={"share_id": share_id, "user_id": user_id},
        )

        return RevokeShareResponse(
            message="Share revoked successfully",
            revoked_at=now,
        )

    def _check_rate_limit(self, share_id: str, client_ip: str) -> None:
        """
        Check and enforce rate limiting per IP per share per hour.

        Args:
            share_id: Share identifier
            client_ip: Client IP address

        Raises:
            RateLimitExceededError: If rate limit exceeded (HTTP 429)
        """
        now = int(time.time())
        window_start = now - (now % RATE_LIMIT_WINDOW_SECONDS)  # Floor to hour

        rate_key = {
            "PK": f"SHARE#{share_id}",
            "SK": f"RATE#{client_ip}",
        }

        rate_item = self.shares_repo.get_item(rate_key)

        if rate_item and int(rate_item.get("window_start", 0)) == window_start:
            attempt_count = int(rate_item.get("attempt_count", 0))
            if attempt_count >= RATE_LIMIT_MAX_ATTEMPTS:
                retry_after = window_start + RATE_LIMIT_WINDOW_SECONDS - now
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "share_id": share_id,
                        "client_ip": client_ip,
                        "attempt_count": attempt_count,
                    },
                )
                raise RateLimitExceededError(retry_after=retry_after)

        # Increment or create rate limit entry
        self.shares_repo.put_item({
            "PK": f"SHARE#{share_id}",
            "SK": f"RATE#{client_ip}",
            "attempt_count": (int(rate_item.get("attempt_count", 0)) + 1)
            if rate_item and int(rate_item.get("window_start", 0)) == window_start
            else 1,
            "window_start": window_start,
            "ttl": window_start + TTL_RATE_LIMIT_CLEANUP,
        })
```

### Step 6: Run tests to verify they pass

Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest tests/unit/services/test_share_service.py -v`
Expected: All tests PASS

### Step 7: Commit

```bash
git add lambda/src/api/services/share_service.py lambda/src/shared/models.py lambda/tests/unit/services/test_share_service.py lambda/tests/conftest.py
git commit -m "feat: add share service layer with rate limiting and TTL"
```

---

## Task 3: Share Route Handlers

**Files:**
- Modify: `lambda/src/api/routes/shares.py` (replace stubs)
- Modify: `lambda/src/environment/service_provider.py` (wire up ShareService)
- Modify: `lambda/tests/unit/routes/test_share_routes.py` (replace stub tests)

### Step 1: Write the failing route tests

Replace `lambda/tests/unit/routes/test_share_routes.py` with:

```python
"""
Unit tests for share route handlers.

Tests verify that share routes work correctly through the lambda handler entrypoint.
"""

import json
import time

import pytest
from botocore.stub import ANY

from src.entrypoint.api import lambda_handler


class TestCreateShareRoute:
    """Test suite for CreateShareRoute through lambda handler."""

    def test_create_share_route_handler(self, mock_service_provider, dynamodb_stubber):
        """Test create share returns share_id and timestamps."""
        user_id = "test-user-123"
        item_id = "test-item-456"

        # Stub get_item for item lookup
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": user_id},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/vault-123/{item_id}"},
                    "upload_status": {"S": "COMPLETE"},
                    "encrypted_metadata": {"B": b"encrypted"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        # Stub put_item for share creation
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {"TableName": "test-shares-table", "Item": ANY, "ConditionExpression": ANY},
        )

        event = {
            "resource": "/v1/shares",
            "path": "/v1/shares",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"item_id": item_id}),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "share_id" in body
        assert "created_at" in body


class TestGetShareRoute:
    """Test suite for GetShareRoute through lambda handler."""

    def test_get_share_route_handler(self, mock_service_provider, dynamodb_stubber):
        """Test get share returns metadata and download URL."""
        share_id = "test-share-123"
        item_id = "test-item-456"

        # Stub rate limit check
        dynamodb_stubber.add_response("get_item", {}, {"TableName": "test-shares-table", "Key": ANY})
        dynamodb_stubber.add_response("put_item", {}, {"TableName": "test-shares-table", "Item": ANY})

        # Stub get share metadata
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "owner"},
                    "created_at": {"N": str(int(time.time()))},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        # Stub get item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "owner"},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/vault-123/{item_id}"},
                    "upload_status": {"S": "COMPLETE"},
                    "encrypted_metadata": {"B": b"encrypted"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        # Stub update access count
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        event = {
            "resource": "/v1/shares/{share_id}",
            "path": f"/v1/shares/{share_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"share_id": share_id},
            "requestContext": {
                "requestId": "test-request-id",
                "identity": {"sourceIp": "1.2.3.4"},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["share_id"] == share_id
        assert "download_url" in body


class TestRevokeShareRoute:
    """Test suite for RevokeShareRoute through lambda handler."""

    def test_revoke_share_route_handler(self, mock_service_provider, dynamodb_stubber):
        """Test revoke share returns confirmation."""
        share_id = "test-share-123"
        user_id = "test-user-123"

        # Stub get share metadata
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item"},
                    "vault_id": {"S": "vault"},
                    "user_id": {"S": user_id},
                    "created_at": {"N": str(int(time.time()))},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            {"TableName": "test-shares-table", "Key": ANY},
        )

        # Stub update item
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
            },
        )

        event = {
            "resource": "/v1/shares/{share_id}",
            "path": f"/v1/shares/{share_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"share_id": share_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Share revoked successfully"
        assert "revoked_at" in body
```

### Step 2: Run tests to verify they fail

Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest tests/unit/routes/test_share_routes.py -v`
Expected: FAIL (stubs return placeholder response, not real data)

### Step 3: Replace share route stubs with real implementation

Replace `lambda/src/api/routes/shares.py`:

```python
"""
File sharing route handlers for Cortex API.

This module implements sharing-related endpoints including share creation,
access, and revocation.

Requirements: 17.3, 17.4, 17.5, 18.2, 18.5
"""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from pydantic import ValidationError as PydanticValidationError

from src.api.routes.base_route import BaseRoute
from src.api.services.share_service import ShareService
from src.shared.auth import get_user_from_context
from src.shared.models import CreateShareRequest

logger = Logger(child=True)


class CreateShareRoute(BaseRoute):
    """Handle share creation."""

    def __init__(self, share_service: ShareService):
        self.share_service = share_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.post("/v1/shares")
        def handle():
            """
            Create share metadata for a file.

            The client handles all encryption. Server only stores
            metadata (share ID, item reference, timestamps).
            No key material is stored.

            Requirements: 17.4, 17.5
            """
            try:
                body = app.current_event.json_body
                request = CreateShareRequest(**body)
            except PydanticValidationError as e:
                logger.warning("Request validation failed", extra={"errors": e.errors()})
                raise BadRequestError("Invalid request format")

            user_id = get_user_from_context(app.current_event)

            response = self.share_service.create_share(user_id, request)

            logger.info(
                "Share created successfully",
                extra={
                    "user_id": user_id,
                    "share_id": response.share_id,
                },
            )

            return {
                "share_id": response.share_id,
                "created_at": response.created_at,
                "expires_at": response.expires_at,
            }


class GetShareRoute(BaseRoute):
    """Handle share access (anonymous)."""

    def __init__(self, share_service: ShareService):
        self.share_service = share_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/shares/<share_id>")
        def handle(share_id: str):
            """
            Access shared file (anonymous). No authentication required.

            Returns share metadata and a presigned S3 download URL.
            Rate-limited per IP per share per hour.

            Requirements: 17.5, 17.7, 18.2, 18.5
            """
            # Extract client IP for rate limiting
            request_context = app.current_event.get("requestContext", {})
            identity = request_context.get("identity", {})
            client_ip = identity.get("sourceIp", "unknown")

            response = self.share_service.get_share(share_id, client_ip)

            logger.info(
                "Share accessed successfully",
                extra={"share_id": share_id},
            )

            return {
                "share_id": response.share_id,
                "item_id": response.item_id,
                "download_url": response.download_url,
                "url_expires_at": response.url_expires_at,
                "expires_at": response.expires_at,
            }


class RevokeShareRoute(BaseRoute):
    """Handle share revocation."""

    def __init__(self, share_service: ShareService):
        self.share_service = share_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.delete("/v1/shares/<share_id>")
        def handle(share_id: str):
            """
            Revoke a share. Requires authentication.

            Sets the share as revoked and schedules TTL cleanup
            after 7 days for audit trail.

            Requirements: 18.5
            """
            user_id = get_user_from_context(app.current_event)

            response = self.share_service.revoke_share(user_id, share_id)

            logger.info(
                "Share revoked successfully",
                extra={"share_id": share_id, "user_id": user_id},
            )

            return {
                "message": response.message,
                "revoked_at": response.revoked_at,
            }
```

### Step 4: Wire up ShareService in service_provider.py

Modify `lambda/src/environment/service_provider.py`:

Add import:
```python
from src.api.services.share_service import ShareService
```

Add service property (after `collection_service`):
```python
    @cached_property
    def share_service(self):
        """Create share service."""
        return ShareService(
            session=self.session,
            shares_table_name=self.shares_table_name,
            items_table_name=self.items_table_name,
            s3_bucket_name=self.files_bucket_name,
        )
```

Update share route registrations (replace lines 183-185):
```python
                # Share routes
                CreateShareRoute(share_service=self.share_service),
                GetShareRoute(share_service=self.share_service),
                RevokeShareRoute(share_service=self.share_service),
```

### Step 5: Run tests to verify they pass

Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest tests/unit/routes/test_share_routes.py -v`
Expected: All tests PASS

Also run full test suite:
Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest -v`
Expected: All tests PASS

### Step 6: Commit

```bash
git add lambda/src/api/routes/shares.py lambda/src/environment/service_provider.py lambda/tests/unit/routes/test_share_routes.py
git commit -m "feat: implement share route handlers with service injection"
```

---

## Task 4: DynamoDB TTL Configuration

**Files:**
- Modify: `cdk/lib/stacks/service.ts`

### Step 1: Add TTL to shares table

Modify `cdk/lib/stacks/service.ts` in `createSharesTable()` method. After the existing table definition add TTL configuration:

```typescript
private createSharesTable(): TableV2 {
    const table = new TableV2(this, "SharesTable", {
        tableName: this.resourceName("shares"),
        partitionKey: {
            name: "PK",
            type: AttributeType.STRING,
        },
        sortKey: {
            name: "SK",
            type: AttributeType.STRING,
        },
        timeToLiveAttribute: "ttl",
        ...DYNAMODB_DEFAULT_PROPS,
    });
    return table;
}
```

### Step 2: Verify CDK synth works

Run: `cd /Users/lcmessen/cortex/cdk && npx cdk synth --quiet`
Expected: Successful synthesis without errors

### Step 3: Commit

```bash
git add cdk/lib/stacks/service.ts
git commit -m "feat: enable DynamoDB TTL on shares table for auto-cleanup"
```

---

## Task 5: Property Test for Share Keys

**Files:**
- Create: `packages/encryption/tests/property/test_share_encryption.test.ts`

### Step 1: Write Property 20 test

Create `packages/encryption/tests/property/test_share_encryption.test.ts`:

```typescript
/**
 * Property-Based Tests for Share Encryption Module
 *
 * Property 20: Share keys enable file access without vault password
 * Validates: Requirements 17.1, 17.4
 */

import fc from 'fast-check';
import {
  generateDek,
  wrapDek,
  unwrapDek,
  encryptFileWithDek,
  decryptFileWithDek,
  DekUnwrapError,
} from '../../src/lib/envelope-encryption';
import {
  deriveShareKeys,
  computeShareHmac,
  verifyShareHmac,
  encodeShareBlob,
  decodeShareBlob,
} from '../../src/lib/share-encryption';

describe('Share Encryption Property Tests', () => {
  /**
   * Feature: cortex-sharing, Property 20: Share keys enable file access without vault password
   *
   * Validates: Requirements 17.1, 17.4
   *
   * End-to-end: encrypt file with vault KEK → create share (re-wrap DEK with
   * share key) → access share with only share password (no vault KEK) →
   * decrypt file → content matches original.
   */
  test('Property 20: Share keys enable file access without vault password', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 1, maxLength: 10000 }),  // file content
        fc.uint8Array({ minLength: 32, maxLength: 32 }),     // vault KEK
        fc.string({ minLength: 16, maxLength: 64 }),         // share password
        async (fileContent, vaultKek, sharePassword) => {
          // === OWNER: Encrypt file with vault KEK ===
          const { encryptedContent, wrappedDek } = await encryptFileWithDek(fileContent, vaultKek);

          // === OWNER: Create share ===
          const salt = crypto.getRandomValues(new Uint8Array(16));
          const { encryptionKey: shareKey } = await deriveShareKeys(sharePassword, salt);

          // Unwrap DEK with vault KEK, re-wrap with share key
          const dek = unwrapDek(wrappedDek, vaultKek);
          const shareWrappedDek = await wrapDek(dek, shareKey);
          dek.fill(0); // Zero DEK after use

          // === RECIPIENT: Access share (NO vault KEK used) ===
          const { encryptionKey: recipientShareKey } = await deriveShareKeys(sharePassword, salt);

          // Unwrap DEK with share key
          const recipientDek = unwrapDek(shareWrappedDek, recipientShareKey);

          // Decrypt file content using raw DEK (not via decryptFileWithDek since
          // wrappedDek was wrapped with share key, not vault KEK)
          const { chacha20poly1305 } = await import('@noble/ciphers/chacha');
          const nonce = encryptedContent.slice(0, 12);
          const ciphertext = encryptedContent.slice(12);
          const cipher = chacha20poly1305(recipientDek, nonce);
          const decrypted = cipher.decrypt(ciphertext);
          recipientDek.fill(0); // Zero DEK after use

          // Verify decrypted content matches original
          expect(decrypted).toEqual(fileContent);
        }
      ),
      { numRuns: 50 }
    );
  });

  /**
   * Property 20b: Wrong share password fails to unwrap DEK
   */
  test('Property 20b: Wrong share password cannot unwrap DEK', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 32, maxLength: 32 }),     // vault KEK
        fc.string({ minLength: 16, maxLength: 64 }),         // correct password
        fc.string({ minLength: 16, maxLength: 64 }),         // wrong password
        async (vaultKek, correctPassword, wrongPassword) => {
          if (correctPassword === wrongPassword) return true;

          const salt = crypto.getRandomValues(new Uint8Array(16));
          const { encryptionKey: shareKey } = await deriveShareKeys(correctPassword, salt);

          // Wrap a DEK with share key
          const dek = await generateDek();
          const shareWrappedDek = await wrapDek(dek, shareKey);
          dek.fill(0);

          // Try to unwrap with wrong password
          const { encryptionKey: wrongKey } = await deriveShareKeys(wrongPassword, salt);
          expect(() => unwrapDek(shareWrappedDek, wrongKey)).toThrow(DekUnwrapError);

          return true;
        }
      ),
      { numRuns: 50 }
    );
  });

  /**
   * Property 20c: HMAC verification catches metadata tampering
   */
  test('Property 20c: HMAC detects metadata tampering', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 16, maxLength: 64 }),         // password
        fc.string({ minLength: 1, maxLength: 50 }),          // correct shareId
        fc.string({ minLength: 1, maxLength: 50 }),          // tampered shareId
        fc.integer({ min: 1000000000, max: 2000000000 }),    // expiresAt
        async (password, correctShareId, tamperedShareId, expiresAt) => {
          if (correctShareId === tamperedShareId) return true;

          const salt = crypto.getRandomValues(new Uint8Array(16));
          const { hmacKey } = await deriveShareKeys(password, salt);

          const mac = computeShareHmac(hmacKey, correctShareId, expiresAt);

          // Verification with correct metadata succeeds
          expect(verifyShareHmac(hmacKey, correctShareId, expiresAt, mac)).toBe(true);

          // Verification with tampered shareId fails
          expect(verifyShareHmac(hmacKey, tamperedShareId, expiresAt, mac)).toBe(false);

          return true;
        }
      ),
      { numRuns: 50 }
    );
  });

  /**
   * Property 20d: Blob encode/decode round-trip
   */
  test('Property 20d: Share blob encode/decode round-trip', () => {
    fc.assert(
      fc.property(
        fc.uint8Array({ minLength: 16, maxLength: 16 }),  // salt
        fc.uint8Array({ minLength: 65, maxLength: 65 }),  // wrappedDek
        fc.uint8Array({ minLength: 32, maxLength: 32 }),  // hmac
        (salt, wrappedDek, hmacVal) => {
          const encoded = encodeShareBlob(1, salt, wrappedDek, hmacVal);
          const decoded = decodeShareBlob(encoded);

          expect(decoded.version).toBe(1);
          expect(decoded.salt).toEqual(salt);
          expect(decoded.wrappedDek).toEqual(wrappedDek);
          expect(decoded.hmac).toEqual(hmacVal);
        }
      ),
      { numRuns: 100 }
    );
  });
});
```

### Step 2: Run tests to verify they pass

Run: `cd /Users/lcmessen/cortex && npx --workspace=packages/encryption jest tests/property/test_share_encryption.test.ts`
Expected: All tests PASS (these test against already-written implementation from Task 1)

### Step 3: Commit

```bash
git add packages/encryption/tests/property/test_share_encryption.test.ts
git commit -m "feat: add property test 20 - share keys enable file access without vault password"
```

---

## Task 6: Frontend Share Components

**Files:**
- Create: `packages/web/src/components/ShareCreate.tsx`
- Create: `packages/web/src/components/ShareAccess.tsx`
- Modify: `packages/web/src/App.tsx`

### Step 1: Create ShareCreate component

Create `packages/web/src/components/ShareCreate.tsx`:

```tsx
import { useState } from 'react';
import {
  deriveShareKeys,
  computeShareHmac,
  encodeShareBlob,
} from '@cortex/encryption';
import { unwrapDek, wrapDek } from '@cortex/encryption';

interface ShareCreateProps {
  itemId: string;
  wrappedDek: Uint8Array;
  vaultKek: Uint8Array;
  apiBaseUrl: string;
}

export function ShareCreate({ itemId, wrappedDek, vaultKek, apiBaseUrl }: ShareCreateProps) {
  const [password, setPassword] = useState('');
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [shareId, setShareId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passwordValid = password.length >= 16;

  const handleCreateShare = async () => {
    if (!passwordValid) return;
    setLoading(true);
    setError(null);

    try {
      // 1. Generate salt and derive share keys
      const salt = crypto.getRandomValues(new Uint8Array(16));
      const { encryptionKey, hmacKey } = await deriveShareKeys(password, salt);

      // 2. Unwrap file's DEK with vault KEK, re-wrap with share key
      const dek = unwrapDek(wrappedDek, vaultKek);
      const shareWrappedDek = await wrapDek(dek, encryptionKey);
      dek.fill(0);

      // 3. POST share metadata to server
      const expiresAt = expiresIn ? Math.floor(Date.now() / 1000) + expiresIn : undefined;
      const res = await fetch(`${apiBaseUrl}/v1/shares`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId, expires_at: expiresAt }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Failed to create share');

      // 4. Compute HMAC over share metadata
      const mac = computeShareHmac(hmacKey, data.share_id, expiresAt);

      // 5. Encode blob and construct URL
      const blob = encodeShareBlob(1, salt, shareWrappedDek, mac);
      const url = `${window.location.origin}/s/${data.share_id}#${blob}`;

      setShareUrl(url);
      setShareId(data.share_id);

      // Zero sensitive material
      encryptionKey.fill(0);
      hmacKey.fill(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create share');
    } finally {
      setLoading(false);
    }
  };

  if (shareUrl) {
    return (
      <div>
        <h3>Share Link Created</h3>
        <input readOnly value={shareUrl} style={{ width: '100%' }} onClick={e => (e.target as HTMLInputElement).select()} />
        <button onClick={() => navigator.clipboard.writeText(shareUrl)}>Copy Link</button>
        <p><strong>Share ID:</strong> {shareId}</p>
        <p><strong>Warning:</strong> Do not use URL shorteners — they expose the encryption key to the shortener service.</p>
        <p>If the link gets truncated, the recipient can enter the Share ID and password manually at /s</p>
      </div>
    );
  }

  return (
    <div>
      <h3>Share File</h3>
      <div>
        <label>Share Password (minimum 16 characters)</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder="Enter a strong password..."
        />
        {password.length > 0 && !passwordValid && (
          <p style={{ color: 'red' }}>Password must be at least 16 characters</p>
        )}
      </div>
      <div>
        <label>Expires In</label>
        <select value={expiresIn ?? ''} onChange={e => setExpiresIn(e.target.value ? Number(e.target.value) : null)}>
          <option value="">Never</option>
          <option value={3600}>1 hour</option>
          <option value={86400}>1 day</option>
          <option value={604800}>7 days</option>
          <option value={2592000}>30 days</option>
        </select>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <button onClick={handleCreateShare} disabled={!passwordValid || loading}>
        {loading ? 'Creating...' : 'Create Share Link'}
      </button>
    </div>
  );
}
```

### Step 2: Create ShareAccess component

Create `packages/web/src/components/ShareAccess.tsx`:

```tsx
import { useState, useEffect } from 'react';
import {
  deriveShareKeys,
  verifyShareHmac,
  decodeShareBlob,
} from '@cortex/encryption';
import { unwrapDek, DekUnwrapError } from '@cortex/encryption';
import { chacha20poly1305 } from '@noble/ciphers/chacha';

interface ShareAccessProps {
  apiBaseUrl: string;
}

export function ShareAccess({ apiBaseUrl }: ShareAccessProps) {
  const [shareId, setShareId] = useState('');
  const [blob, setBlob] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failCount, setFailCount] = useState(0);

  // Extract shareId and blob from URL on mount
  useEffect(() => {
    const path = window.location.pathname;
    const match = path.match(/^\/s\/(.+)$/);
    if (match) setShareId(match[1]);

    const fragment = window.location.hash.slice(1);
    if (fragment) setBlob(fragment);
  }, []);

  const handleAccess = async () => {
    if (!shareId || !password) return;

    // Client-side rate limiting: exponential backoff after 3 failures
    if (failCount >= 3) {
      const delay = Math.min(1000 * Math.pow(2, failCount - 3), 30000);
      setError(`Too many attempts. Please wait ${Math.ceil(delay / 1000)} seconds.`);
      await new Promise(r => setTimeout(r, delay));
    }

    setLoading(true);
    setError(null);

    try {
      let blobData: { version: number; salt: Uint8Array; wrappedDek: Uint8Array; hmac: Uint8Array };

      if (blob) {
        blobData = decodeShareBlob(blob);
      } else {
        setError('No share data found. The link may have been truncated. Please enter the share ID and password.');
        setLoading(false);
        return;
      }

      // 1. Fetch share metadata from server
      const res = await fetch(`${apiBaseUrl}/v1/shares/${shareId}`);
      if (res.status === 429) {
        setError('Rate limit exceeded. Please try again later.');
        setLoading(false);
        return;
      }
      if (res.status === 410) {
        const data = await res.json();
        setError(data.message || 'This share is no longer available.');
        setLoading(false);
        return;
      }
      if (!res.ok) throw new Error('Share not found');
      const shareData = await res.json();

      // 2. Derive keys from password
      const { encryptionKey, hmacKey } = await deriveShareKeys(password, blobData.salt);

      // 3. Verify HMAC over metadata
      if (!verifyShareHmac(hmacKey, shareData.share_id, shareData.expires_at, blobData.hmac)) {
        hmacKey.fill(0);
        encryptionKey.fill(0);
        setError('Share metadata verification failed. The link may have been tampered with.');
        setLoading(false);
        return;
      }
      hmacKey.fill(0);

      // 4. Unwrap DEK
      let dek: Uint8Array;
      try {
        dek = unwrapDek(blobData.wrappedDek, encryptionKey);
      } catch (err) {
        encryptionKey.fill(0);
        if (err instanceof DekUnwrapError) {
          setFailCount(c => c + 1);
          setError('Incorrect password. Please try again.');
          setLoading(false);
          return;
        }
        throw err;
      }
      encryptionKey.fill(0);

      // 5. Download encrypted file
      const fileRes = await fetch(shareData.download_url);
      if (!fileRes.ok) throw new Error('Failed to download file');
      const encryptedContent = new Uint8Array(await fileRes.arrayBuffer());

      // 6. Decrypt file
      const nonce = encryptedContent.slice(0, 12);
      const ciphertext = encryptedContent.slice(12);
      const cipher = chacha20poly1305(dek, nonce);
      const decrypted = cipher.decrypt(ciphertext);
      dek.fill(0);

      // 7. Trigger browser download
      const blobObj = new Blob([decrypted]);
      const url = URL.createObjectURL(blobObj);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'shared-file';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to access share');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h2>Access Shared File</h2>
      <div>
        <label>Share ID</label>
        <input value={shareId} onChange={e => setShareId(e.target.value)} placeholder="Enter share ID..." />
      </div>
      <div>
        <label>Share Password</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter share password..." />
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <button onClick={handleAccess} disabled={!shareId || !password || loading}>
        {loading ? 'Decrypting...' : 'Access File'}
      </button>
    </div>
  );
}
```

### Step 3: Update App.tsx to route share access

Modify `packages/web/src/App.tsx`:

```tsx
import { ShareAccess } from './components/ShareAccess';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function App() {
  const isShareRoute = window.location.pathname.startsWith('/s');

  if (isShareRoute) {
    return <ShareAccess apiBaseUrl={API_BASE_URL} />;
  }

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Cortex</h1>
      <p>Zero-Knowledge Media Backup</p>
    </div>
  );
}

export default App;
```

### Step 4: Verify frontend builds

Run: `cd /Users/lcmessen/cortex && npm run --workspace=packages/web build`
Expected: Build succeeds

### Step 5: Commit

```bash
git add packages/web/src/components/ShareCreate.tsx packages/web/src/components/ShareAccess.tsx packages/web/src/App.tsx
git commit -m "feat: add share creation and access frontend components"
```

---

## Task 7: Update task list and final verification

### Step 1: Run all backend tests

Run: `cd /Users/lcmessen/cortex/lambda && python -m pytest -v`
Expected: All tests PASS

### Step 2: Run all encryption tests

Run: `cd /Users/lcmessen/cortex && npx --workspace=packages/encryption jest`
Expected: All tests PASS

### Step 3: Run frontend build

Run: `cd /Users/lcmessen/cortex && npm run --workspace=packages/web build`
Expected: Build succeeds

### Step 4: Update tasks.md

Mark tasks 17.1-17.5 as complete in `.kiro/specs/cortex/tasks.md`:
- `[x] 17. Implement file sharing system`
- `[x] 17.1 Build frontend share creation with envelope encryption`
- `[x] 17.2 Create share route handlers`
- `[x] 17.3 Create share service layer with server-side rate limiting`
- `[x] 17.4 Build frontend share access with envelope encryption and HMAC verification`
- `[x] 17.5 Write property test for share keys enable file access without vault password`

### Step 5: Commit

```bash
git add .kiro/specs/cortex/tasks.md
git commit -m "docs: mark task 17 (file sharing) as complete"
```
