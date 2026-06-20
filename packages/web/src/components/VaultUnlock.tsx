import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../auth/SessionContext';

export default function VaultUnlock() {
  const { unlockVault } = useSession();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await unlockVault(password);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unlock failed');
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1>Unlock your vault</h1>
      <label>
        Vault password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit">Unlock</button>
    </form>
  );
}
