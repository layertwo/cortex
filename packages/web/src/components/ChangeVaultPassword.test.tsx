import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { mockChangeVaultPassword, mockSession } = vi.hoisted(() => {
  const mockChangeVaultPassword = vi.fn();
  return {
    mockChangeVaultPassword,
    mockSession: {
      status: 'unlocked',
      changeVaultPassword: mockChangeVaultPassword,
      rotationInterrupted: false,
    },
  };
});
vi.mock('../auth/SessionContext', () => ({ useSession: () => mockSession }));

import ChangeVaultPassword from './ChangeVaultPassword';

const onDone = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
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
    await waitFor(() => expect(mockChangeVaultPassword).toHaveBeenCalledWith('old', 'New$ecure1', expect.any(Function)));
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
});
