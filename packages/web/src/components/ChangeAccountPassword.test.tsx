import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { SessionValue } from '../auth/SessionContext';

const { mockChangeAccountPassword, mockSession } = vi.hoisted(() => {
  const mockChangeAccountPassword = vi.fn<SessionValue['changeAccountPassword']>();
  return {
    mockChangeAccountPassword,
    mockSession: { status: 'unlocked', changeAccountPassword: mockChangeAccountPassword },
  };
});
vi.mock('../auth/SessionContext', () => ({ useSession: () => mockSession }));

import ChangeAccountPassword from './ChangeAccountPassword';

const onDone = vi.fn();

function fill(current: string, next: string, confirm: string) {
  fireEvent.change(screen.getByLabelText(/current account password/i), { target: { value: current } });
  fireEvent.change(screen.getByLabelText(/^new account password$/i), { target: { value: next } });
  fireEvent.change(screen.getByLabelText(/confirm new account password/i), { target: { value: confirm } });
}

beforeEach(() => {
  onDone.mockClear();
  mockChangeAccountPassword.mockReset();
  mockChangeAccountPassword.mockResolvedValue(undefined);
});

describe('ChangeAccountPassword', () => {
  it('shows an error when the new passwords do not match and does not call the API', async () => {
    render(<ChangeAccountPassword onDone={onDone} />);

    fill('old', 'abc123', 'different');
    fireEvent.click(screen.getByRole('button', { name: /change account password/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/passwords do not match/i);
    expect(mockChangeAccountPassword).not.toHaveBeenCalled();
  });

  it('calls changeAccountPassword with the current and new password, then confirms', async () => {
    render(<ChangeAccountPassword onDone={onDone} />);

    fill('old', 'New$ecure1', 'New$ecure1');
    fireEvent.click(screen.getByRole('button', { name: /change account password/i }));

    await waitFor(() =>
      expect(mockChangeAccountPassword).toHaveBeenCalledWith('old', 'New$ecure1'),
    );
    expect(await screen.findByText(/account password changed/i)).toBeInTheDocument();
  });

  it('shows an error and stays on the form when the change is rejected', async () => {
    mockChangeAccountPassword.mockRejectedValueOnce(new Error('Incorrect username or password.'));
    render(<ChangeAccountPassword onDone={onDone} />);

    fill('wrong', 'New$ecure1', 'New$ecure1');
    fireEvent.click(screen.getByRole('button', { name: /change account password/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect username or password/i);
    expect(onDone).not.toHaveBeenCalled();
  });
});
