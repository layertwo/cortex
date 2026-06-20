import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSession } from '../auth/SessionContext';

export default function VerifyEmail() {
  const { confirmAccount } = useSession();
  const navigate = useNavigate();
  const passedEmail = (useLocation().state as { email?: string } | null)?.email ?? '';
  const [email, setEmail] = useState(passedEmail);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await confirmAccount(email, code);
      navigate('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1>Verify your email</h1>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Verification code
        <input value={code} onChange={(e) => setCode(e.target.value)} required />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit">Verify</button>
    </form>
  );
}
