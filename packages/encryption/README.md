# @cortex/encryption

Zero-knowledge encryption library for the Cortex productivity suite. All encryption and decryption happens client-side.

## Vault Salt Integrity

The vault salt is fetched from the server every time keys are derived on a new device or after the cached bundle expires. To detect a malicious server swapping the salt — which would cause the client to derive a totally different vault master key and present a corrupted vault as legitimate — the client binds the salt to the vault master key locally:

1. **First unlock on a device.** After `deriveVaultMasterKey` and `deriveKeys` succeed, the caller invokes `bindSaltHmac({ vaultId, saltHmacKey, salt })`. The library computes `HMAC-SHA256(saltHmacKey, salt)` and stores it next to the encrypted key bundle in IndexedDB.

2. **Subsequent unlocks.** The caller fetches the salt from the server, derives `saltHmacKey`, then calls `verifySaltHmac(saltHmacKey, salt, storedMac)`. The comparison is constant-time. If it fails, **abort key derivation** and show the user a tampering warning.

3. **Reset (after a tampering false-positive or legitimate salt change during account recovery).** Force re-entry of both the account password and the vault password. Re-derive keys. Call `resetSaltHmac(...)` to overwrite the stored HMAC.

The salt HMAC itself is non-secret integrity material — the cryptographic guarantee comes from the attacker not knowing the vault master key. We persist it in plaintext alongside the encrypted bundle.

### Recovery procedure for HMAC failure

If `verifySaltHmac` returns false, surface this UX:

> **Vault tampering detected.** The salt your server returned does not match what this device expected. This usually means one of:
> - Someone has tampered with your vault on the server.
> - You completed account recovery and the server-side salt was legitimately reset.
>
> To continue, re-enter both your account password and vault password. If you did not just recover your account, contact support before proceeding.

Only on explicit user acknowledgment plus a successful re-derivation should the client call `resetSaltHmac`.
