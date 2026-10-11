import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { SessionValue } from '../auth/SessionContext';

const PHRASE = Array.from({ length: 24 }, (_, i) => `w${i + 1}`).join(' ');

const { mockRotate, mockSession } = vi.hoisted(() => {
  const mockRotate = vi.fn<SessionValue['rotateEncryptionKeys']>();
  return {
    mockRotate,
    mockSession: { rotateEncryptionKeys: mockRotate },
  };
});
vi.mock('../auth/SessionContext', () => ({
  useSession: () => mockSession,
  ROTATION_INCOMPLETE: 'Some files still need re-keying; the key rotation is paused and can be resumed',
}));

import RotateKeysDialog from './RotateKeysDialog';

const onDone = vi.fn();

beforeEach(() => {
  mockRotate.mockResolvedValue(PHRASE);
});

describe('RotateKeysDialog', () => {
  it('confirms the password, then shows the new phrase and closes once saved', async () => {
    render(<RotateKeysDialog onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/vault password/i), { target: { value: 'pw' } });
    fireEvent.click(screen.getByRole('button', { name: /rotate keys/i }));
    await waitFor(() => expect(mockRotate).toHaveBeenCalledWith('pw', expect.any(Function)));
    expect(await screen.findByText('w1 w2 w3')).toBeInTheDocument();
    const done = screen.getByRole('button', { name: /^done$/i });
    expect(done).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /saved my new recovery phrase/i }));
    await userEvent.click(done);
    expect(onDone).toHaveBeenCalled();
  });

  it('returns to the form with the error when the password is wrong', async () => {
    mockRotate.mockRejectedValueOnce(new Error('Incorrect vault password'));
    render(<RotateKeysDialog onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/vault password/i), { target: { value: 'bad' } });
    fireEvent.click(screen.getByRole('button', { name: /rotate keys/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect vault password/i);
    expect(screen.getByRole('button', { name: /rotate keys/i })).toBeInTheDocument();
    expect(onDone).not.toHaveBeenCalled();
  });

  it('surfaces a resumable straggler error plainly', async () => {
    mockRotate.mockRejectedValueOnce(new Error('Some files still need re-keying; the key rotation is paused and can be resumed'));
    render(<RotateKeysDialog onDone={onDone} />);
    fireEvent.change(screen.getByLabelText(/vault password/i), { target: { value: 'pw' } });
    fireEvent.click(screen.getByRole('button', { name: /rotate keys/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/try again to finish it/i);
  });
});
