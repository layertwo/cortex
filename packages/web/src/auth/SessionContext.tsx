import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from 'react';
import {
  signUp,
  confirmSignUp,
  signIn,
  signOut,
  resetPassword,
  confirmResetPassword,
  resendSignUpCode,
} from 'aws-amplify/auth';
import {
  deriveVaultMasterKey,
  deriveKeys,
  generateRecoveryKey,
  storeKeys,
  clearKeys,
  retrieveKeys,
  stringToBytes,
  bytesToString,
  bytesToBase64,
  base64ToBytes,
  type DerivedKeys,
} from '@cortex/encryption';
import {
  createVault,
  getVaultSalt,
  getVault,
  updateVault,
  updateVaultRotation,
  listAllVaults,
  deleteVault as apiDeleteVault,
} from '../api/client';
import type { VaultRecord } from '../api/client';
import type { RotationState } from '@cortex/client';
import { listAllItems, listItems } from '../api/items';
import { listAllCollections } from '../api/collections';
import { rotateItems, rotateCollections } from '../items/key-rotation';
import { createVerifier, checkVerifier, saveVerifier, loadVerifier } from '../vault/verifier';
import { keysFromPhrase, identifyVaultForPhrase, PHRASE_ERROR } from '../vault/recovery';
import { decryptMetadata } from '../items/metadata';
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

// Thrown by unlockVault for a wrong vault password. Exported so screens can show a
// vault-specific message instead of this generic one.
export const WRONG_VAULT_PASSWORD = 'Incorrect vault password';

// Thrown by deleteVault when neither the server nor this device has a verifier: a
// password-confirmed delete cannot be confirmed, so it is refused (spec §7).
const DELETE_REFUSED = 'Unlock this vault once on a device that knows its password';

// Rotation outcomes the screens turn into copy. REKEYED_ERROR: "Start over" was refused because
// an earlier attempt already re-wrapped files under its new password. CANCELLED_ERROR: the user
// dismissed the resume dialog; the rotation is paused, not failed.
export const REKEYED_ERROR =
  "Some files were already re-keyed with the new password you started with; you need that password to finish.";
export const CANCELLED_ERROR = 'Password change cancelled';
// Exact server text of the ABANDON 409 that means "files were re-keyed" (rotation-abandon spec §3.2).
const REKEYED_SERVER_MESSAGE = 'Some files were already re-keyed; finish the password change with the new password';

// What the resume dialog decided when the typed password does not open the staged pair.
export type StagedDecision = { action: 'finish'; password: string } | { action: 'startOver' } | { action: 'cancel' };
export type OnStagedMismatch = (startedAt: number | null, error?: string) => Promise<StagedDecision>;

function sameBytes(a: Uint8Array | null, b: Uint8Array): boolean {
  return a !== null && a.length === b.length && a.every((x, i) => x === b[i]);
}

// Wherever a password is checked, the server verifier (held in memory after sync) is
// authoritative; the local blob is the offline fallback on a device that unlocked once.
function verifierFor(entry: Pick<VaultEntry, 'vaultId' | 'verifier'>): string | null {
  return entry.verifier ?? loadVerifier(entry.vaultId);
}

