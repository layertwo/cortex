# @cortex/encryption

Zero-knowledge encryption library for the Cortex productivity suite. All encryption and decryption happens client-side.

> Clean break: the VMK model replaces the previous verifier / salt-derived master key outright. Nothing is deployed yet, so no data migration is needed.

## Vault Salt Integrity

The vault salt is fetched from the server every time keys are derived. To detect a malicious server swapping the salt — which would cause the client to derive a totally different vault master key and present a corrupted vault as legitimate — the client binds the salt to the vault master key locally via an HMAC.

### Storage design

The salt HMAC is stored in a **separate, plaintext, non-expiring per-vault record** in IndexedDB (or localStorage as fallback). It is **not** inside the encrypted key bundle. This is intentional:

- The HMAC is non-secret integrity material — the security guarantee comes from the attacker not knowing the vault master key, not from secrecy of the HMAC.
- The record survives key-bundle expiry (the default 24-hour max age) because it has no expiry of its own.
- The record survives logout (clearing the key bundle does not remove the HMAC record).
- The record persists for the lifetime of the device or until explicitly cleared via `clearSaltHmacRecord`.

### Error codes on `SaltIntegrityError`

| Code | When |
|------|------|
| `NO_PRIOR_BINDING` | Reserved — no record found (future use) |
| `ALREADY_BOUND` | `bindSaltHmac` called when a record already exists for the vault |
| `TAMPERED` | Reserved for future verify-and-throw callers |
| `STORAGE_FAILURE` | The underlying store threw during write |

### Call sequence (web layer's responsibility)

```typescript
import {
  deriveWrappingKey, unwrapVmk, deriveKeys,
  bindSaltHmac, resetSaltHmac, getStoredSaltHmac, verifySaltHmac,
  SaltIntegrityError,
} from '@cortex/encryption';

const wrappingKey = await deriveWrappingKey(password, salt);
const vmk = unwrapVmk(envelope.wrappedVmk, wrappingKey);
const { saltHmacKey } = deriveKeys(vmk);

const stored = await getStoredSaltHmac(vaultId);
if (stored === null) {
  // First unlock on this device — establish the baseline.
  await bindSaltHmac({ vaultId, saltHmacKey, salt });
} else if (!verifySaltHmac(saltHmacKey, salt, stored)) {
  // Tampering detected. Show warning, require re-auth, then resetSaltHmac.
  throw new TamperingDetected();
}
```

Steps:

1. **First unlock on a device.** `getStoredSaltHmac` returns `null`. Call `bindSaltHmac({ vaultId, saltHmacKey, salt })`. The library computes `HMAC-SHA256(saltHmacKey, salt)` and writes it to the standalone record store.

2. **Subsequent unlocks.** `getStoredSaltHmac` returns the stored HMAC. Call `verifySaltHmac(saltHmacKey, salt, stored)`. The comparison is constant-time. If it returns `false`, abort key derivation and show the user a tampering warning.

3. **Reset (after a tampering false-positive or legitimate salt change during account recovery).** Force re-entry of both the account password and the vault password. Re-derive keys. Call `resetSaltHmac({ vaultId, saltHmacKey, salt })` to overwrite the stored HMAC. `resetSaltHmac` always succeeds — it is the explicit overwrite path.

Note: `bindSaltHmac` throws `SaltIntegrityError('ALREADY_BOUND')` if a record already exists. Use `resetSaltHmac` when you need to overwrite an existing binding after re-authentication.

### Recovery procedure for HMAC failure

If `verifySaltHmac` returns false, surface this UX:

> **Vault tampering detected.** The salt your server returned does not match what this device expected. This usually means one of:
> - Someone has tampered with your vault on the server.
> - You completed account recovery and the server-side salt was legitimately reset.
>
> To continue, re-enter both your account password and vault password. If you did not just recover your account, contact support before proceeding.

Only on explicit user acknowledgment plus a successful re-derivation should the client call `resetSaltHmac`.

## DEK wrapping-format versioning

Every wrapped DEK begins with a version byte. `CURRENT_DEK_VERSION` is used for new
wraps; `SUPPORTED_DEK_VERSIONS` lists everything the client can read; and
`DEPRECATED_DEK_VERSIONS` lists versions that are refused. Deploy a new version as
SUPPORTED for a soak period before promoting it to CURRENT, so a rollback never
orphans files.

`getWrappedDekVersion(wrappedDek)` reads the version without decrypting;
`isDekVersionDeprecated(version)` reports refusal; and `unwrapDek` throws
`DekUnwrapError` with code `WRONG_KEK_VERSION` for both unsupported and deprecated
versions (the deprecated message points at migration).

## Key zeroization on logout

`secureZeroize(buffer)` overwrites a key buffer in place — zeros, then cryptographically
random bytes. `zeroizeKeys(keys)` does the same for every present buffer in a derived-key
set. `clearAllKeys()` removes all key material from IndexedDB, localStorage, and
sessionStorage.

These are **best-effort**. JavaScript cannot guarantee a value is gone from memory: the
garbage collector may have copied it, and a buffer handed to Web Crypto or a third-party
library may persist in that library's own memory. What this library does to shrink the
window: raw `Uint8Array` (never strings) holds key material, the two-pass overwrite
replaces it, and the at-rest device key is a `crypto.subtle` non-exportable `CryptoKey`.

The web app keeps no long-lived in-memory key cache. `retrieveKeys` decrypts the encrypted
bundle from IndexedDB per operation, and `SessionContext` zeroizes each transient master
key immediately after deriving the working keys (`secureZeroize` / `zeroizeKeys`). The
inactivity timeout is enforced by the bundle's own expiry (`DEFAULT_CONFIG.timeoutMinutes`,
30 minutes): once it lapses `retrieveKeys` returns `null` and the vault reads as locked.
Because nothing persistent lives in memory, there is no separate `beforeunload` hook to
register.
