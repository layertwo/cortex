import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from 'react';
import {
  signUp,
  confirmSignUp,
  signIn,
  signOut,
  resetPassword,
  confirmResetPassword,
  resendSignUpCode,
  updatePassword,
} from 'aws-amplify/auth';
import {
  deriveWrappingKey,
  deriveKeys,
  generateVaultMasterKey,
  generateRecoveryKey,
  wrapVmk,
  unwrapVmk,
  storeKeys,
  clearKeys,
  retrieveKeys,
  bytesToBase64,
  secureZeroize,
} from '@cortex/encryption';
import {
  createVault,
  getVault,
  updateVault,
  updateVaultPassword,
  updateVaultRotation,
  listAllVaults,
  deleteVault as apiDeleteVault,
} from '../api/client';
import type { VaultRecord, VmkEnvelopeRecord } from '../api/client';
import { ConflictError } from '@cortex/client';
import { listAllItems, listItems } from '../api/items';
import { listAllCollections } from '../api/collections';
import { decryptMetadata } from '../items/metadata';
import { rotateItems, rotateCollections, stragglers } from '../items/key-rotation';
import {
  keysFromPhrase,
  identifyVaultForPhrase,
  normalizePhrase,
  PHRASE_ERROR,
} from '../vault/recovery';
import { encryptCollectionName, decryptCollectionName } from '../items/collectionMetadata';
import { resolveAccount, clearAccount } from './account';
import {
  listVaults,
  upsertVault,
  renameInRegistry,
  activeVaultId,
  setActiveVault,
  removeVault,
  migrateLegacyRegistry,
  syncFromServer,
  DEFAULT_VAULT_NAME,
  type VaultEntry,
} from '../vault/registry';

export type SessionStatus = 'loading' | 'signedOut' | 'signedInVaultLocked' | 'unlocked';

// Thrown for a wrong vault password anywhere a password opens a VMK envelope. Exported so
// screens can show a vault-specific message instead of this generic one.
export const WRONG_VAULT_PASSWORD = 'Incorrect vault password';

// Thrown by deleteVault when the vault has no envelope to check the entered password against:
// a password-confirmed delete cannot be confirmed, so it is refused.
export const DELETE_REFUSED = 'This vault has no key to confirm your password against';

// Thrown by unlockVault for a vault that was created but never bootstrapped (no envelopes).
// The caller routes such a vault to setup rather than showing a password error.
export const VAULT_NEEDS_SETUP = 'This vault was created but never set up';

// Thrown by rotateEncryptionKeys when a sweep leaves items on an older dekVersion: RELEASE is
// withheld so the rotation stays IN_PROGRESS and resumable; nothing is stranded.
export const ROTATION_INCOMPLETE = 'Some files still need re-keying; the key rotation is paused and can be resumed';

// Thrown by recoverVault while a key rotation holds the lock: the device cannot know the new VMK.
export const RECOVERY_BLOCKED_BY_ROTATION = 'A key rotation is in progress; finish it before recovering this vault';

// Does the phrase's metadata key open anything already stored in the vault? Used during recovery
// to prove a phrase when the vault has no server-side encrypted name. An empty vault proves
// nothing, and the caller must refuse: a wrong but well-formed phrase would otherwise re-wrap the
// surviving VMK irreversibly.
async function provesOwnership(vaultId: string, currentVmkVersion: number, metadataKey: Uint8Array): Promise<boolean> {
  const [items, collections] = await Promise.all([listItems(vaultId), listAllCollections(vaultId)]);
  const oldKeyItems = items.filter(
    (i) => i.itemType === 'MEDIA' && i.encryptedMetadata && (i.dekVersion ?? 0) <= currentVmkVersion,
  );
  if (oldKeyItems.length) {
    return oldKeyItems.some((i) => {
      try {
        decryptMetadata(i.encryptedMetadata!, metadataKey);
        return true;
      } catch {
        return false;
      }
    });
  }
  const withMetadata = collections.filter((c) => c.encryptedMetadata);
  if (!withMetadata.length) return false; // nothing to prove against
  return withMetadata.some((c) => {
    try {
      decryptCollectionName(c.encryptedMetadata!, metadataKey);
      return true;
    } catch {
      return false;
    }
  });
}