export interface SessionValue {
  status: SessionStatus;
  signUpAccount(email: string, password: string): Promise<void>;
  confirmAccount(email: string, code: string): Promise<void>;
  resendCode(email: string): Promise<void>;
  signInAccount(email: string, password: string): Promise<void>;
  // Cognito *account* password reset (emails a code). NOT the vault password, that
  // derives the KEK client-side and is unrecoverable except via BIP39 recovery.
  requestPasswordReset(email: string): Promise<void>;
  confirmPasswordReset(email: string, code: string, newPassword: string): Promise<void>;
  logout(): Promise<void>;
  // Creates the vault, then stores its encrypted name and verifier server-side; returns
  // the BIP39 recovery phrase.
  setupVault(vaultPassword: string, name?: string): Promise<string>;
  // Checks the server verifier (local blob as the offline fallback); a legacy vault with no
  // server verifier uploads its local one so it can be unlocked elsewhere.
  unlockVault(vaultPassword: string, vaultId?: string): Promise<void>;
  // Returns the new BIP39 recovery phrase after a successful rotation sweep.
  // Throws WRONG_VAULT_PASSWORD if currentPassword fails the verifier; REKEYED_ERROR or the
  // server message when "Start over" is refused; CANCELLED_ERROR when the resume dialog is
  // dismissed (the rotation is then PAUSED on the server). `onStagedMismatch` is asked when the
  // server returns an earlier attempt's staged pair that newPassword does not open.
  changeVaultPassword(
    currentPassword: string,
    newPassword: string,
    onProgress?: (done: number, total: number) => void,
    onStagedMismatch?: OnStagedMismatch,
  ): Promise<string>;
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
  // Restore access with the 24-word phrase and set a new vault password. `target` comes
  // from a recovery kit on a device that has never opened the vault; otherwise the vault is
  // identified from this device's verifiers. Shares the rotation path with changeVaultPassword,
  // including the staged-pair check. Resolves with the NEW phrase.
  recoverVault(
    phrase: string,
    newPassword: string,
    onProgress?: (done: number, total: number) => void,
    target?: { vaultId: string; name?: string },
    onStagedMismatch?: OnStagedMismatch,
  ): Promise<{ phrase: string; vaultId: string; name: string }>;
  // Checks vaultPassword against the vault's verifier, calls DeleteVault until the server
  // reports DELETED (or 404 on a later call), then forgets the vault on this device.
  // Rejects with 'Unlock this vault once on a device that knows its password' when no
  // verifier exists anywhere, with WRONG_VAULT_PASSWORD on a bad password, and with the
  // server message on any DeleteVault failure (a 409 while a rotation lock is live).
  deleteVault(vaultId: string, vaultPassword: string, onProgress?: (deletedItems: number) => void): Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>('loading');
  const [rotationInterrupted, setRotationInterrupted] = useState(false);
  // The registry never persists vaultSalt/verifier (salt + verifier is an offline guessing
  // oracle); this session's copies live in `vaults`, mirrored in a ref so the callbacks
  // below read the latest list without depending on it.
  const vaultsRef = useRef<VaultEntry[]>([]);
  const [vaults, setVaultsState] = useState<VaultEntry[]>([]);
  const [vaultVersion, setVaultVersion] = useState(0);
  const activeVault = vaults.find((v) => v.vaultId === activeVaultId()) ?? null;

  const setVaults = useCallback((list: VaultEntry[]) => {
    vaultsRef.current = list;
    setVaultsState(list);
  }, []);

