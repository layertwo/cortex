import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { SessionValue } from '../auth/SessionContext';

const WORDS = Array.from({ length: 24 }, (_, i) => `w${i + 1}`);
const NEW_PHRASE = Array.from({ length: 24 }, (_, i) => `n${i + 1}`).join(' ');

const { session, navigate, recovery } = vi.hoisted(() => ({
  session: {
    vaults: [{ vaultId: 'v1', name: 'Personal' }],
    recoverVault: vi.fn<SessionValue['recoverVault']>(async () => ({ phrase: '', vaultId: 'v1', name: 'Personal' })),
  },
  navigate: vi.fn(),
  recovery: { identifyVaultForPhrase: vi.fn((): string | null => 'v1') },
}));
vi.mock('../auth/SessionContext', () => ({
  useSession: () => session,
  CANCELLED_ERROR: 'Password change cancelled',
}));
vi.mock('react-router-dom', async (o) => ({
  ...(await o<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));
vi.mock('../vault/recovery', async (o) => ({
  ...(await o<typeof import('../vault/recovery')>()),
  identifyVaultForPhrase: recovery.identifyVaultForPhrase,
}));

import RecoverVault from './RecoverVault';

beforeEach(() => {
  recovery.identifyVaultForPhrase.mockReturnValue('v1');
  session.recoverVault.mockResolvedValue({ phrase: NEW_PHRASE, vaultId: 'v1', name: 'Personal' });
});

function pastePhrase() {
  fireEvent.paste(screen.getByLabelText('Word 1'), { clipboardData: { getData: () => WORDS.join(' ') } });
}

describe('RecoverVault', () => {
  it('walks phrase → new password → sweep → new phrase → open vault', async () => {
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    expect(screen.getByText(/it opens personal/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^new vault password/i), 'NewVaultPw123!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewVaultPw123!');
    await userEvent.click(screen.getByRole('button', { name: /set password and re-secure/i }));
    await waitFor(() =>
      expect(session.recoverVault).toHaveBeenCalledWith(
        WORDS.join(' '),
        'NewVaultPw123!',
        expect.any(Function),
        { vaultId: 'v1', name: undefined },
        expect.any(Function),
      ),
    );
    expect(await screen.findByText('n1 n2 n3')).toBeInTheDocument();
    const open = screen.getByRole('button', { name: /open my vault/i });
    expect(open).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /replaced my old phrase/i }));
    await userEvent.click(open);
    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('shows one generic message when the phrase opens nothing on this device', async () => {
    recovery.identifyVaultForPhrase.mockReturnValue(null);
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/don't open a vault on this device/i);
    expect(screen.getByLabelText('Word 1')).toHaveValue('w1'); // boxes keep their contents
    expect(screen.queryByLabelText(/new vault password/i)).toBeNull();
  });

  it('a recovery kit file fills the words and supplies the vault for a new device', async () => {
    recovery.identifyVaultForPhrase.mockReturnValue(null);
    session.vaults = [];
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    const kit = `CORTEX RECOVERY KIT\nVault:    Family archive\nVault ID: v-far\n\nRecovery phrase (24 words, in order):\n${WORDS.join(' ')}\n`;
    const file = new File([kit], 'kit.txt', { type: 'text/plain' });
    await userEvent.upload(screen.getByLabelText(/recovery kit file/i), file);
    expect(await screen.findByDisplayValue('w24')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    expect(screen.getByText(/family archive/i)).toBeInTheDocument();
    session.vaults = [{ vaultId: 'v1', name: 'Personal' }];
  });

  it('the kit path warns that an empty vault cannot be proven before re-securing it', async () => {
    recovery.identifyVaultForPhrase.mockReturnValue(null);
    session.vaults = [];
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    const kit = `CORTEX RECOVERY KIT\nVault:    Family archive\nVault ID: v-far\n\nRecovery phrase (24 words, in order):\n${WORDS.join(' ')}\n`;
    const file = new File([kit], 'kit.txt', { type: 'text/plain' });
    await userEvent.upload(screen.getByLabelText(/recovery kit file/i), file);
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    expect(screen.getByText(/if this vault has no files yet, we can't confirm the phrase/i)).toBeInTheDocument();
    session.vaults = [{ vaultId: 'v1', name: 'Personal' }];
  });

  it('does not show the empty-vault warning on the local-verifier path', async () => {
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    expect(screen.queryByText(/can't confirm the phrase/i)).toBeNull();
  });

  it('a rotation failure returns to the password step with the error', async () => {
    session.recoverVault.mockRejectedValueOnce(new Error('Another vault password change is already in progress'));
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    await userEvent.type(screen.getByLabelText(/^new vault password/i), 'NewVaultPw123!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewVaultPw123!');
    await userEvent.click(screen.getByRole('button', { name: /set password and re-secure/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/already in progress/i);
    expect(screen.getByLabelText(/^new vault password/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Word 1')).toBeNull();
  });

  it('offers to start over when the staged password change does not match the new password', async () => {
    session.recoverVault.mockImplementationOnce(async (_phrase, _password, _onProgress, _target, onStagedMismatch) => {
      const decision = await onStagedMismatch!(1_757_900_000);
      if (decision.action !== 'startOver') throw new Error(`unexpected ${decision.action}`);
      return { phrase: NEW_PHRASE, vaultId: 'v1', name: 'Personal' };
    });
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    await userEvent.type(screen.getByLabelText(/^new vault password/i), 'NewVaultPw123!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewVaultPw123!');
    await userEvent.click(screen.getByRole('button', { name: /set password and re-secure/i }));
    const staged = await screen.findByRole('dialog', { name: 'Finish an earlier password change?' });
    await userEvent.click(within(staged).getByRole('button', { name: 'Start over' }));
    expect(await screen.findByText('n1 n2 n3')).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Finish an earlier password change?' })).toBeNull();
  });

  it('Cancel in the staged dialog returns to the password step without an error', async () => {
    session.recoverVault.mockImplementationOnce(async (_phrase, _password, _onProgress, _target, onStagedMismatch) => {
      const decision = await onStagedMismatch!(null);
      if (decision.action === 'cancel') throw new Error('Password change cancelled');
      throw new Error(`unexpected ${decision.action}`);
    });
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    await userEvent.type(screen.getByLabelText(/^new vault password/i), 'NewVaultPw123!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewVaultPw123!');
    await userEvent.click(screen.getByRole('button', { name: /set password and re-secure/i }));
    const staged = await screen.findByRole('dialog', { name: 'Finish an earlier password change?' });
    await userEvent.click(within(staged).getByRole('button', { name: 'Cancel' }));
    expect(await screen.findByLabelText(/^new vault password/i)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('dialog', { name: 'Finish an earlier password change?' })).toBeNull();
  });
});
