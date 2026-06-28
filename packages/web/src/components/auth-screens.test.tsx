import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const { session, navigate } = vi.hoisted(() => ({
  session: {
    signUpAccount: vi.fn(async () => {}),
    confirmAccount: vi.fn(async () => {}),
    signInAccount: vi.fn(async () => {}),
    requestPasswordReset: vi.fn(async () => {}),
    confirmPasswordReset: vi.fn(async () => {}),
  },
  navigate: vi.fn(),
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => session }));
vi.mock('react-router-dom', async (o) => ({
  ...(await o<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import Signup from './Signup';
import Login from './Login';
import ForgotPassword from './ForgotPassword';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('auth screens', () => {
  it('Signup calls signUpAccount with email + account password and navigates to /verify', async () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'Abcdefg1!2345');
    await userEvent.click(screen.getByRole('button', { name: /sign up/i }));
    expect(session.signUpAccount).toHaveBeenCalledWith('a@b.com', 'Abcdefg1!2345');
    expect(navigate).toHaveBeenCalledWith('/verify', { state: { email: 'a@b.com' } });
  });

  it('Login calls signInAccount and navigates to / on success', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'Abcdefg1!2345');
    await userEvent.click(screen.getByRole('button', { name: /log in/i }));
    expect(session.signInAccount).toHaveBeenCalledWith('a@b.com', 'Abcdefg1!2345');
    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('ForgotPassword stage 1 requests a code, then reveals the code + new-password fields', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    );
    // Code/password inputs are hidden until a reset code has been requested.
    expect(screen.queryByLabelText(/reset code/i)).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    expect(session.requestPasswordReset).toHaveBeenCalledWith('a@b.com');
    expect(await screen.findByLabelText(/reset code/i)).toBeInTheDocument();
  });

  it('ForgotPassword stage 2 confirms the reset and navigates to /login', async () => {
    render(
      <MemoryRouter>
        <ForgotPassword />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await userEvent.type(await screen.findByLabelText(/reset code/i), '123456');
    await userEvent.type(screen.getByLabelText(/new password/i), 'Newpass1!2345');
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
    expect(session.confirmPasswordReset).toHaveBeenCalledWith('a@b.com', '123456', 'Newpass1!2345');
    expect(navigate).toHaveBeenCalledWith('/login');
  });
});