  // Re-read the registry and re-attach the in-memory salt/verifier of each vault, optionally
  // replacing one vault's pair with freshly learned values.
  const refreshVaults = useCallback(
    (memory?: { vaultId: string; vaultSalt?: Uint8Array; verifier?: string }) => {
      setVaults(
        listVaults().map((v) => {
          const prev = vaultsRef.current.find((p) => p.vaultId === v.vaultId);
          const fresh = memory?.vaultId === v.vaultId ? memory : undefined;
          const vaultSalt = fresh?.vaultSalt ?? prev?.vaultSalt;
          const verifier = fresh?.verifier ?? prev?.verifier;
          return { ...v, ...(vaultSalt ? { vaultSalt } : {}), ...(verifier ? { verifier } : {}) };
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
  // memory-only fields (`vaultSalt`, `verifier`); `refreshVaults` re-reads the registry, which now
  // carries the patch, and re-attaches them: the patch's values when given, the ones already held
  // otherwise (so a `rotationState: 'PAUSED'` patch keeps the salt and verifier in state).
  const patchEntry = useCallback(
    (vaultId: string, patch: Partial<VaultEntry>) => {
      const onDisk = listVaults().find((v) => v.vaultId === vaultId) ?? { vaultId, name: DEFAULT_VAULT_NAME };
      upsertVault({ ...onDisk, ...patch });
      refreshVaults({ vaultId, vaultSalt: patch.vaultSalt, verifier: patch.verifier });
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

  // Keys and the in-memory salts/verifiers go; the registry stays so a returning user is
  // never routed to setup. Clearing the account makes the readers return nothing until the
  // next gate resolves a subject.
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
      const master = await deriveVaultMasterKey(vaultPassword, vaultSalt);
      const keys = deriveKeys(master);
      const verifierString = await createVerifier(keys.metadataEncryptionKey);
      const encryptedName = await encryptCollectionName(displayName, keys.metadataEncryptionKey);
      // Server first: a failure here leaves nothing half-configured on this device. The vault
      // row exists either way; the next gate lists it under the default name and rename repairs it.
      // No re-sync after setup (accepted deviation from spec §5, see the plan's Global Constraints):
      // ListVaults is eventually consistent and a read that missed this row would drop the vault.
      await updateVault(vaultId, { encryptedName, verifier: stringToBytes(verifierString) });
      saveVerifier(vaultId, verifierString);
      const recovery = generateRecoveryKey(master);
      await storeKeys(vaultId, keys);
      upsertVault({
        vaultId,
        name: displayName,
        encryptedName: bytesToBase64(encryptedName),
        kekVersion: 1,
        rotationState: 'IDLE',
      });
      refreshVaults({ vaultId, vaultSalt, verifier: verifierString });
      activate(vaultId);
      setStatus('unlocked');
      return recovery;
    },
    [activate, refreshVaults],
  );

  const unlockVault = useCallback(
    async (vaultPassword: string, vaultId = activeVaultId() ?? listVaults()[0]?.vaultId): Promise<void> => {
      if (!vaultId) throw new Error('No vault on this device, set one up first');
      const entry = vaultsRef.current.find((v) => v.vaultId === vaultId);
      const salt = entry?.vaultSalt ?? (await getVaultSalt(vaultId));
      const master = await deriveVaultMasterKey(vaultPassword, salt);
      const keys = deriveKeys(master);
      const verifier = verifierFor({ vaultId, verifier: entry?.verifier });
      // Missing verifier is a hard failure: unlocking without it would silently accept a
      // wrong password and store keys that decrypt nothing.
      if (!verifier) throw new Error('Vault verifier missing on this device, re-run setup');
      if (!checkVerifier(verifier, keys.metadataEncryptionKey)) {
        throw new Error(WRONG_VAULT_PASSWORD);
      }
      saveVerifier(vaultId, verifier);
      await storeKeys(vaultId, keys);
      if (entry?.encryptedName && entry.name === DEFAULT_VAULT_NAME) {
        // First unlock on this device of a vault discovered from the server: reveal its name.
        try {
          renameInRegistry(vaultId, decryptCollectionName(base64ToBytes(entry.encryptedName), keys.metadataEncryptionKey));
        } catch {
          // Undecryptable name (written under other keys): keep the default.
        }
      }
      refreshVaults({ vaultId, vaultSalt: salt, verifier });
      activate(vaultId);
      // Detect an interrupted rotation so the Dashboard can show a resume banner, and check
      // whether the server truly has no verifier (not just "this session never learned one",
      // which entry?.verifier cannot distinguish) before uploading this device's local blob.
      try {
        const vault = await getVault(vaultId);
        setRotationInterrupted(vault.rotationState !== 'IDLE');
        if (vault.verifier == null) {
          // Legacy vault (set up before verifiers were stored server-side): upload the local one
          // so the vault becomes unlockable on other devices. Advisory, so offline still unlocks.
          try {
            await updateVault(vaultId, { verifier: stringToBytes(verifier) });
          } catch {
            // Retried on the next unlock.
          }
        }
      } catch {
        // Non-fatal: a failed read skips both the banner and the upload, the correct default.
      }
      setStatus('unlocked');
    },
    [activate, refreshVaults],
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

  // Steps shared by change-password and phrase recovery (spec §6). The server stages the new salt
  // and verifier on ACQUIRE and returns the pair that is actually staged; when an earlier
  // attempt's pair comes back, its keys must be used (or the pair abandoned) so the sweep never
  // mixes two new-key generations. Returns the new recovery phrase.
  const rotateVault = useCallback(
    async (
      vaultId: string,
      vault: VaultRecord,
      keysOld: DerivedKeys,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
      onStagedMismatch?: OnStagedMismatch,
    ): Promise<string> => {
      const targetDekVersion = vault.kekVersion + 1;

      // 1. This attempt's new keys and verifier.
      const newSalt = crypto.getRandomValues(new Uint8Array(16));
      const masterNew = await deriveVaultMasterKey(newPassword, newSalt);
      const keysNew = deriveKeys(masterNew);
      const verifierNew = await createVerifier(keysNew.metadataEncryptionKey);

      // What the sweep will use: this attempt's pair unless the server hands back a staged one.
      let inUse: { keys: DerivedKeys; master: Uint8Array; salt: Uint8Array; verifier: string } = {
        keys: keysNew,
        master: masterNew,
        salt: newSalt,
        verifier: verifierNew,
      };

      // 2. ACQUIRE with the vault's current state (IDLE, or PAUSED/IN_PROGRESS on resume); after a
      // successful ABANDON, with the state ABANDON returned.
      let expectedState: RotationState = vault.rotationState;
      let acquired = false; // any failure after this point pauses the rotation
      let lockHeld = false; // PAUSE is only sent while this attempt holds the lock

      try {
        acquire: for (;;) {
          const staged = await updateVaultRotation({
            vaultId,
            action: 'ACQUIRE',
            expectedState,
            newVaultSalt: newSalt,
            newVerifier: stringToBytes(verifierNew),
          });
          acquired = true;
          lockHeld = true;
          if (!staged.pendingVaultSalt || !staged.pendingVerifier) {
            // Re-keying under keys derived from a salt the server did not record would strand
            // every other device, so stop before touching anything.
            throw new Error('Server did not stage the new vault salt');
          }

          // 3. Returned-pair check.
          if (sameBytes(staged.pendingVaultSalt, newSalt)) break; // this attempt owns the pair

          // An earlier attempt's pair is staged: use its keys if a password opens them, else ask.
          const stagedSalt = staged.pendingVaultSalt;
          const stagedVerifier = bytesToString(staged.pendingVerifier);
          let password = newPassword;
          let error: string | undefined;
          for (;;) {
            const master = await deriveVaultMasterKey(password, stagedSalt);
            const keys = deriveKeys(master);
            if (checkVerifier(stagedVerifier, keys.metadataEncryptionKey)) {
              inUse = { keys, master, salt: stagedSalt, verifier: stagedVerifier };
              break acquire;
            }
            const decision: StagedDecision = onStagedMismatch
              ? await onStagedMismatch(vault.rotationLockedAt, error)
              : { action: 'cancel' };
            if (decision.action === 'cancel') throw new Error(CANCELLED_ERROR);
            if (decision.action === 'startOver') break;
            password = decision.password;
            error = WRONG_VAULT_PASSWORD;
          }

          // Start over: ABANDON requires PAUSED, so PAUSE first. The server refuses ABANDON when
          // anything was already re-keyed under the staged pair; ABANDON is never retried.
          await updateVaultRotation({ vaultId, action: 'PAUSE', expectedState: 'IN_PROGRESS' });
          lockHeld = false;
          expectedState = 'PAUSED'; // this attempt's own commit; ABANDON below may still overwrite it
          let abandoned: { rotationState: RotationState };
          try {
            abandoned = await updateVaultRotation({ vaultId, action: 'ABANDON', expectedState: 'PAUSED' });
          } catch (err) {
            throw err instanceof Error && err.message === REKEYED_SERVER_MESSAGE ? new Error(REKEYED_ERROR) : err;
          }
          expectedState = abandoned.rotationState;
        }

        // 4. Sweep items, then collections, with the keys in use.
        const items = await listAllItems(vaultId);
        await rotateItems({
          vaultId,
          items,
          targetDekVersion,
          oldKek: keysOld.keyEncryptionKey,
          newKek: inUse.keys.keyEncryptionKey,
          oldMetadataKey: keysOld.metadataEncryptionKey,
          newMetadataKey: inUse.keys.metadataEncryptionKey,
          onProgress,
        });
        const cols = await listAllCollections(vaultId);
        await rotateCollections(
          cols,
          keysOld.metadataEncryptionKey,
          inUse.keys.metadataEncryptionKey,
          vaultId,
          targetDekVersion,
        );

        // 5. The vault name travels to RELEASE re-encrypted under the keys in use. The server
        // blob (old keys) is preferred; an unreadable or absent blob falls back to the registry name.
        const readServerName = (): string | null => {
          try {
            return vault.encryptedName ? decryptCollectionName(vault.encryptedName, keysOld.metadataEncryptionKey) : null;
          } catch {
            return null;
          }
        };
        const plaintext =
          readServerName() ?? listVaults().find((v) => v.vaultId === vaultId)?.name ?? DEFAULT_VAULT_NAME;
        const newEncryptedName = await encryptCollectionName(plaintext, inUse.keys.metadataEncryptionKey);
        const newPhrase = generateRecoveryKey(inUse.master);

        // RELEASE promotes the staged pair and writes the version and name: the durability
        // commit point. No newVerifier, no newVaultSalt (the server rejects both while staged).
        await updateVaultRotation({
          vaultId,
          action: 'RELEASE',
          expectedState: 'IN_PROGRESS',
          kekVersion: targetDekVersion,
          newEncryptedName,
        });
        lockHeld = false;

        // 6. Commit locally, only now that the server has.
        saveVerifier(vaultId, inUse.verifier);
        await storeKeys(vaultId, inUse.keys);
        patchEntry(vaultId, {
          name: plaintext,
          kekVersion: targetDekVersion,
          rotationState: 'IDLE',
          encryptedName: bytesToBase64(newEncryptedName),
          vaultSalt: inUse.salt,
          verifier: inUse.verifier,
        });
        setRotationInterrupted(false);
        return newPhrase;
      } catch (err) {
        // 7. Anything after ACQUIRE (a sweep error, a cancelled dialog, a refused ABANDON) leaves
        // the rotation PAUSED so the banner shows and a resume can pick the staged pair up — unless
        // this attempt's own Start over already ran ABANDON to completion (expectedState is then
        // 'IDLE') and the failure is the re-ACQUIRE itself: the server is genuinely IDLE there, so
        // the registry must say so too, not PAUSED.
        if (!acquired) throw err;
        if (lockHeld) {
          try {
            await updateVaultRotation({ vaultId, action: 'PAUSE', expectedState: 'IN_PROGRESS' });
          } catch {
            // Best effort: never mask the original error.
          }
          expectedState = 'PAUSED';
        }
        patchEntry(vaultId, { rotationState: expectedState === 'IDLE' ? 'IDLE' : 'PAUSED' });
        setRotationInterrupted(expectedState !== 'IDLE');
        throw err;
      }
    },
    [patchEntry],
  );

  const changeVaultPassword = useCallback(
    async (
      currentPassword: string,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
      onStagedMismatch?: OnStagedMismatch,
    ): Promise<string> => {
      const vaultId = activeVaultId();
      if (!vaultId) throw new Error('No vault on this device');

      // Verify the current password client-side (fast-fail). The server verifier is
      // authoritative; the in-memory copy and then the local blob are the offline fallbacks.
      const vault = await getVault(vaultId);
      const masterOld = await deriveVaultMasterKey(currentPassword, vault.vaultSalt);
      const keysOld = deriveKeys(masterOld);
      const verifier =
        (vault.verifier && bytesToString(vault.verifier)) ||
        vaults.find((v) => v.vaultId === vaultId)?.verifier ||
        loadVerifier(vaultId);
      if (!verifier || !checkVerifier(verifier, keysOld.metadataEncryptionKey)) {
        throw new Error(WRONG_VAULT_PASSWORD);
      }
      // A PAUSED or IN_PROGRESS vault resumes through the same path: ACQUIRE with its real state.
      return rotateVault(vaultId, vault, keysOld, newPassword, onProgress, onStagedMismatch);
    },
    [rotateVault, vaults],
  );

  const recoverVault = useCallback(
    async (
      phrase: string,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
      target?: { vaultId: string; name?: string },
      onStagedMismatch?: OnStagedMismatch,
    ) => {
      const derived = keysFromPhrase(phrase);
      if (!derived) throw new Error(PHRASE_ERROR);
      const known = listVaults();
      const vaultId = target?.vaultId ?? identifyVaultForPhrase(phrase, known.map((v) => v.vaultId));
      if (!vaultId) throw new Error(PHRASE_ERROR);
      const vault = await getVault(vaultId);
      if (!loadVerifier(vaultId)) {
        // New device: nothing local to check against, so prove the keys against whatever the
        // rotation sweep below is actually going to touch. Items still under the OLD key (the
        // same predicate rotateItems uses: dekVersion <= vault.kekVersion) are the real proof
        // candidates, an item a prior, partially-completed sweep already advanced is under
        // the NEW key and would wrongly fail a correct phrase on retry. Collections carry no
        // version and are always swept, so they're only the fallback when there are no
        // old-key items to check instead. This runs before any write, so a wrong phrase is
        // caught here rather than mid-sweep. A vault with no readable candidates at all is
        // accepted unverified: the sweep then has nothing to re-encrypt, so a wrong phrase
        // can't corrupt anything.
        const [items, cols] = await Promise.all([listItems(vaultId), listAllCollections(vaultId)]);
        const oldKeyItems = items.filter(
          (i) => i.itemType === 'MEDIA' && i.encryptedMetadata && (i.dekVersion ?? 0) <= vault.kekVersion,
        );
        const candidates: { encryptedMetadata?: Uint8Array }[] = oldKeyItems.length
          ? oldKeyItems
          : cols.filter((c) => c.encryptedMetadata);
        const decrypt = oldKeyItems.length ? decryptMetadata : decryptCollectionName;
        const opens = (blob: Uint8Array) => {
          try {
            decrypt(blob, derived.keys.metadataEncryptionKey);
            return true;
          } catch {
            return false;
          }
        };
        if (candidates.length && !candidates.some((c) => opens(c.encryptedMetadata!))) throw new Error(PHRASE_ERROR);
      }
      // Steps 1 to 7 of the rotation, including the staged-pair dialog: a recovering user usually
      // cannot know an earlier attempt's new password, so "Start over" is the expected route.
      const newPhrase = await rotateVault(vaultId, vault, derived.keys, newPassword, onProgress, onStagedMismatch);
      // rotateVault stored the server name; a recovery-kit name only fills in for a vault that
      // never had one.
      const rotated = listVaults().find((v) => v.vaultId === vaultId);
      const name =
        rotated && rotated.name !== DEFAULT_VAULT_NAME ? rotated.name : target?.name ?? rotated?.name ?? DEFAULT_VAULT_NAME;
      if (name !== rotated?.name) patchEntry(vaultId, { name });
      activate(vaultId);
      setStatus('unlocked');
      // No re-sync here (same decision as setupVault, see Global Constraints): rotateVault's own
      // commit already left the registry row correct (kekVersion, rotationState, name,
      // encryptedName); an eventually-consistent ListVaults read could overwrite it with the
      // pre-rotation fields. The next gate syncs.
      return { phrase: newPhrase, vaultId, name };
    },
    [rotateVault, activate, patchEntry],
  );

  // Password-confirmed, fail-closed delete (spec §7). The check runs before the first call;
  // DeleteVault is a resumable sweep, so it is repeated until the server says DELETED. A 404
  // on a later call means the vault is already gone. Nothing here retries: the dialog offers
  // Retry and the server sweep is idempotent.
  const deleteVault = useCallback(
    async (vaultId: string, vaultPassword: string, onProgress?: (deletedItems: number) => void): Promise<void> => {
      const entry = vaults.find((v) => v.vaultId === vaultId);
      const verifier = entry ? verifierFor(entry) : loadVerifier(vaultId);
      if (!verifier) throw new Error(DELETE_REFUSED);
      const salt = entry?.vaultSalt ?? (await getVaultSalt(vaultId));
      const keys = deriveKeys(await deriveVaultMasterKey(vaultPassword, salt));
      if (!checkVerifier(verifier, keys.metadataEncryptionKey)) throw new Error(WRONG_VAULT_PASSWORD);

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
      localStorage.removeItem(`cortex_vault_verifier_${vaultId}`); // vault/verifier.ts STORAGE_PREFIX
      localStorage.removeItem(`cortex_welcome_done:${vaultId}`); // components/WelcomeCard.tsx key
      const wasActive = activeVaultId() === vaultId;
      removeVault(vaultId);
      if (wasActive) {
        // RequireVault then routes to /vault/unlock (a vault remains) or /vault/setup (none).
        const next = listVaults().sort((a, b) => (b.lastOpened ?? 0) - (a.lastOpened ?? 0))[0];
        if (next) setActiveVault(next.vaultId);
        setStatus('signedInVaultLocked');
      }
      // No re-sync (same decision as setupVault and recoverVault, see Global Constraints):
      // ListVaults is eventually consistent, so a read racing this delete could still include
      // the just-deleted vault and resurrect it. refreshVaults re-reads the registry this
      // removeVault call already updated. The next gate syncs.
      refreshVaults();
    },
    [vaults, refreshVaults],
  );

  const value: SessionValue = {
    status,
    signUpAccount,
    confirmAccount,
    resendCode,
    signInAccount,
    requestPasswordReset,
    confirmPasswordReset,
    logout,
    setupVault,
    unlockVault,
    changeVaultPassword,
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
