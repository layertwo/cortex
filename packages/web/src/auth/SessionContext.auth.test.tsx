import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// vi.hoisted so `amplify` is initialized before the hoisted vi.mock factory runs.
const amplify = vi.hoisted(() => ({
  signUp: vi.fn(async () => ({ isSignUpComplete: false })),
  confirmSignUp: vi.fn(async () => ({ isSignUpComplete: true })),
  signIn: vi.fn(async () => ({ isSignedIn: true })),
  signOut: vi.fn(async () => {}),
  getCurrentUser: vi.fn(async () => {
    throw new Error('no user');
  }),
}));
vi.mock('aws-amplify/auth', () => amplify);

import { SessionProvider, useSession } from './SessionContext';

function Probe() {
  const s = useSession();
  return (
    <div>
      <span data-testid="status">{s.status}</span>
      <button onClick={() => s.signInAccount('a@b.com', 'pw')}>signin</button>
      <button onClick={() => s.logout()}>logout</button>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('SessionContext auth', () => {
  it('starts signedOut when no current user', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    expect(await screen.findByTestId('status')).toHaveTextContent('signedOut');
  });

  it('signInAccount → signedInVaultLocked, logout → signedOut', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('signin');
    await act(async () => {
      await userEvent.click(screen.getByText('signin'));
    });
    expect(amplify.signIn).toHaveBeenCalledWith({ username: 'a@b.com', password: 'pw' });
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    await act(async () => {
      await userEvent.click(screen.getByText('logout'));
    });
    expect(screen.getByTestId('status')).toHaveTextContent('signedOut');
  });
});
