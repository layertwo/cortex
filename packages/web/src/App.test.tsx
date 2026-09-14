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
  }),
}));

import App from './App';

beforeEach(() => {
  localStorage.clear();
});

describe('App routing', () => {
  it('shows Login at /login when signed out', () => {
    state.status = 'signedOut';
    window.history.pushState({}, '', '/login');
    render(<App />);
    expect(screen.getByRole('heading', { name: /welcome back/i })).toBeInTheDocument();
    expect(document.querySelector('[data-astryx-theme="cortex"]')).not.toBeNull();
  });

  it('shows the Dashboard at / when unlocked', () => {
    state.status = 'unlocked';
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByRole('heading', { name: /all files/i })).toBeInTheDocument();
  });

  it('shows the landing hero at / when signed out', () => {
    state.status = 'signedOut';
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/a vault for your memories/i);
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
  });
});
