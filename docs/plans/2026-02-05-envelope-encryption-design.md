# Envelope Encryption for Media Files — Design

Task 6.12 and subtasks 6.12.1–6.12.5.

## Overview

Each media file gets a unique Data Encryption Key (DEK). The DEK encrypts the file content, then the DEK itself is wrapped (encrypted) with the vault's Key Encryption Key (KEK). This means key rotation only requires re-wrapping DEKs — not re-encrypting every file.

## Binary Format

### Wrapped DEK without HMAC binding (65 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 1 | Version (`0x01`) |
| 1 | 4 | Timestamp (uint32_be, Unix epoch seconds) |
| 5 | 12 | Nonce (ChaCha20-Poly1305) |
| 17 | 32 | Encrypted DEK |
| 49 | 16 | Auth tag |

### Wrapped DEK with HMAC binding (97 bytes)

Same as above, plus:

| Offset | Size | Field |
|--------|------|-------|
| 65 | 32 | HMAC-SHA256(DEK, file_id) |

Detection: buffer length of 97 indicates HMAC binding is present; 65 indicates no binding. Version byte is `0x01` for both variants.

## Exported API

File: `packages/encryption/src/lib/envelope-encryption.ts`

### Types

```typescript
export type DekUnwrapErrorCode =
  | 'CORRUPTED_DEK'
  | 'WRONG_KEK_VERSION'
  | 'AUTHENTICATION_FAILED';

export class DekUnwrapError extends Error {
  constructor(
    public readonly code: DekUnwrapErrorCode,
    message: string
  ) {
    super(message);
    this.name = 'DekUnwrapError';
  }
}
```

### Functions

```typescript
generateDek(): Promise<Uint8Array>
```
Returns 32 random bytes via CSPRNG.

```typescript
wrapDek(dek: Uint8Array, kek: Uint8Array, fileId?: string): Promise<Uint8Array>
```
Encrypts DEK with KEK using ChaCha20-Poly1305, packs into binary format. If `fileId` is provided, appends HMAC-SHA256(DEK, fileId) for binding. Returns 65 or 97 bytes.

```typescript
unwrapDek(wrappedDek: Uint8Array, kek: Uint8Array, fileId?: string): Uint8Array
```
Parses binary format, decrypts DEK, verifies HMAC if present. Throws `DekUnwrapError` on failure.

```typescript
encryptFileWithDek(
  content: Uint8Array,
  kek: Uint8Array,
  fileId?: string
): Promise<{ encryptedContent: Uint8Array; wrappedDek: Uint8Array }>
```
Generates a DEK, encrypts content, wraps DEK, zeros DEK buffer, returns both.

```typescript
decryptFileWithDek(
  encryptedContent: Uint8Array,
  wrappedDek: Uint8Array,
  kek: Uint8Array,
  fileId?: string
): Uint8Array
```
Unwraps DEK, decrypts content, zeros DEK buffer, returns plaintext. Throws `DekUnwrapError` on failure.

## Error Handling

`unwrapDek` validation order:

1. **Structural validation** (before any crypto):
   - Length must be 65 or 97 → `CORRUPTED_DEK`
   - Version byte must be `0x01` → `WRONG_KEK_VERSION`

2. **ChaCha20-Poly1305 decryption**:
   - Auth tag failure → `AUTHENTICATION_FAILED`

3. **HMAC verification** (if binding present):
   - Requires `fileId` parameter → `CORRUPTED_DEK` if missing
   - Computes HMAC-SHA256(decrypted DEK, fileId), compares to stored HMAC
   - Mismatch → `CORRUPTED_DEK` (zeros DEK before throwing)

HMAC verification happens after decryption because the HMAC is computed over the plaintext DEK.

## Security

- **DEK zeroing**: `dek.fill(0)` after use in `encryptFileWithDek` and `decryptFileWithDek`, and in error paths where DEK was decrypted but HMAC fails.
- **Uint8Array only**: All key material uses `Uint8Array` to enable explicit zeroing.
- **No key material in errors**: Error messages contain only error codes and descriptions.
- **Failure logging**: `console.warn` with error code and timestamp, no key material.

### Key Commitment Documentation

JSDoc on `wrapDek` will document:
1. ChaCha20-Poly1305 does not provide key commitment — an attacker could theoretically find two DEKs that both decrypt to valid plaintexts.
2. Risk is low in Cortex because an attacker must replace both the ciphertext AND the wrapped DEK.
3. HMAC binding (when `fileId` provided) adds defense-in-depth against key substitution.

## Property Tests

File: `packages/encryption/tests/property/test_envelope_encryption.test.ts`

### Property 32 — Envelope encryption round-trip

For random content (0–10KB), random 32-byte KEK, and optional fileId:
- `encryptFileWithDek` then `decryptFileWithDek` returns original content
- Encrypted content differs from plaintext
- Wrapped DEK is 65 bytes (no fileId) or 97 bytes (with fileId)
- Version byte is `0x01`

Validates: 28.1, 28.2, 28.3, 29.2, 29.3

### Property 33 — DEK uniqueness

- 100 calls to `generateDek()` produce 100 unique 32-byte keys
- Two files encrypted with the same KEK produce different wrapped DEKs

Validates: 28.4, 28.5

## Implementation Order

1. 6.12.1 — `generateDek`, `wrapDek`, `unwrapDek`, `DekUnwrapError`
2. 6.12.2 — `encryptFileWithDek`
3. 6.12.3 — `decryptFileWithDek` with error handling and DEK zeroing
4. 6.12.4 — Property 32 (round-trip)
5. 6.12.5 — Property 33 (uniqueness)

Each subtask builds on the previous. Export all public API from `packages/encryption/src/index.ts`.
