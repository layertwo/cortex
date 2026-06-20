import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import type { ReactNode } from 'react';

const state = vi.hoisted(() => ({ status: 'signedOut' as string }));
vi.mock('./SessionContext', () => ({ useSession: () => ({ status: state.status }) }));

import { RequireAuth, RequireVault } from './guards';

function renderAt(path: string, ui: ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>login-screen</div>} />
        <Route path="/vault/unlock" element={<div>unlock-screen</div>} />
        <Route path="/vault/setup" element={<div>setup-screen</div>} />
        <Route path="/secret" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe('guards', () => {
  it('RequireAuth redirects to /login when signedOut', () => {
    state.status = 'signedOut';
    renderAt('/secret', <RequireAuth><div>protected</div></RequireAuth>);
    expect(screen.getByText('login-screen')).toBeInTheDocument();
  });

  it('RequireAuth renders children when unlocked', () => {
    state.status = 'unlocked';
    renderAt('/secret', <RequireAuth><div>protected</div></RequireAuth>);
    expect(screen.getByText('protected')).toBeInTheDocument();
  });

  it('RequireVault redirects locked user to /vault/setup when no vault id', () => {
    state.status = 'signedInVaultLocked';
    localStorage.removeItem('cortex_vault_id');
    renderAt('/secret', <RequireVault><div>vault-content</div></RequireVault>);
    expect(screen.getByText('setup-screen')).toBeInTheDocument();
  });

  it('RequireVault redirects locked user to /vault/unlock when vault id exists', () => {
    state.status = 'signedInVaultLocked';
    localStorage.setItem('cortex_vault_id', 'v1');
    renderAt('/secret', <RequireVault><div>vault-content</div></RequireVault>);
    expect(screen.getByText('unlock-screen')).toBeInTheDocument();
  });
});
