import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { SessionValue } from '../auth/SessionContext';

const { mockChangeVaultPassword, mockSession } = vi.hoisted(() => {
  const mockChangeVaultPassword = vi.fn<SessionValue['changeVaultPassword']>();
  return {
    mockChangeVaultPassword,
    mockSession: {
      status: 'unlocked',
      changeVaultPassword: mockChangeVaultPassword,
    },
  };
});
vi.mock('../auth/SessionContext', () => ({
  useSession: () => mockSession,
}));

import ChangeVaultPassword from './ChangeVaultPassword';

const onDone = vi.fn();

beforeEach(() => {
  mockChangeVaultPassword.mockResolvedValue(undefined);
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

  it('calls changeVaultPassword with current + new password and closes on success', async () => {
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    await waitFor(() => expect(mockChangeVaultPassword).toHaveBeenCalledWith('old', 'New$ecure1'));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it('says the recovery phrase is unchanged and shows no sweep or phrase stage', async () => {
    render(<ChangeVaultPassword onDone={onDone} />);
    expect(screen.getByText(/your recovery phrase stays the same/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(screen.queryByText(/type your new recovery phrase/i)).toBeNull();
    expect(screen.queryByText(/re-encrypting files/i)).toBeNull();
  });

  it('shows error and returns to the form when changeVaultPassword rejects (wrong password)', async () => {
    mockChangeVaultPassword.mockRejectedValueOnce(new Error('Incorrect vault password'));
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'wrong' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect vault password/i);
    expect(screen.getByRole('button', { name: /change password/i })).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();
  });

  it('shows error and returns to form for a message-only rejection (rotation conflict)', async () => {
    mockChangeVaultPassword.mockRejectedValueOnce(new Error('A vault password change cannot add or drop a VMK version'));
    render(<ChangeVaultPassword onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/current vault password/i), { target: { value: 'old' } });
    fireEvent.change(screen.getByLabelText(/^new vault password$/i), { target: { value: 'New$ecure1' } });
    fireEvent.change(screen.getByLabelText(/confirm new/i), { target: { value: 'New$ecure1' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot add or drop a VMK version/i);
    expect(onDone).not.toHaveBeenCalled();
  });
});
