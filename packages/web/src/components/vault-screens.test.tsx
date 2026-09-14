import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { VaultEntry } from '../vault/registry';

const RECOVERY =
  'alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray';

const { session, navigate } = vi.hoisted(() => ({
  session: {
    setupVault: vi.fn(async () => '__RECOVERY__'),
    unlockVault: vi.fn(async () => {}),
    activeVault: { vaultId: 'v1', name: 'Personal' },
    vaults: [] as VaultEntry[],
    logout: vi.fn(async () => {}),
  },
  navigate: vi.fn(),
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => session, WRONG_VAULT_PASSWORD: 'Incorrect vault password' }));
vi.mock('react-router-dom', async (o) => ({
  ...(await o<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import VaultSetup from './VaultSetup';
import VaultUnlock from './VaultUnlock';

beforeEach(() => {
  vi.clearAllMocks();
  session.setupVault.mockResolvedValue(RECOVERY);
  session.vaults = [];
});

describe('vault screens', () => {
  it('VaultSetup shows the recovery phrase and gates navigation on the checkbox', async () => {
    render(
      <MemoryRouter>
        <VaultSetup />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/^vault password/i), 'VaultPw123456!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'VaultPw123456!');
    await userEvent.click(screen.getByRole('button', { name: /create vault/i }));
    expect(session.setupVault).toHaveBeenCalledWith('VaultPw123456!', 'Personal');

    expect(await screen.findByText(/whiskey xray/)).toBeInTheDocument();
    const cont = screen.getByRole('button', { name: /open my vault/i });
    expect(cont).toBeDisabled();
    await userEvent.click(screen.getByLabelText(/i have saved/i));
    expect(cont).toBeEnabled();
    await userEvent.click(cont);
    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('VaultSetup blocks mismatched passwords without calling setupVault', async () => {
    render(
      <MemoryRouter>
        <VaultSetup />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/^vault password/i), 'VaultPw123456!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'different');
    await userEvent.click(screen.getByRole('button', { name: /create vault/i }));
    expect(session.setupVault).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/do not match/i);
  });

  it('VaultSetup lets you name the vault and offers a restore path', async () => {
    render(
      <MemoryRouter>
        <VaultSetup />
      </MemoryRouter>,
    );
    const name = screen.getByLabelText(/vault name/i);
    expect(name).toHaveValue('Personal');
    await userEvent.clear(name);
    await userEvent.type(name, 'Family');
    await userEvent.type(screen.getByLabelText(/^vault password/i), 'VaultPw123456!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'VaultPw123456!');
    expect(screen.getByRole('progressbar', { name: /password strength/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /restore/i })).toHaveAttribute('href', '/vault/recover');
    await userEvent.click(screen.getByRole('button', { name: /create vault/i }));
    expect(session.setupVault).toHaveBeenCalledWith('VaultPw123456!', 'Family');
  });

  it('VaultUnlock surfaces a vault-specific message with a recovery link for a wrong password', async () => {
    session.unlockVault.mockRejectedValueOnce(new Error('Incorrect vault password'));
    const { container } = render(
      <MemoryRouter>
        <VaultUnlock />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/vault password/i), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));
    const banner = await within(container).findByRole('alert');
    expect(banner).toHaveTextContent(/that isn't the vault password for this vault/i);
    expect(within(banner).getByRole('link', { name: /recover with your 24 words/i })).toHaveAttribute(
      'href',
      '/vault/recover',
    );
  });

  it('VaultUnlock shows the plain message for a non-password error', async () => {
    session.unlockVault.mockRejectedValueOnce(new Error('Network error'));
    render(
      <MemoryRouter>
        <VaultUnlock />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/vault password/i), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));
    expect(await screen.findByText('Network error')).toBeInTheDocument();
  });

  it('VaultUnlock with one vault shows a single password field and the recovery link', () => {
    session.vaults = [{ vaultId: 'v1', name: 'Personal' }];
    render(
      <MemoryRouter>
        <VaultUnlock />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('radio')).toBeNull();
    expect(screen.getByLabelText(/vault password/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /forgot your vault password/i })).toHaveAttribute('href', '/vault/recover');
  });

  it('VaultUnlock with several vaults lets you pick one and unlocks that vault', async () => {
    session.vaults = [
      { vaultId: 'v1', name: 'Personal' },
      { vaultId: 'v2', name: 'Family archive' },
    ];
    render(
      <MemoryRouter>
        <VaultUnlock />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole('radio', { name: /family archive/i }));
    await userEvent.type(screen.getByLabelText(/vault password for family archive/i), 'pw');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));
    expect(session.unlockVault).toHaveBeenCalledWith('pw', 'v2');
    expect(navigate).toHaveBeenCalledWith('/');
  });
});
