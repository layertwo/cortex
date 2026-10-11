import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { SessionValue } from '../auth/SessionContext';

const WORDS = Array.from({ length: 24 }, (_, i) => `w${i + 1}`);

const { session, navigate, recovery } = vi.hoisted(() => ({
  session: {
    vaults: [{ vaultId: 'v1', name: 'Personal' }],
    recoverVault: vi.fn<SessionValue['recoverVault']>(async () => ({ phrase: '', vaultId: 'v1', name: 'Personal' })),
  },
  navigate: vi.fn(),
  recovery: { identifyVaultForPhrase: vi.fn((): string | null => 'v1'), PHRASE_ERROR: "Those words don't open a vault on this device. Check each word and the order, then try again. On a new device, use your recovery kit." },
}));
vi.mock('../auth/SessionContext', () => ({
  useSession: () => session,
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
  session.vaults = [{ vaultId: 'v1', name: 'Personal' }];
  session.recoverVault.mockResolvedValue({ phrase: WORDS.join(' '), vaultId: 'v1', name: 'Personal' });
});

function pastePhrase() {
  fireEvent.paste(screen.getByLabelText('Word 1'), { clipboardData: { getData: () => WORDS.join(' ') } });
}

describe('RecoverVault', () => {
  it('walks phrase → new password → restored → open vault, keeping the same phrase', async () => {
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
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
    await waitFor(() =>
      expect(session.recoverVault).toHaveBeenCalledWith(WORDS.join(' '), 'NewVaultPw123!', { vaultId: 'v1', name: undefined }),
    );
    expect(await screen.findByText(/your vault is restored/i)).toBeInTheDocument();
    expect(screen.getByText(/recovery phrase is unchanged/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /open my vault/i }));
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
  });

  it('does not show the empty-vault warning on the local path', async () => {
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    expect(screen.queryByText(/can't confirm the phrase/i)).toBeNull();
  });

  it('a recovery failure returns to the password step with the error', async () => {
    session.recoverVault.mockRejectedValueOnce(new Error('A key rotation is in progress; finish it before recovering this vault'));
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    await userEvent.type(screen.getByLabelText(/^new vault password/i), 'NewVaultPw123!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewVaultPw123!');
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/rotation is in progress/i);
    expect(screen.getByLabelText(/^new vault password/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Word 1')).toBeNull();
  });

  it('a phrase error returns to the phrase step', async () => {
    session.recoverVault.mockRejectedValueOnce(new Error(recovery.PHRASE_ERROR));
    render(
      <MemoryRouter>
        <RecoverVault />
      </MemoryRouter>,
    );
    pastePhrase();
    await userEvent.click(screen.getByRole('button', { name: /continue · 24 of 24/i }));
    await userEvent.type(screen.getByLabelText(/^new vault password/i), 'NewVaultPw123!');
    await userEvent.type(screen.getByLabelText(/confirm/i), 'NewVaultPw123!');
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
    expect(await screen.findByLabelText('Word 1')).toBeInTheDocument();
  });
});
