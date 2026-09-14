import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const { session, navigate } = vi.hoisted(() => ({
  session: { confirmAccount: vi.fn(async () => {}), resendCode: vi.fn(async () => {}) },
  navigate: vi.fn(),
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => session }));
vi.mock('react-router-dom', async (o) => ({
  ...(await o<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import VerifyEmail from './VerifyEmail';

beforeEach(() => vi.clearAllMocks());

function renderWithEmail() {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/verify', state: { email: 'a@b.com' } }]}>
      <VerifyEmail />
    </MemoryRouter>,
  );
}

describe('VerifyEmail', () => {
  it('shows the address the code went to and submits when the code is complete', async () => {
    renderWithEmail();
    expect(screen.getByText(/a@b\.com/)).toBeInTheDocument();
    fireEvent.paste(screen.getByLabelText('Digit 1'), { clipboardData: { getData: () => '123456' } });
    await waitFor(() => expect(session.confirmAccount).toHaveBeenCalledWith('a@b.com', '123456'));
    expect(navigate).toHaveBeenCalledWith('/login');
  });

  it('asks for the email when none was passed', () => {
    render(
      <MemoryRouter>
        <VerifyEmail />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it('can resend the code', async () => {
    renderWithEmail();
    await userEvent.click(screen.getByRole('button', { name: /resend code/i }));
    expect(session.resendCode).toHaveBeenCalledWith('a@b.com');
  });

  it('shows an error when resending fails', async () => {
    session.resendCode.mockRejectedValueOnce(new Error('Too many attempts'));
    renderWithEmail();
    await userEvent.click(screen.getByRole('button', { name: /resend code/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many attempts/i);
  });
});
