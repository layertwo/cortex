import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../auth/SessionContext';

export default function VaultSetup() {
  const { setupVault } = useSession();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [recovery, setRecovery] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Vault passwords do not match');
      return;
    }
    try {
      setRecovery(await setupVault(password));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Vault setup failed');
    }
  }

  if (recovery) {
    return (
      <div>
        <h1>Save your recovery phrase</h1>
        <p>
          This 24-word phrase is the only way to recover your vault if you forget your vault
          password. Store it offline. It will not be shown again.
        </p>
        <pre>{recovery}</pre>
        <label>
          <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} /> I
          have saved my recovery phrase
        </label>
        <button disabled={!saved} onClick={() => navigate('/')}>
          Continue
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onCreate}>
      <h1>Set up your vault</h1>
      <p>Use a different password than your account password.</p>
      <label>
        Vault password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      <label>
        Confirm vault password
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="submit">Create vault</button>
    </form>
  );
}
