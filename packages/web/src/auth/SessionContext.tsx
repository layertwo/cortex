import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import {
  signUp,
  confirmSignUp,
  signIn,
  signOut,
  getCurrentUser,
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
  type DerivedKeys,
} from '@cortex/encryption';
import { createVault, getVaultSalt, getVault, updateVaultRotation } from '../api/client';
import type { VaultRecord } from '../api/client';
import { listAllItems, listItems } from '../api/items';
import { listCollections } from '../api/collections';
import { saveBridge, clearBridge } from '../vault/rotationBridge';
import { rotateItems, rotateCollections } from '../items/key-rotation';
import { createVerifier, checkVerifier, saveVerifier, loadVerifier } from '../vault/verifier';
import { keysFromPhrase, identifyVaultForPhrase, PHRASE_ERROR } from '../vault/recovery';
import { decryptMetadata } from '../items/metadata';
import { decryptCollectionName } from '../items/collectionMetadata';
import {
  listVaults,
  upsertVault,
  activeVaultId,
  setActiveVault,
  DEFAULT_VAULT_NAME,
  type VaultEntry,
} from '../vault/registry';

export type SessionStatus = 'loading' | 'signedOut' | 'signedInVaultLocked' | 'unlocked';

// Thrown by unlockVault for a wrong vault password. Exported so screens can show a
// vault-specific message instead of this generic one.
export const WRONG_VAULT_PASSWORD = 'Incorrect vault password';

export interface SessionValue {
  status: SessionStatus;
  signUpAccount(email: string, password: string): Promise<void>;
  confirmAccount(email: string, code: string): Promise<void>;
  resendCode(email: string): Promise<void>;
  signInAccount(email: string, password: string): Promise<void>;
  // Cognito *account* password reset (emails a code). NOT the vault password — that
  // derives the KEK client-side and is unrecoverable except via BIP39 recovery.
  requestPasswordReset(email: string): Promise<void>;
  confirmPasswordReset(email: string, code: string, newPassword: string): Promise<void>;
  logout(): Promise<void>;
  // Implemented in Task 5:
  setupVault(vaultPassword: string, name?: string): Promise<string>; // returns the BIP39 recovery phrase
  unlockVault(vaultPassword: string, vaultId?: string): Promise<void>;
  // Returns the new BIP39 recovery phrase after a successful rotation sweep.
  // Throws with 'Incorrect vault password' if currentPassword fails the verifier.
  // Throws with 'ROTATION_CONFLICT' if another tab holds the lock.
  changeVaultPassword(
    currentPassword: string,
    newPassword: string,
    onProgress?: (done: number, total: number) => void,
  ): Promise<string>;
  // True when GetVault returns rotationState !== 'IDLE' on unlock — banner trigger.
  rotationInterrupted: boolean;
  vaults: VaultEntry[];
  activeVault: VaultEntry | null;
  // Increments whenever the active vault changes; the dashboard uses it as a reload key.
  vaultVersion: number;
  switchVault(vaultId: string): Promise<'unlocked' | 'locked'>;
  renameVault(vaultId: string, name: string): void;
  // Restore access with the 24-word phrase and set a new vault password. `target` comes
  // from a recovery kit on a device that has never opened the vault; otherwise the vault is
  // identified from this device's verifiers. Resolves with the NEW phrase.
  recoverVault(
    phrase: string,
    newPassword: string,
    onProgress?: (done: number, total: number) => void,
    target?: { vaultId: string; name?: string },
  ): Promise<{ phrase: string; vaultId: string; name: string }>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>('loading');
  const [rotationInterrupted, setRotationInterrupted] = useState(false);
  const [vaults, setVaults] = useState<VaultEntry[]>(() => listVaults());
  const [vaultVersion, setVaultVersion] = useState(0);
  const activeVault = vaults.find((v) => v.vaultId === activeVaultId()) ?? null;

  // Make `vaultId` the active vault and reload anything keyed on it. Callers register the
  // vault before this, but unlockVault reaches here after storeKeys and before setStatus, so
  // a registry/pointer mismatch must self-heal with a default entry rather than throw.
  const activate = useCallback((vaultId: string) => {
    const entry = listVaults().find((v) => v.vaultId === vaultId) ?? { vaultId, name: DEFAULT_VAULT_NAME };
    setActiveVault(vaultId);
    upsertVault({ ...entry, lastOpened: Date.now() });
    setVaults(listVaults());
    setVaultVersion((n) => n + 1);
  }, []);

