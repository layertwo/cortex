import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const state = vi.hoisted(() => ({ status: 'signedOut' as string }));
vi.mock('./auth/SessionContext', async (o) => ({
  ...(await o<typeof import('./auth/SessionContext')>()),
  SessionProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useSession: () => ({
    status: state.status,
    vaults: [{ vaultId: 'v1', name: 'Personal' }],
    activeVault: { vaultId: 'v1', name: 'Personal' },
    vaultVersion: 0,
    switchVault: vi.fn(),
    unlockVault: vi.fn(),
    signIn: vi.fn(),
  }),
}));

import App from './App';

beforeEach(() => {
  localStorage.clear();
});

describe('App routing', () => {
  it('shows the dashboard at / when unlocked', () => {
    state.status = 'unlocked';
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByRole('heading', { name: /all files/i })).toBeInTheDocument();
    expect(document.querySelector('[data-astryx-theme="cortex"]')).not.toBeNull();
  });

  it('offers OIDC sign-in at / when signed out', () => {
    state.status = 'signedOut';
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByRole('heading', { name: /sign in to cortex/i })).toBeInTheDocument();
  });

  it('keeps the public share route reachable without a session', () => {
    state.status = 'signedOut';
    window.history.pushState({}, '', '/s/share-1');
    render(<App />);
    expect(screen.queryByRole('heading', { name: /sign in to cortex/i })).not.toBeInTheDocument();
  });
});
