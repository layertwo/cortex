import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const { session } = vi.hoisted(() => ({
  session: {
    vaults: [
      { vaultId: 'v1', name: 'Personal' },
      { vaultId: 'v2', name: 'Family archive' },
    ],
    activeVault: { vaultId: 'v1', name: 'Personal' },
    unlockVault: vi.fn(async () => {}),
    setupVault: vi.fn(async () => 'w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11 w12 w13 w14 w15 w16 w17 w18 w19 w20 w21 w22 w23 w24'),
    renameVault: vi.fn(async () => {}),
    deleteVault: vi.fn(async () => {}),
  },
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => session }));

import UnlockVaultDialog from './UnlockVaultDialog';
import NewVaultDialog from './NewVaultDialog';
import ManageVaultsDialog from './ManageVaultsDialog';

beforeEach(() => vi.clearAllMocks());

describe('UnlockVaultDialog', () => {
  it('unlocks the named vault and reports success', async () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <UnlockVaultDialog vault={{ vaultId: 'v2', name: 'Family archive' }} onClose={onClose} />
      </MemoryRouter>,
    );
    const dialog = screen.getByRole('dialog', { name: /unlock family archive/i });
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'pw');
    await userEvent.click(within(dialog).getByRole('button', { name: /unlock and switch/i }));
    await waitFor(() => expect(session.unlockVault).toHaveBeenCalledWith('pw', 'v2'));
    expect(onClose).toHaveBeenCalled();
    expect(within(dialog).getByRole('link', { name: /forgot your vault password/i })).toHaveAttribute('href', '/vault/recover');
  });

  it('keeps the dialog open and shows the error on a wrong password', async () => {
    session.unlockVault.mockRejectedValueOnce(new Error('Incorrect vault password'));
    render(
      <MemoryRouter>
        <UnlockVaultDialog vault={{ vaultId: 'v2', name: 'Family archive' }} onClose={vi.fn()} />
      </MemoryRouter>,
    );
    const dialog = screen.getByRole('dialog', { name: /unlock family archive/i });
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'bad');
    await userEvent.click(within(dialog).getByRole('button', { name: /unlock and switch/i }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/incorrect vault password/i);
  });
});

describe('NewVaultDialog', () => {
  it('creates a named vault, then shows the phrase and closes on Done', async () => {
    const onClose = vi.fn();
    render(<NewVaultDialog onClose={onClose} />);
    const dialog = screen.getByRole('dialog', { name: /new vault/i });
    await userEvent.type(within(dialog).getByLabelText(/vault name/i), 'Work');
    await userEvent.type(within(dialog).getByLabelText(/^vault password/i), 'VaultPw123456!');
    await userEvent.type(within(dialog).getByLabelText(/confirm/i), 'VaultPw123456!');
    await userEvent.click(within(dialog).getByRole('button', { name: /create vault/i }));
    await waitFor(() => expect(session.setupVault).toHaveBeenCalledWith('VaultPw123456!', 'Work'));
    expect(await screen.findByText('w1 w2 w3')).toBeInTheDocument();
    const done = screen.getByRole('button', { name: /^done$/i });
    expect(done).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /saved my recovery phrase/i }));
    await userEvent.click(done);
    expect(onClose).toHaveBeenCalled();
  });

  it('blocks mismatched passwords', async () => {
    render(<NewVaultDialog onClose={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /new vault/i });
    await userEvent.type(within(dialog).getByLabelText(/vault name/i), 'Work');
    await userEvent.type(within(dialog).getByLabelText(/^vault password/i), 'VaultPw123456!');
    await userEvent.type(within(dialog).getByLabelText(/confirm/i), 'nope');
    await userEvent.click(within(dialog).getByRole('button', { name: /create vault/i }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/do not match/i);
    expect(session.setupVault).not.toHaveBeenCalled();
  });
});

