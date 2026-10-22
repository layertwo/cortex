import { Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useSession } from './SessionContext';
import SignIn from '../components/SignIn';
import { listVaults } from '../vault/registry';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useSession();
  if (status === 'loading') return null;
  if (status === 'signedOut') return <SignIn />;
  return <>{children}</>;
}

export function RequireVault({ children }: { children: ReactNode }) {
  const { status } = useSession();
  if (status === 'loading') return null;
  if (status === 'signedOut') return <SignIn />;
  if (status !== 'unlocked') {
    // A vault created but never bootstrapped (currentVmkVersion 0, no envelopes) has nothing to
    // unlock: route it to setup rather than a password prompt that cannot succeed.
    const hasUsableVault = listVaults().some((v) => (v.currentVmkVersion ?? 0) > 0);
    return <Navigate to={hasUsableVault ? '/vault/unlock' : '/vault/setup'} replace />;
  }
  return <>{children}</>;
}