export interface SessionValue {
  status: SessionStatus;
  signUpAccount(email: string, password: string): Promise<void>;
  confirmAccount(email: string, code: string): Promise<void>;
  resendCode(email: string): Promise<void>;
  signInAccount(email: string, password: string): Promise<void>;
  // Cognito *account* password reset (emails a code). NOT the vault password, that
  // opens the VMK envelope client-side and is unrecoverable except via BIP39 recovery.
  requestPasswordReset(email: string): Promise<void>;
  confirmPasswordReset(email: string, code: string, newPassword: string): Promise<void>;
  // Change the signed-in account's Cognito password. The vault password and keys are
  // untouched — no re-encryption, no new recovery phrase.
  changeAccountPassword(currentPassword: string, newPassword: string): Promise<void>;
  logout(): Promise<void>;
  // Creates the vault, bootstraps its first VMK envelope server-side, stores the vault name;
  // returns the BIP39 recovery phrase (which encodes the VMK).
  setupVault(vaultPassword: string, name?: string): Promise<string>;
  // Unwraps the envelope matching the vault's current VMK version; unwrap success is the
  // password check. An unbootstrapped vault (no envelopes) throws VAULT_NEEDS_SETUP.
  unlockVault(vaultPassword: string, vaultId?: string): Promise<void>;
  // Re-wraps every VMK envelope under the new password. No sweep, no new phrase: the VMK (and
  // so the recovery phrase) is unchanged. Throws WRONG_VAULT_PASSWORD on a bad current password.
  changeVaultPassword(currentPassword: string, newPassword: string): Promise<void>;
  // Deliberate, rare action: mint a new VMK, sweep item/collection keys onto it, and RELEASE
  // only when zero stragglers remain. Returns the NEW recovery phrase. Throws
  // WRONG_VAULT_PASSWORD on a bad confirmation password, or ROTATION_INCOMPLETE when a
  // straggler keeps RELEASE withheld (the rotation stays IN_PROGRESS and is resumable).
  rotateEncryptionKeys(currentPassword: string, onProgress?: (done: number, total: number) => void): Promise<string>;
  // True when GetVault returns rotationState !== 'IDLE' on unlock, banner trigger.
  rotationInterrupted: boolean;
  vaults: VaultEntry[];
  activeVault: VaultEntry | null;
  // Increments whenever the active vault changes; the dashboard uses it as a reload key.
  vaultVersion: number;
  switchVault(vaultId: string): Promise<'unlocked' | 'locked'>;
  // Only an unlocked vault can be renamed: the name is encrypted under its metadata key and
  // stored server-side (UpdateVault) before the registry changes. Rejects with the server
  // message, or 'Unlock to rename' when this device holds no keys for it.
  renameVault(vaultId: string, name: string): Promise<void>;
  // Restore access with the 24-word phrase and set a new vault password. The phrase IS the VMK,
  // so it is proven against the vault's encrypted name before any write and is returned
  // unchanged. `target` comes from a recovery kit on a device that has never opened the vault.
  recoverVault(
    phrase: string,
    newPassword: string,
    target?: { vaultId: string; name?: string },
  ): Promise<{ phrase: string; vaultId: string; name: string }>;
  // Confirms the password by unwrapping the current VMK envelope, then calls DeleteVault until
  // the server reports DELETED (or 404 on a later call), then forgets the vault on this device.
  // Rejects with DELETE_REFUSED when the vault has no envelope to check, WRONG_VAULT_PASSWORD
  // on a bad password, and the server message on any DeleteVault failure (a 409 while a
  // rotation lock is live).
  deleteVault(vaultId: string, vaultPassword: string, onProgress?: (deletedItems: number) => void): Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>('loading');
  const [rotationInterrupted, setRotationInterrupted] = useState(false);
  // The registry never persists vaultSalt (with a wrapped envelope it is an offline guessing
  // oracle); this session's copies live in `vaults`, mirrored in a ref so the callbacks below
  // read the latest list without depending on it.
  const vaultsRef = useRef<VaultEntry[]>([]);
  const [vaults, setVaultsState] = useState<VaultEntry[]>([]);
  const [vaultVersion, setVaultVersion] = useState(0);
  const activeVault = vaults.find((v) => v.vaultId === activeVaultId()) ?? null;

  const setVaults = useCallback((list: VaultEntry[]) => {
    vaultsRef.current = list;
    setVaultsState(list);
  }, []);

