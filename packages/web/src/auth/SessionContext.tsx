import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { signUp, confirmSignUp, signIn, signOut, getCurrentUser } from 'aws-amplify/auth';

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
    await signOut();
    setStatus('signedOut');
  }, []);

  // Replaced in Task 5 — throw so they are never silently no-ops.
  const setupVault = useCallback(async (_vaultPassword: string): Promise<string> => {
    throw new Error('setupVault not implemented yet (Task 5)');
  }, []);
  const unlockVault = useCallback(async (_vaultPassword: string) => {
    throw new Error('unlockVault not implemented yet (Task 5)');
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
