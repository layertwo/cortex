import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { signUp, confirmSignUp, signIn, signOut, getCurrentUser } from 'aws-amplify/auth';
import {
  deriveVaultMasterKey,
  deriveKeys,
  generateRecoveryKey,
  storeKeys,
  clearKeys,
} from '@cortex/encryption';
import { createVault, getVaultSalt } from '../api/client';
import { createVerifier, checkVerifier, saveVerifier, loadVerifier } from '../vault/verifier';

const VAULT_ID_KEY = 'cortex_vault_id';

export type SessionStatus = 'loading' | 'signedOut' | 'signedInVaultLocked' | 'unlocked';

export interface SessionValue {
  status: SessionStatus;
  signUpAccount(email: string, password: string): Promise<void>;
  confirmAccount(email: string, code: string): Promise<void>;
  signInAccount(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
  // Implemented in Task 5:
  setupVault(vaultPassword: string): Promise<string>; // returns the BIP39 recovery phrase
  unlockVault(vaultPassword: string): Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionStatus>('loading');

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
    setStatus('unlocked');
  }, []);

  const value: SessionValue = {
    status,
    signUpAccount,
    confirmAccount,
    signInAccount,
    logout,
    setupVault,
    unlockVault,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