  // Re-read the registry and re-attach the in-memory salt of each vault, optionally replacing
  // one vault's salt with a freshly learned value.
  const refreshVaults = useCallback(
    (memory?: { vaultId: string; vaultSalt?: Uint8Array }) => {
      setVaults(
        listVaults().map((v) => {
          const prev = vaultsRef.current.find((p) => p.vaultId === v.vaultId);
          const fresh = memory?.vaultId === v.vaultId ? memory : undefined;
          const vaultSalt = fresh?.vaultSalt ?? prev?.vaultSalt;
          return { ...v, ...(vaultSalt ? { vaultSalt } : {}) };
        }),
      );
    },
    [setVaults],
  );

  // Make `vaultId` the active vault and reload anything keyed on it. Callers register the
  // vault before this, but unlockVault reaches here after storeKeys and before setStatus, so
  // a registry/pointer mismatch must self-heal with a default entry rather than throw.
  const activate = useCallback(
    (vaultId: string) => {
      const entry = listVaults().find((v) => v.vaultId === vaultId) ?? { vaultId, name: DEFAULT_VAULT_NAME };
      setActiveVault(vaultId);
      upsertVault({ ...entry, lastOpened: Date.now() });
      refreshVaults();
      setVaultVersion((n) => n + 1);
    },
    [refreshVaults],
  );

  // Update one registry entry on disk and in state. `upsertVault` deliberately drops the
  // memory-only salt; `refreshVaults` re-reads the registry, which now carries the patch, and
  // re-attaches the salt: the patch's value when given, the one already held otherwise.
  const patchEntry = useCallback(
    (vaultId: string, patch: Partial<VaultEntry>) => {
      const onDisk = listVaults().find((v) => v.vaultId === vaultId) ?? { vaultId, name: DEFAULT_VAULT_NAME };
      upsertVault({ ...onDisk, ...patch });
      refreshVaults({ vaultId, vaultSalt: patch.vaultSalt });
    },
    [refreshVaults],
  );

  // The registry is a cache of ListVaults: server fields win, device fields (name, lastOpened)
  // are kept, vaults the server no longer lists are dropped. Offline, the cache stands.
  const syncRegistry = useCallback(async () => {
    try {
      setVaults(syncFromServer(await listAllVaults()));
    } catch (err) {
      console.warn('Vault sync skipped:', err instanceof Error ? err.message : String(err));
      refreshVaults();
    }
  }, [setVaults, refreshVaults]);

  // Account gate: resolve the Cognito subject once (it namespaces the registry), adopt a
  // pre-account registry, merge the server's list, then let the guards route. Status stays
  // 'loading' (guards render nothing) until the subject is known.
  const gate = useCallback(async () => {
    try {
      await resolveAccount();
    } catch {
      setStatus('signedOut');
      return;
    }
    migrateLegacyRegistry();
    await syncRegistry();
    setStatus('signedInVaultLocked');
  }, [syncRegistry]);

  useEffect(() => {
    void gate();
  }, [gate]);

  const signUpAccount = useCallback(async (email: string, password: string) => {
    await signUp({ username: email, password, options: { userAttributes: { email } } });
  }, []);

  const confirmAccount = useCallback(async (email: string, code: string) => {
    await confirmSignUp({ username: email, confirmationCode: code });
  }, []);

  const resendCode = useCallback(async (email: string) => {
    await resendSignUpCode({ username: email });
  }, []);

  const signInAccount = useCallback(
    async (email: string, password: string) => {
      await signIn({ username: email, password });
      await gate();
    },
    [gate],
  );

  const requestPasswordReset = useCallback(async (email: string) => {
    await resetPassword({ username: email });
  }, []);

  const confirmPasswordReset = useCallback(
    async (email: string, code: string, newPassword: string) => {
      await confirmResetPassword({ username: email, confirmationCode: code, newPassword });
    },
    [],
  );