  useEffect(() => {
    getCurrentUser()
      .then(() => setStatus('signedInVaultLocked'))
      .catch(() => setStatus('signedOut'));
  }, []);

  const signUpAccount = useCallback(async (email: string, password: string) => {
    await signUp({ username: email, password, options: { userAttributes: { email } } });
  }, []);

  const confirmAccount = useCallback(async (email: string, code: string) => {
    await confirmSignUp({ username: email, confirmationCode: code });
  }, []);

  const resendCode = useCallback(async (email: string) => {
    await resendSignUpCode({ username: email });
  }, []);

  const signInAccount = useCallback(async (email: string, password: string) => {
    await signIn({ username: email, password });
    setStatus('signedInVaultLocked');
  }, []);

  const requestPasswordReset = useCallback(async (email: string) => {
    await resetPassword({ username: email });
  }, []);

  const confirmPasswordReset = useCallback(
    async (email: string, code: string, newPassword: string) => {
      await confirmResetPassword({ username: email, confirmationCode: code, newPassword });
    },
    [],
  );

  const logout = useCallback(async () => {
    for (const v of listVaults()) await clearKeys(v.vaultId);
    await signOut();
    setStatus('signedOut');
  }, []);

  const setupVault = useCallback(
    async (vaultPassword: string, name = DEFAULT_VAULT_NAME): Promise<string> => {
      const { vaultId, vaultSalt } = await createVault();
      const master = await deriveVaultMasterKey(vaultPassword, vaultSalt);
      const keys = deriveKeys(master);
      saveVerifier(vaultId, await createVerifier(keys.metadataEncryptionKey));
      const recovery = generateRecoveryKey(master);
      await storeKeys(vaultId, keys);
      upsertVault({ vaultId, name: name.trim() || DEFAULT_VAULT_NAME });
      activate(vaultId);
      setStatus('unlocked');
      return recovery;
    },
    [activate],
  );

