import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const state = vi.hoisted(() => ({ status: 'signedOut' as string }));
vi.mock('./auth/SessionContext', async (o) => ({
  ...(await o<typeof import('./auth/SessionContext')>()),
  SessionProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useSession: () => ({ status: state.status }),
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
    expect(screen.getByRole('heading', { name: /log in/i })).toBeInTheDocument();
  });

  it('shows the Dashboard at / when unlocked', () => {
    state.status = 'unlocked';
    window.history.pushState({}, '', '/');
    render(<App />);
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });
});