  // Cognito owns the account password; the server never sees it. Because the vault key is
  // derived from the separate vault password, nothing encrypted needs to change.
  const changeAccountPassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<void> => {
      await updatePassword({ oldPassword: currentPassword, newPassword });
    },
    [],
  );

  // Keys and the in-memory salts go; the registry stays so a returning user is never routed to
  // setup. Clearing the account makes the readers return nothing until the next gate resolves
  // a subject.
  const logout = useCallback(async () => {
    for (const v of listVaults()) await clearKeys(v.vaultId);
    await signOut();
    clearAccount();
    setVaults([]);
    setRotationInterrupted(false);
    setStatus('signedOut');
  }, [setVaults]);

  const setupVault = useCallback(
    async (vaultPassword: string, name = DEFAULT_VAULT_NAME): Promise<string> => {
      const displayName = name.trim() || DEFAULT_VAULT_NAME;
      const { vaultId, vaultSalt } = await createVault();
      const vmk = await generateVaultMasterKey();
      const wrappingKey = await deriveWrappingKey(vaultPassword, vaultSalt);
      const wrappedVmk = await wrapVmk(vmk, wrappingKey);
      const keys = deriveKeys(vmk);
      const encryptedName = await encryptCollectionName(displayName, keys.metadataEncryptionKey);
      // Server first: a failure here leaves nothing half-configured on this device. The envelope
      // bootstrap is the security-critical write; the name is written after it and, if that
      // fails, is repaired by a rename.
      await updateVaultPassword(vaultId, 0, [{ vmkVersion: 1, wrappedVmk, createdAt: new Date() }]);
      await updateVault(vaultId, { encryptedName });
      const recovery = generateRecoveryKey(vmk);
      secureZeroize(wrappingKey);
      secureZeroize(vmk); // the derived keys are held; the root secret is not
      await storeKeys(vaultId, keys);
      upsertVault({
        vaultId,
        name: displayName,
        encryptedName: bytesToBase64(encryptedName),
        currentVmkVersion: 1,
        rotationState: 'IDLE',
      });
      refreshVaults({ vaultId, vaultSalt });
      activate(vaultId);
      setStatus('unlocked');
      return recovery;
    },
    [activate, refreshVaults],
  );

  // The password check is the VMK unwrap itself; there is no separate stored secret. An empty
  // envelope list means the vault was created but never bootstrapped, which routes to setup.
  const unlockVault = useCallback(
    async (vaultPassword: string, vaultId = activeVaultId() ?? listVaults()[0]?.vaultId): Promise<void> => {
      if (!vaultId) throw new Error('No vault on this device, set one up first');
      const vault = await getVault(vaultId);
      if (!vault.vmkEnvelopes.length) throw new Error(VAULT_NEEDS_SETUP);
      const envelope = vault.vmkEnvelopes.find((e) => e.vmkVersion === vault.currentVmkVersion);
      if (!envelope) throw new Error(WRONG_VAULT_PASSWORD);
      const wrappingKey = await deriveWrappingKey(vaultPassword, vault.vaultSalt);
      let vmk: Uint8Array;
      try {
        vmk = unwrapVmk(envelope.wrappedVmk, wrappingKey);
      } catch {
        throw new Error(WRONG_VAULT_PASSWORD);
      } finally {
        secureZeroize(wrappingKey);
      }
      const keys = deriveKeys(vmk);
      secureZeroize(vmk); // only the derived keys are needed past this point
      await storeKeys(vaultId, keys);
      const entry = vaultsRef.current.find((v) => v.vaultId === vaultId);
      if (vault.encryptedName && (entry?.name ?? DEFAULT_VAULT_NAME) === DEFAULT_VAULT_NAME) {
        // First unlock on this device of a vault discovered from the server: reveal its name.
        try {
          renameInRegistry(vaultId, decryptCollectionName(vault.encryptedName, keys.metadataEncryptionKey));
        } catch {
          // Undecryptable name (written under other keys): keep the default.
        }
      }
      patchEntry(vaultId, {
        currentVmkVersion: vault.currentVmkVersion,
        rotationState: vault.rotationState,
        ...(vault.encryptedName ? { encryptedName: bytesToBase64(vault.encryptedName) } : {}),
        vaultSalt: vault.vaultSalt,
      });
      setRotationInterrupted(vault.rotationState !== 'IDLE');
      activate(vaultId);
      setStatus('unlocked');
    },
    [activate, patchEntry],
  );

  const switchVault = useCallback(
    async (vaultId: string): Promise<'unlocked' | 'locked'> => {
      // A storage failure in retrieveKeys routes to the unlock dialog, same as "no keys here".
      if (!(await retrieveKeys(vaultId).catch(() => null))) return 'locked';
      activate(vaultId);
      return 'unlocked';
    },
    [activate],
  );

  const renameVault = useCallback(
    async (vaultId: string, name: string): Promise<void> => {
      const trimmed = name.trim();
      if (!trimmed) return;
      const keys = await retrieveKeys(vaultId).catch(() => null);
      if (!keys) throw new Error('Unlock to rename');
      const encryptedName = await encryptCollectionName(trimmed, keys.metadataEncryptionKey);
      await updateVault(vaultId, { encryptedName });
      upsertVault({ vaultId, name: trimmed, encryptedName: bytesToBase64(encryptedName) });
      refreshVaults();
    },
    [refreshVaults],
  );

  // Re-wrap the whole envelope list under the new password. The VMK never changes, so the
  // session's working keys (and the recovery phrase) stay valid. On an envelopeVersion
  // conflict another device changed the list: refetch and retry once against the fresh list.
  const changeVaultPassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<void> => {
      const vaultId = activeVaultId();
      if (!vaultId) throw new Error('No vault on this device');
      const vault = await getVault(vaultId);
      const oldKey = await deriveWrappingKey(currentPassword, vault.vaultSalt);
      const newKey = await deriveWrappingKey(newPassword, vault.vaultSalt);
      const rewrap = async (source: VaultRecord): Promise<VmkEnvelopeRecord[]> => {
        const out: VmkEnvelopeRecord[] = source.vmkEnvelopes.map((e) => ({
          vmkVersion: e.vmkVersion,
          wrappedVmk: e.wrappedVmk,
          createdAt: e.createdAt,
        }));
        if (!out.length) throw new Error(WRONG_VAULT_PASSWORD);
        let opened = false;
        for (const envelope of out) {
          let vmk: Uint8Array;
          try {
            vmk = unwrapVmk(envelope.wrappedVmk, oldKey);
          } catch {
            // A superseded generation (e.g. wrapped before a recovery on another device) that the
            // current password no longer opens: leave it unchanged rather than blocking the
            // change forever. The server only requires the version set to be preserved.
            continue;
          }
          opened = true;
          envelope.wrappedVmk = await wrapVmk(vmk, newKey);
          envelope.createdAt = new Date();
          secureZeroize(vmk);
        }
        if (!opened) throw new Error(WRONG_VAULT_PASSWORD); // no envelope opened ⇒ wrong password
        return out;
      };
      try {
        await updateVaultPassword(vaultId, vault.envelopeVersion, await rewrap(vault));
      } catch (err) {
        if (!(err instanceof ConflictError)) throw err;
        const fresh = await getVault(vaultId);
        await updateVaultPassword(vaultId, fresh.envelopeVersion, await rewrap(fresh));
      } finally {
        secureZeroize(oldKey);
        secureZeroize(newKey);
      }
    },
    [],
  );

  // Deliberate new-VMK rotation: ACQUIRE appends a freshly wrapped VMK (bumping the version),
  // sweep item/collection keys onto it, then RELEASE only with zero stragglers left. The
  // password is re-entered as a confirmation gate (also the wrapping key for the new envelope).
  const rotateEncryptionKeys = useCallback(
    async (currentPassword: string, onProgress?: (done: number, total: number) => void): Promise<string> => {
      const vaultId = activeVaultId();
      if (!vaultId) throw new Error('No vault on this device');
      const vault = await getVault(vaultId);
      const wrappingKey = await deriveWrappingKey(currentPassword, vault.vaultSalt);
      const current = vault.vmkEnvelopes.find((e) => e.vmkVersion === vault.currentVmkVersion);
      let vmkOld: Uint8Array;
      try {
        if (!current) throw new Error(WRONG_VAULT_PASSWORD);
        vmkOld = unwrapVmk(current.wrappedVmk, wrappingKey); // confirmation gate
      } catch {
        secureZeroize(wrappingKey);
        throw new Error(WRONG_VAULT_PASSWORD);
      }
      const keysOld = deriveKeys(vmkOld);
      const vmkNew = await generateVaultMasterKey();
      const wrappedNewVmk = await wrapVmk(vmkNew, wrappingKey);
      secureZeroize(wrappingKey);
      const keysNew = deriveKeys(vmkNew);
      const newVersion = vault.currentVmkVersion + 1;
      await updateVaultRotation({
        vaultId,
        action: 'ACQUIRE',
        expectedState: vault.rotationState,
        expectedEnvelopeVersion: vault.envelopeVersion,
        newVmkVersion: newVersion,
        wrappedNewVmk,
      });
      try {
        const items = await listAllItems(vaultId);
        await rotateItems({
          vaultId,
          items,
          targetDekVersion: newVersion,
          oldKek: keysOld.keyEncryptionKey,
          newKek: keysNew.keyEncryptionKey,
          oldMetadataKey: keysOld.metadataEncryptionKey,
          newMetadataKey: keysNew.metadataEncryptionKey,
          onProgress,
        });
        const collections = await listAllCollections(vaultId);
        await rotateCollections(
          collections,
          keysOld.metadataEncryptionKey,
          keysNew.metadataEncryptionKey,
          vaultId,
          newVersion,
        );

        // RELEASE is withheld unless the re-list shows zero items below the new version — the
        // invariant recovery depends on (IDLE ⇒ one VMK generation referenced). A straggler
        // (an upload that raced ACQUIRE) leaves the rotation IN_PROGRESS and resumable.
        if (stragglers(await listAllItems(vaultId), newVersion).length) throw new Error(ROTATION_INCOMPLETE);

        const plaintext = vault.encryptedName
          ? decryptCollectionName(vault.encryptedName, keysOld.metadataEncryptionKey)
          : listVaults().find((v) => v.vaultId === vaultId)?.name ?? DEFAULT_VAULT_NAME;
        const newEncryptedName = await encryptCollectionName(plaintext, keysNew.metadataEncryptionKey);
        await updateVaultRotation({ vaultId, action: 'RELEASE', expectedState: 'IN_PROGRESS', newEncryptedName });

        // Commit locally, only now that the server has.
        await storeKeys(vaultId, keysNew);
        patchEntry(vaultId, {
          name: plaintext,
          currentVmkVersion: newVersion,
          rotationState: 'IDLE',
          encryptedName: bytesToBase64(newEncryptedName),
          vaultSalt: vault.vaultSalt,
        });
        setRotationInterrupted(false);
        return generateRecoveryKey(vmkNew);
      } catch (err) {
        // ACQUIRE committed and the server bumped currentVmkVersion, but storeKeys was not called,
        // so this client still holds the OLD KEK. Do NOT advance currentVmkVersion in the registry:
        // advertising a version whose KEK the client cannot unwrap would tag uploads with an
        // unreadable dekVersion. The next unlock reads GetVault and adopts the new keys/version.
        patchEntry(vaultId, { rotationState: 'IN_PROGRESS', vaultSalt: vault.vaultSalt });
        setRotationInterrupted(true);
        throw err;
      } finally {
        secureZeroize(vmkOld);
        secureZeroize(vmkNew);
      }
    },
    [patchEntry],
  );

  const recoverVault = useCallback(
    async (
      phrase: string,
      newPassword: string,
      target?: { vaultId: string; name?: string },
    ): Promise<{ phrase: string; vaultId: string; name: string }> => {
      const derived = keysFromPhrase(phrase);
      if (!derived) throw new Error(PHRASE_ERROR);
      const { vmk, keys } = derived;
      try {
        const known = listVaults();
        const vaultId =
          target?.vaultId ??
          identifyVaultForPhrase(
            phrase,
            known.map((v) => ({ vaultId: v.vaultId, encryptedName: v.encryptedName })),
          );
        if (!vaultId) throw new Error(PHRASE_ERROR);
        const vault = await getVault(vaultId);
        if (vault.rotationState !== 'IDLE') throw new Error(RECOVERY_BLOCKED_BY_ROTATION);

        // Prove the phrase before any write. Normally the vault's encrypted name is the proof;
        // when it is absent (a name write that failed, or a legacy row) fall back to an old-key
        // item or a collection. If there is nothing at all to prove against, refuse: a wrong but
        // well-formed phrase must never overwrite the surviving VMK.
        let name = target?.name ?? known.find((v) => v.vaultId === vaultId)?.name ?? DEFAULT_VAULT_NAME;
        if (vault.encryptedName) {
          try {
            name = decryptCollectionName(vault.encryptedName, keys.metadataEncryptionKey);
          } catch {
            throw new Error(PHRASE_ERROR);
          }
        } else if (!(await provesOwnership(vaultId, vault.currentVmkVersion, keys.metadataEncryptionKey))) {
          throw new Error(PHRASE_ERROR);
        }

        const newKey = await deriveWrappingKey(newPassword, vault.vaultSalt);
        const newVersion = vault.currentVmkVersion || 1;
        // The server keeps the VMK version set intact on a re-wrap, so re-wrap the current
        // envelope with the phrase's VMK and pass any superseded generations through unchanged.
        const envelopes: VmkEnvelopeRecord[] = vault.vmkEnvelopes.length
          ? vault.vmkEnvelopes.map((e) => ({
              vmkVersion: e.vmkVersion,
              wrappedVmk: e.wrappedVmk,
              createdAt: e.createdAt,
            }))
          : [{ vmkVersion: 1, wrappedVmk: new Uint8Array(0), createdAt: new Date() }];
        const current = envelopes.find((e) => e.vmkVersion === newVersion) ?? envelopes[0];
        current.vmkVersion = newVersion;
        current.wrappedVmk = await wrapVmk(vmk, newKey);
        current.createdAt = new Date();
        secureZeroize(newKey);
        await updateVaultPassword(vaultId, vault.envelopeVersion, envelopes);
        await storeKeys(vaultId, keys);
        upsertVault({
          vaultId,
          name,
          ...(vault.encryptedName ? { encryptedName: bytesToBase64(vault.encryptedName) } : {}),
          currentVmkVersion: newVersion,
          rotationState: 'IDLE',
        });
        refreshVaults({ vaultId, vaultSalt: vault.vaultSalt });
        activate(vaultId);
        setStatus('unlocked');
        return { phrase: normalizePhrase(phrase), vaultId, name };
      } finally {
        secureZeroize(vmk);
      }
    },
    [activate, refreshVaults],
  );

  // Password-confirmed, fail-closed delete. Confirmation is unwrapping the current VMK envelope;
  // DeleteVault is a resumable sweep, so it is repeated until the server says DELETED. A 404 on
  // a later call means the vault is already gone. Nothing here retries: the dialog offers Retry
  // and the server sweep is idempotent.
  const deleteVault = useCallback(
    async (vaultId: string, vaultPassword: string, onProgress?: (deletedItems: number) => void): Promise<void> => {
      const vault = await getVault(vaultId);
      const envelope = vault.vmkEnvelopes.find((e) => e.vmkVersion === vault.currentVmkVersion);
      if (!envelope) throw new Error(DELETE_REFUSED);
      const wrappingKey = await deriveWrappingKey(vaultPassword, vault.vaultSalt);
      let vmk: Uint8Array;
      try {
        vmk = unwrapVmk(envelope.wrappedVmk, wrappingKey);
      } catch {
        throw new Error(WRONG_VAULT_PASSWORD);
      } finally {
        secureZeroize(wrappingKey);
      }
      secureZeroize(vmk); // the unwrap is the only use

      let removed = 0;
      for (let calls = 1; ; calls++) {
        const out = await apiDeleteVault(vaultId).catch((err: unknown) => {
          if (calls > 1 && (err as { name?: string }).name === 'ResourceNotFoundError') return null;
          throw err;
        });
        if (!out) break;
        removed += out.deletedItems;
        onProgress?.(removed);
        if (out.deletionState === 'DELETED') break;
      }

      await clearKeys(vaultId);
      localStorage.removeItem(`cortex_welcome_done:${vaultId}`); // components/WelcomeCard.tsx key
      const wasActive = activeVaultId() === vaultId;
      removeVault(vaultId);
      if (wasActive) {
        // RequireVault then routes to /vault/unlock (a vault remains) or /vault/setup (none).
        const next = listVaults().sort((a, b) => (b.lastOpened ?? 0) - (a.lastOpened ?? 0))[0];
        if (next) setActiveVault(next.vaultId);
        setStatus('signedInVaultLocked');
      }
      // No re-sync (same decision as setupVault and recoverVault): ListVaults is eventually
      // consistent, so a read racing this delete could still include the just-deleted vault and
      // resurrect it. refreshVaults re-reads the registry this removeVault call already updated.
      refreshVaults();
    },
    [refreshVaults],
  );

  const value: SessionValue = {
    status,
    signUpAccount,
    confirmAccount,
    resendCode,
    signInAccount,
    requestPasswordReset,
    confirmPasswordReset,
    changeAccountPassword,
    logout,
    setupVault,
    unlockVault,
    changeVaultPassword,
    rotateEncryptionKeys,
    rotationInterrupted,
    vaults,
    activeVault,
    vaultVersion,
    switchVault,
    renameVault,
    recoverVault,
    deleteVault,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