  const unlockVault = useCallback(
    async (vaultPassword: string, vaultId = activeVaultId() ?? listVaults()[0]?.vaultId): Promise<void> => {
      if (!vaultId) throw new Error('No vault on this device — set one up first');
      const salt = await getVaultSalt(vaultId);
      const master = await deriveVaultMasterKey(vaultPassword, salt);
      const keys = deriveKeys(master);
      const verifier = loadVerifier(vaultId);
      // Missing verifier is a hard failure: unlocking without it would silently accept a
      // wrong password and store keys that decrypt nothing.
      if (!verifier) throw new Error('Vault verifier missing on this device — re-run setup');
      if (!checkVerifier(verifier, keys.metadataEncryptionKey)) {
        throw new Error(WRONG_VAULT_PASSWORD);
      }
      await storeKeys(vaultId, keys);
      activate(vaultId);
      // Detect an interrupted rotation so the Dashboard can show a resume banner.
      try {
        const vault = await getVault(vaultId);
        setRotationInterrupted(vault.rotationState !== 'IDLE');
      } catch {
        // Non-fatal: rotation banner is advisory, not blocking.
      }
      setStatus('unlocked');
    },
    [activate],
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

  const renameVault = useCallback((vaultId: string, name: string) => {
    if (!name.trim()) return;
    upsertVault({ vaultId, name: name.trim() });
    setVaults(listVaults());
  }, []);

  // Steps shared by change-password and phrase recovery: derive new keys from the new
  // password, re-wrap every item, re-encrypt collections, commit on RELEASE, then update
  // local state. Returns the new recovery phrase.
  const rotateVault = useCallback(
    async (
      vaultId: string,
      vault: VaultRecord,
      keysOld: DerivedKeys,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
    ): Promise<string> => {
      // Derive new keys.
      const masterNew = await deriveVaultMasterKey(newPassword, vault.vaultSalt);
      const keysNew = deriveKeys(masterNew);
      const targetDekVersion = vault.kekVersion + 1;

      // Write bridge BEFORE acquiring the lock — bridge must exist before any
      // server state changes so resume always works.
      await saveBridge(
        vaultId,
        keysOld.keyEncryptionKey,
        keysOld.metadataEncryptionKey,
        keysNew.keyEncryptionKey,
      );

      // Acquire rotation lock (conditional — fails if another tab holds it).
      // Use the vault's actual rotationState rather than hardcoding 'IDLE': when
      // resuming after a crashed mid-sweep attempt (rotationState === 'IN_PROGRESS'),
      // this lets the backend's `rotation_state = :expected` clause match immediately
      // instead of requiring the 7-day staleness window to elapse.
      await updateVaultRotation({
        vaultId,
        action: 'ACQUIRE',
        expectedState: vault.rotationState,
      });

      try {
        // Sweep items.
        const items = await listAllItems(vaultId);
        await rotateItems({
          vaultId,
          items,
          targetDekVersion,
          oldKek: keysOld.keyEncryptionKey,
          newKek: keysNew.keyEncryptionKey,
          oldMetadataKey: keysOld.metadataEncryptionKey,
          newMetadataKey: keysNew.metadataEncryptionKey,
          onProgress,
        });

        // Re-encrypt collections.
        const cols = await listCollections(vaultId);
        await rotateCollections(
          cols,
          keysOld.metadataEncryptionKey,
          keysNew.metadataEncryptionKey,
          vaultId,
        );

        // Recompute verifier (don't persist yet — server RELEASE is the commit point).
        const newVerifierStr = await createVerifier(keysNew.metadataEncryptionKey);
        const newVerifierBytes = new TextEncoder().encode(newVerifierStr);

        // Generate the new recovery phrase (caller MUST show this before continuing).
        const newPhrase = generateRecoveryKey(masterNew);

        // Release lock: write new kekVersion + verifier. This is the durability commit
        // point — only after this succeeds do we update local state to match the new
        // keys, so a transient failure here can't leave the local verifier pointing at
        // the new password while the server and in-memory keys are still on the old one.
        await updateVaultRotation({
          vaultId,
          action: 'RELEASE',
          expectedState: 'IN_PROGRESS',
          kekVersion: targetDekVersion,
          newVerifier: newVerifierBytes,
        });

        // Now safe to commit locally: persist verifier, delete bridge, update
        // in-memory keys, clear interrupted flag.
        saveVerifier(vaultId, newVerifierStr);
        clearBridge(vaultId);
        await storeKeys(vaultId, keysNew);
        setRotationInterrupted(false);

        return newPhrase;
      } catch (err) {
        // On any failure, set PAUSED so the banner shows on next unlock.
        try {
          await updateVaultRotation({
            vaultId,
            action: 'RELEASE',
            expectedState: 'IN_PROGRESS',
          });
        } catch {
          // Best-effort state update — don't mask the original error.
        }
        throw err;
      }
    },
    [],
  );

  const changeVaultPassword = useCallback(
    async (
      currentPassword: string,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
    ): Promise<string> => {
      const vaultId = activeVaultId();
      if (!vaultId) throw new Error('No vault on this device');

      // Verify current password client-side (fast-fail, no network).
      const vault = await getVault(vaultId);
      const masterOld = await deriveVaultMasterKey(currentPassword, vault.vaultSalt);
      const keysOld = deriveKeys(masterOld);
      const verifier = loadVerifier(vaultId);
      if (!verifier || !checkVerifier(verifier, keysOld.metadataEncryptionKey)) {
        throw new Error(WRONG_VAULT_PASSWORD);
      }
      return rotateVault(vaultId, vault, keysOld, newPassword, onProgress);
    },
    [rotateVault],
  );

  const recoverVault = useCallback(
    async (
      phrase: string,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
      target?: { vaultId: string; name?: string },
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
        // candidates — an item a prior, partially-completed sweep already advanced is under
        // the NEW key and would wrongly fail a correct phrase on retry. Collections carry no
        // version and are always swept, so they're only the fallback when there are no
        // old-key items to check instead. This runs before any write, so a wrong phrase is
        // caught here rather than mid-sweep. A vault with no readable candidates at all is
        // accepted unverified: the sweep then has nothing to re-encrypt, so a wrong phrase
        // can't corrupt anything.
        const [items, cols] = await Promise.all([listItems(vaultId), listCollections(vaultId)]);
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
      const newPhrase = await rotateVault(vaultId, vault, derived.keys, newPassword, onProgress);
      const name = known.find((v) => v.vaultId === vaultId)?.name ?? target?.name ?? DEFAULT_VAULT_NAME;
      upsertVault({ vaultId, name });
      activate(vaultId);
      setStatus('unlocked');
      return { phrase: newPhrase, vaultId, name };
    },
    [rotateVault, activate],
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
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