describe('ManageVaultsDialog', () => {
  it('lists vaults with their state, renames inline, and offers unlock for locked ones', async () => {
    const onUnlock = vi.fn();
    const onChangePassword = vi.fn();
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={onUnlock} onChangePassword={onChangePassword} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    expect(within(dialog).getByText('Open')).toBeInTheDocument();
    expect(within(dialog).getByText('Locked')).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText(/rename personal/i), '!');
    expect(session.renameVault).not.toHaveBeenCalled(); // draft only, commits on blur/Enter
    await userEvent.tab();
    expect(session.renameVault).toHaveBeenLastCalledWith('v1', 'Personal!');
    await userEvent.click(within(dialog).getByRole('button', { name: /unlock family archive/i }));
    expect(onUnlock).toHaveBeenCalledWith({ vaultId: 'v2', name: 'Family archive' });
    await userEvent.click(within(dialog).getByRole('button', { name: /change password/i }));
    expect(onChangePassword).toHaveBeenCalled();
  });

  it('renaming: commits the new name on blur when non-empty and different', async () => {
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={vi.fn()} onChangePassword={vi.fn()} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    const field = within(dialog).getByLabelText(/rename personal/i);
    await userEvent.clear(field);
    await userEvent.type(field, 'Work');
    await userEvent.tab();
    expect(session.renameVault).toHaveBeenCalledTimes(1);
    expect(session.renameVault).toHaveBeenCalledWith('v1', 'Work');
  });

  it('renaming: locked vaults are disabled with a visible hint, the open vault stays editable', () => {
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={vi.fn()} onChangePassword={vi.fn()} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    const field = within(dialog).getByLabelText(/rename family archive/i);
    expect(field).toBeDisabled();
    // Astryx's TextInput forwards `description` into a screen-reader-only span whenever the
    // label is hidden (isLabelHidden), so a hint passed that way is invisible by construction.
    // Asserting the field carries no accessible description (rather than only that the text
    // exists somewhere in the DOM) is what actually distinguishes a visible sibling hint from
    // that sr-only one.
    expect(field).not.toHaveAccessibleDescription();
    expect(within(dialog).getByText('Unlock to rename')).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/rename personal/i)).toBeEnabled();
  });

  it('renaming: the hint sits under the field, in its own column, not beside the row state label', () => {
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={vi.fn()} onChangePassword={vi.fn()} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    const field = within(dialog).getByLabelText(/rename family archive/i);
    const hint = within(dialog).getByText('Unlock to rename');
    // Astryx's Stack (VStack/HStack) reflects its `direction` prop as a real `data-direction`
    // DOM attribute (see Global Constraints); the field's nearest vertical ancestor must
    // contain the hint but not the row's own "Locked" state label or buttons.
    const column = field.closest('[data-direction="vertical"]');
    expect(column).not.toBeNull();
    expect(column).toContainElement(hint);
    expect(column).not.toHaveTextContent('Locked');
  });

  it('renaming: shows the error in the dialog when the server rejects it', async () => {
    session.renameVault.mockRejectedValueOnce(new Error('Network error'));
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={vi.fn()} onChangePassword={vi.fn()} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    await userEvent.type(within(dialog).getByLabelText(/rename personal/i), '!');
    await userEvent.tab();
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Network error');
  });

  it('renaming: clearing the field and blurring does not clear the name — the field reverts', async () => {
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={vi.fn()} onChangePassword={vi.fn()} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    const field = within(dialog).getByLabelText(/rename personal/i);
    await userEvent.clear(field);
    await userEvent.tab();
    expect(session.renameVault).not.toHaveBeenCalled();
    expect(within(dialog).getByLabelText(/rename personal/i)).toHaveValue('Personal');
  });

  it('offers Delete per vault and opens the password confirmation for that vault', async () => {
    render(<ManageVaultsDialog onClose={vi.fn()} onUnlock={vi.fn()} onChangePassword={vi.fn()} onNew={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: /manage vaults/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /^delete family archive$/i }));
    const confirm = screen.getByRole('dialog', { name: /^delete family archive$/i });
    expect(within(confirm).getByRole('button', { name: /^delete vault$/i })).toBeDisabled();
    await userEvent.click(within(confirm).getByRole('button', { name: /^cancel$/i }));
    expect(screen.queryByRole('dialog', { name: /^delete family archive$/i })).toBeNull();
    expect(session.deleteVault).not.toHaveBeenCalled();
  });
});
