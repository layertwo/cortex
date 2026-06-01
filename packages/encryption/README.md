# @cortex/encryption

Zero-knowledge encryption library for the Cortex productivity suite. All encryption and decryption happens client-side.

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
  deriveVaultMasterKey, deriveKeys,
  bindSaltHmac, resetSaltHmac, getStoredSaltHmac, verifySaltHmac,
  SaltIntegrityError,
} from '@cortex/encryption';

const masterKey = await deriveVaultMasterKey(password, salt);
const { saltHmacKey } = deriveKeys(masterKey);

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
