import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const { session } = vi.hoisted(() => ({
  session: {
    deleteVault: vi.fn(async (_vaultId: string, _password: string, _onProgress?: (n: number) => void) => {}),
  },
}));
vi.mock('../auth/SessionContext', () => ({
  useSession: () => session,
  DELETE_REFUSED: 'Unlock this vault once on a device that knows its password',
}));

import DeleteVaultDialog from './DeleteVaultDialog';
import { DELETE_REFUSED } from '../auth/SessionContext';

const vault = { vaultId: 'v2', name: 'Family archive' };

beforeEach(() => vi.clearAllMocks());

function setup() {
  const onClose = vi.fn();
  render(<DeleteVaultDialog vault={vault} onClose={onClose} />);
  const dialog = screen.getByRole('dialog', { name: /delete family archive/i });
  return { dialog, onClose };
}

describe('DeleteVaultDialog', () => {
  it('explains the consequence and enables Delete vault only once a password is typed', async () => {
    const { dialog } = setup();
    expect(
      within(dialog).getByText('Deletes every file, collection and share in this vault. This cannot be undone.'),
    ).toBeInTheDocument();
    const del = within(dialog).getByRole('button', { name: /^delete vault$/i });
    expect(del).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'pw');
    expect(del).toBeEnabled();
  });

  it('shows progress while deleting, blocks Cancel, then closes on success', async () => {
    let finish!: () => void;
    session.deleteVault.mockImplementationOnce((_id, _pw, onProgress) => {
      onProgress?.(3);
      return new Promise<void>((resolve) => {
        finish = resolve;
      });
    });
    const { dialog, onClose } = setup();
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'pw');
    await userEvent.click(within(dialog).getByRole('button', { name: /^delete vault$/i }));
    expect(await within(dialog).findByText('Deleting… 3 files removed')).toBeInTheDocument();
    expect(session.deleteVault).toHaveBeenCalledWith('v2', 'pw', expect.any(Function));
    expect(within(dialog).getByRole('button', { name: /cancel/i })).toBeDisabled();
    expect(onClose).not.toHaveBeenCalled();
    finish();
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('stops on a 409 with the server message and offers no Retry', async () => {
    session.deleteVault.mockRejectedValueOnce(
      Object.assign(new Error('A vault password change is in progress; wait for it to finish or pause it first'), {
        name: 'ConflictError',
      }),
    );
    const { dialog, onClose } = setup();
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'pw');
    await userEvent.click(within(dialog).getByRole('button', { name: /^delete vault$/i }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'A vault password change is in progress; wait for it to finish or pause it first',
    );
    expect(within(dialog).queryByRole('button', { name: /retry/i })).toBeNull();
    expect(within(dialog).getByRole('button', { name: /^delete vault$/i })).toBeEnabled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('offers Retry after any other error and runs the delete again', async () => {
    session.deleteVault.mockRejectedValueOnce(new Error('Failed to fetch'));
    const { dialog, onClose } = setup();
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'pw');
    await userEvent.click(within(dialog).getByRole('button', { name: /^delete vault$/i }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Failed to fetch');
    await userEvent.click(within(dialog).getByRole('button', { name: /^retry$/i }));
    await waitFor(() => expect(session.deleteVault).toHaveBeenCalledTimes(2));
    expect(onClose).toHaveBeenCalled();
  });

  it('Cancel closes without calling deleteVault', async () => {
    const { dialog, onClose } = setup();
    await userEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
    expect(session.deleteVault).not.toHaveBeenCalled();
  });

  it('a fail-closed refusal (no verifier anywhere) offers no Retry', async () => {
    session.deleteVault.mockRejectedValueOnce(new Error(DELETE_REFUSED));
    const { dialog, onClose } = setup();
    await userEvent.type(within(dialog).getByLabelText(/vault password/i), 'pw');
    await userEvent.click(within(dialog).getByRole('button', { name: /^delete vault$/i }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(DELETE_REFUSED);
    expect(within(dialog).queryByRole('button', { name: /retry/i })).toBeNull();
    expect(within(dialog).getByRole('button', { name: /^delete vault$/i })).toBeEnabled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
