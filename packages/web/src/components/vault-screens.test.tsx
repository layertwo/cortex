import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const RECOVERY =
  'alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray';

const { session, navigate } = vi.hoisted(() => ({
  session: {
    setupVault: vi.fn(async () => '__RECOVERY__'),
    unlockVault: vi.fn(async () => {}),
  },
  navigate: vi.fn(),
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => session }));
vi.mock('react-router-dom', async (o) => ({
  ...(await o<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import VaultSetup from './VaultSetup';
import VaultUnlock from './VaultUnlock';

beforeEach(() => {
  vi.clearAllMocks();
  session.setupVault.mockResolvedValue(RECOVERY);
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
    expect(session.setupVault).toHaveBeenCalledWith('VaultPw123456!');

    expect(await screen.findByText(/whiskey xray/)).toBeInTheDocument();
    const cont = screen.getByRole('button', { name: /continue/i });
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

  it('VaultUnlock surfaces an incorrect-password error', async () => {
    session.unlockVault.mockRejectedValueOnce(new Error('Incorrect vault password'));
    render(
      <MemoryRouter>
        <VaultUnlock />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/vault password/i), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /unlock/i }));
    expect(await screen.findByText('Incorrect vault password')).toBeInTheDocument();
  });
});
