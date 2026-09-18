import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { SessionValue } from '../auth/SessionContext';

const { mockChangeVaultPassword, mockSession } = vi.hoisted(() => {
  const mockChangeVaultPassword = vi.fn<SessionValue['changeVaultPassword']>();
  return {
    mockChangeVaultPassword,
    mockSession: {
      status: 'unlocked',
      changeVaultPassword: mockChangeVaultPassword,
      rotationInterrupted: false,
    },
  };
});
vi.mock('../auth/SessionContext', () => ({
  useSession: () => mockSession,
  CANCELLED_ERROR: 'Password change cancelled',
}));

import ChangeVaultPassword from './ChangeVaultPassword';

const onDone = vi.fn();

beforeEach(() => {
  mockChangeVaultPassword.mockResolvedValue('word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24');
});

describe('ChangeVaultPassword', () => {
  it('shows error when new passwords do not match', async () => {
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'abc123' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'different' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/passwords do not match/i);
    expect(mockChangeVaultPassword).not.toHaveBeenCalled();
  });

  it('calls changeVaultPassword with current + new password', async () => {
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    await waitFor(() =>
      expect(mockChangeVaultPassword).toHaveBeenCalledWith('old', 'New$ecure1', expect.any(Function), expect.any(Function)),
    );
  });

  it('shows recovery phrase after sweep completes', async () => {
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    expect(await screen.findByText(/your old recovery phrase no longer works/i)).toBeInTheDocument();
    expect(screen.getByText('word1 word2 word3')).toBeInTheDocument();
  });

  it('requires phrase confirmation before completing', async () => {
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    await screen.findByText(/your old recovery phrase/i);
    fireEvent.click(screen.getByRole('button', { name: /complete password change/i }));
    // onDone not called yet — no phrase typed
    expect(onDone).not.toHaveBeenCalled();
  });

  it('calls onDone when phrase typed correctly and confirmed', async () => {
    const phrase = 'word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24';
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    await screen.findByText(/your old recovery phrase/i);
    fireEvent.change(screen.getByLabelText(/type your new recovery phrase/i), { target: { value: phrase } });
    fireEvent.click(screen.getByRole('button', { name: /complete password change/i }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it('shows error and returns to form when changeVaultPassword rejects (wrong password)', async () => {
    mockChangeVaultPassword.mockRejectedValueOnce(new Error('Incorrect vault password'));
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'wrong' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect vault password/i);
    // returned to the form stage, not stuck on the sweep-progress view
    expect(screen.getByRole('button', { name: /change password/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/current vault password/i)).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();
  });

  it('shows error and returns to form for a message-only rejection (no error code, e.g. rotation conflict)', async () => {
    // Simulates the backend's ConflictError shape: a plain Error with a message,
    // no `code` field — the component must not pattern-match on `code`.
    mockChangeVaultPassword.mockRejectedValueOnce(new Error('Another vault password change is already in progress'));
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/another vault password change is already in progress/i);
    expect(screen.getByRole('button', { name: /change password/i })).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();
  });

  it('asks for the earlier new password when a different change is staged, then finishes with it', async () => {
    mockChangeVaultPassword.mockImplementationOnce(async (_current, _next, _onProgress, onStagedMismatch) => {
      const decision = await onStagedMismatch!(1_757_900_000);
      if (decision.action !== 'finish' || decision.password !== 'Earlier1!') throw new Error(`unexpected ${decision.action}`);
      return 'word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24';
    });
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    const staged = await screen.findByRole('dialog', { name: 'Finish an earlier password change?' });
    expect(staged).toHaveTextContent(new Date(1_757_900_000 * 1000).toLocaleString());
    await userEvent.type(within(staged).getByLabelText('Earlier new password'), 'Earlier1!');
    await userEvent.click(within(staged).getByRole('button', { name: 'Finish' }));
    expect(await screen.findByText(/your old recovery phrase no longer works/i)).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Finish an earlier password change?' })).toBeNull();
  });

  it('Cancel in the staged dialog closes the change-password dialog without showing an error', async () => {
    mockChangeVaultPassword.mockImplementationOnce(async (_current, _next, _onProgress, onStagedMismatch) => {
      const decision = await onStagedMismatch!(null);
      if (decision.action === 'cancel') throw new Error('Password change cancelled');
      throw new Error(`unexpected ${decision.action}`);
    });
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    const staged = await screen.findByRole('dialog', { name: 'Finish an earlier password change?' });
    await userEvent.click(within(staged).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    // purpose="required" renders the sweep-stage dialog as an alertdialog.
    const sweep = screen.getByRole('alertdialog', { name: /changing vault password/i });
    expect(within(sweep).queryByRole('alert')).toBeNull();
  });
});
