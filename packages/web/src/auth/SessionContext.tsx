import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import {
  signUp,
  confirmSignUp,
  signIn,
  signOut,
  getCurrentUser,
  resetPassword,
  confirmResetPassword,
} from 'aws-amplify/auth';
import {
  deriveVaultMasterKey,
  deriveKeys,
  generateRecoveryKey,
  storeKeys,
  clearKeys,
} from '@cortex/encryption';
import { createVault, getVaultSalt, getVault, updateVaultRotation } from '../api/client';
import { listAllItems } from '../api/items';
import { listCollections } from '../api/collections';
import { saveBridge, clearBridge } from '../vault/rotationBridge';
import { rotateItems, rotateCollections } from '../items/key-rotation';
import { createVerifier, checkVerifier, saveVerifier, loadVerifier } from '../vault/verifier';

const VAULT_ID_KEY = 'cortex_vault_id';

export type SessionStatus = 'loading' | 'signedOut' | 'signedInVaultLocked' | 'unlocked';

export interface SessionValue {
  status: SessionStatus;
  signUpAccount(email: string, password: string): Promise<void>;
  confirmAccount(email: string, code: string): Promise<void>;
  signInAccount(email: string, password: string): Promise<void>;
  // Cognito *account* password reset (emails a code). NOT the vault password — that
  // derives the KEK client-side and is unrecoverable except via BIP39 recovery.
  requestPasswordReset(email: string): Promise<void>;
  confirmPasswordReset(email: string, code: string, newPassword: string): Promise<void>;
  logout(): Promise<void>;
  // Implemented in Task 5:
  setupVault(vaultPassword: string): Promise<string>; // returns the BIP39 recovery phrase
  unlockVault(vaultPassword: string): Promise<void>;
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
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>('loading');
  const [rotationInterrupted, setRotationInterrupted] = useState(false);

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
    const vaultId = localStorage.getItem(VAULT_ID_KEY);
    if (vaultId) await clearKeys(vaultId);
    await signOut();
    setStatus('signedOut');
  }, []);

  const setupVault = useCallback(async (vaultPassword: string): Promise<string> => {
    const { vaultId, vaultSalt } = await createVault();
    localStorage.setItem(VAULT_ID_KEY, vaultId);
    const master = await deriveVaultMasterKey(vaultPassword, vaultSalt);
    const keys = deriveKeys(master);
    saveVerifier(vaultId, await createVerifier(keys.metadataEncryptionKey));
    const recovery = generateRecoveryKey(master);
    await storeKeys(vaultId, keys);
    setStatus('unlocked');
    return recovery;
  }, []);

  const unlockVault = useCallback(async (vaultPassword: string): Promise<void> => {
    const vaultId = localStorage.getItem(VAULT_ID_KEY);
    if (!vaultId) throw new Error('No vault on this device — set one up first');
    const salt = await getVaultSalt(vaultId);
    const master = await deriveVaultMasterKey(vaultPassword, salt);
    const keys = deriveKeys(master);
    const verifier = loadVerifier(vaultId);
    // Missing verifier is a hard failure: unlocking without it would silently accept a
    // wrong password and store keys that decrypt nothing.
    if (!verifier) throw new Error('Vault verifier missing on this device — re-run setup');
    if (!checkVerifier(verifier, keys.metadataEncryptionKey)) {
      throw new Error('Incorrect vault password');
    }
    await storeKeys(vaultId, keys);
    // Detect an interrupted rotation so the Dashboard can show a resume banner.
    try {
      const vault = await getVault(vaultId);
      setRotationInterrupted(vault.rotationState !== 'IDLE');
    } catch {
      // Non-fatal: rotation banner is advisory, not blocking.
    }
    setStatus('unlocked');
  }, []);

  const changeVaultPassword = useCallback(
    async (
      currentPassword: string,
      newPassword: string,
      onProgress?: (done: number, total: number) => void,
    ): Promise<string> => {
      const vaultId = localStorage.getItem(VAULT_ID_KEY);
      if (!vaultId) throw new Error('No vault on this device');

      // 1. Verify current password client-side (fast-fail, no network).
      const vault = await getVault(vaultId);
      const masterOld = await deriveVaultMasterKey(currentPassword, vault.vaultSalt);
      const keysOld = deriveKeys(masterOld);
      const verifier = loadVerifier(vaultId);
      if (!verifier || !checkVerifier(verifier, keysOld.metadataEncryptionKey)) {
        throw new Error('Incorrect vault password');
      }

      // 2. Derive new keys.
      const masterNew = await deriveVaultMasterKey(newPassword, vault.vaultSalt);
      const keysNew = deriveKeys(masterNew);
      const targetDekVersion = vault.kekVersion + 1;

      // 3. Write bridge BEFORE acquiring the lock — bridge must exist before any
      //    server state changes so resume always works.
      await saveBridge(
        vaultId,
        keysOld.keyEncryptionKey,
        keysOld.metadataEncryptionKey,
        keysNew.keyEncryptionKey,
      );

      // 4. Acquire rotation lock (conditional — fails if another tab holds it).
      //    Use the vault's actual rotationState rather than hardcoding 'IDLE': when
      //    resuming after a crashed mid-sweep attempt (rotationState === 'IN_PROGRESS'),
      //    this lets the backend's `rotation_state = :expected` clause match immediately
      //    instead of requiring the 7-day staleness window to elapse.
      await updateVaultRotation({
        vaultId,
        action: 'ACQUIRE',
        expectedState: vault.rotationState,
      });

      try {
        // 5. Sweep items.
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

        // 6. Re-encrypt collections.
        const cols = await listCollections(vaultId);
        await rotateCollections(
          cols,
          keysOld.metadataEncryptionKey,
          keysNew.metadataEncryptionKey,
          vaultId,
        );

        // 7. Recompute verifier (don't persist yet — server RELEASE is the commit point).
        const newVerifierStr = await createVerifier(keysNew.metadataEncryptionKey);
        const newVerifierBytes = new TextEncoder().encode(newVerifierStr);

        // 8. Generate the new recovery phrase (caller MUST show this before continuing).
        const newPhrase = generateRecoveryKey(masterNew);

        // 9. Release lock: write new kekVersion + verifier. This is the durability commit
        //    point — only after this succeeds do we update local state to match the new
        //    keys, so a transient failure here can't leave the local verifier pointing at
        //    the new password while the server and in-memory keys are still on the old one.
        await updateVaultRotation({
          vaultId,
          action: 'RELEASE',
          expectedState: 'IN_PROGRESS',
          kekVersion: targetDekVersion,
          newVerifier: newVerifierBytes,
        });

        // 10. Now safe to commit locally: persist verifier, delete bridge, update
        //     in-memory keys, clear interrupted flag.
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

  const value: SessionValue = {
    status,
    signUpAccount,
    confirmAccount,
    signInAccount,
    requestPasswordReset,
    confirmPasswordReset,
    logout,
    setupVault,
    unlockVault,
    changeVaultPassword,
    rotationInterrupted,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
