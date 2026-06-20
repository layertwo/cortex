import { Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useSession } from './SessionContext';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useSession();
  if (status === 'loading') return null;
  if (status === 'signedOut') return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function RequireVault({ children }: { children: ReactNode }) {
  const { status } = useSession();
  if (status === 'loading') return null;
  if (status === 'signedOut') return <Navigate to="/login" replace />;
  if (status !== 'unlocked') {
    const hasVault = !!localStorage.getItem('cortex_vault_id');
    return <Navigate to={hasVault ? '/vault/unlock' : '/vault/setup'} replace />;
  }
  return <>{children}</>;
}
