import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../auth/SessionContext';

// Resets the Cognito *account* password only. The vault password (which derives the
// encryption key client-side) is separate and unrecoverable here — that's BIP39 recovery.
export default function ForgotPassword() {
  const { requestPasswordReset, confirmPasswordReset } = useSession();
  const navigate = useNavigate();
  const [sent, setSent] = useState(false);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');

  async function onRequest(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send reset code');
    }
  }

  async function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await confirmPasswordReset(email, code, newPassword);
      navigate('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed');
    }
  }

  return (
    <form onSubmit={sent ? onConfirm : onRequest}>
      <h1>Reset account password</h1>
      <p>This resets your account login only. Your vault password is separate.</p>
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={sent}
          required
        />
      </label>
      {sent && (
        <>
          <label>
            Reset code
            <input value={code} onChange={(e) => setCode(e.target.value)} required />
          </label>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </label>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      <button type="submit">{sent ? 'Set new password' : 'Send reset code'}</button>
    </form>
  );
}
