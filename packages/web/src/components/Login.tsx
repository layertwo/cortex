import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useSession } from '../auth/SessionContext';

export default function Login() {
  const { signInAccount } = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await signInAccount(email, password);
      // Land on '/'; the RequireAuth + RequireVault guards forward to vault unlock/setup.
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1>Log in</h1>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit">Log in</button>
      <Link to="/forgot">Forgot password?</Link>
    </form>
  );
}
