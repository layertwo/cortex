import { useState } from 'react';
import { useSession } from '../auth/SessionContext';

type Stage = 'form' | 'sweep' | 'phrase' | 'done';

export default function ChangeVaultPassword({ onDone }: { onDone: () => void }) {
  const { changeVaultPassword } = useSession();
  const [stage, setStage] = useState<Stage>('form');
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [phrase, setPhrase] = useState('');
  const [phraseInput, setPhraseInput] = useState('');
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (next !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setStage('sweep');
    try {
      const newPhrase = await changeVaultPassword(current, next, (done, total) =>
        setProgress({ done, total }),
      );
      setPhrase(newPhrase);
      setStage('phrase');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password change failed');
      setStage('form');
    }
  }

  function handleComplete() {
    if (phraseInput.trim() !== phrase.trim()) {
      setError('Recovery phrase does not match — copy it exactly');
      return;
    }
    setStage('done');
    onDone();
  }

  if (stage === 'sweep') {
    return (
      <div>
        <h2>Changing vault password…</h2>
        <p>Keep this tab open — you can safely resume if interrupted.</p>
        {progress.total > 0 && (
          <progress value={progress.done} max={progress.total}>
            {Math.round((progress.done / progress.total) * 100)}%
          </progress>
        )}
      </div>
    );
  }

  if (stage === 'phrase') {
    const words = phrase.split(' ');
    const rows: string[] = [];
    for (let i = 0; i < words.length; i += 3) {
      rows.push(words.slice(i, i + 3).join(' '));
    }
    return (
      <div>
        <h2>Save your new recovery phrase</h2>
        <p>Your old recovery phrase no longer works. Save this new one before continuing.</p>
        <div aria-label="recovery phrase">
          {rows.map((row, i) => (
            <div key={i}>{row}</div>
          ))}
        </div>
        <button
          onClick={() => navigator.clipboard.writeText(phrase).catch(() => {})}
          type="button"
        >
          Copy to clipboard
        </button>
        <label htmlFor="phrase-input">Type your new recovery phrase to confirm:</label>
        <input
          id="phrase-input"
          aria-label="type your new recovery phrase"
          value={phraseInput}
          onChange={(e) => setPhraseInput(e.target.value)}
        />
        {error && <p role="alert">{error}</p>}
        <button type="button" onClick={handleComplete}>
          Complete password change
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Change vault password</h2>
      <label htmlFor="current-pw">Current vault password</label>
      <input
        id="current-pw"
        type="password"
        aria-label="current vault password"
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
        required
      />
      <label htmlFor="new-pw">New vault password</label>
      <input
        id="new-pw"
        type="password"
        aria-label="new vault password"
        value={next}
        onChange={(e) => setNext(e.target.value)}
        required
      />
      <label htmlFor="confirm-pw">Confirm new password</label>
      <input
        id="confirm-pw"
        type="password"
        aria-label="confirm new password"
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        required
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit">Change password</button>
    </form>
  );
}
