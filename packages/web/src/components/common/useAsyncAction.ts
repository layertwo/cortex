import { useState } from 'react';

// The submit scaffold every auth and vault screen needs: clear the previous error,
// hold `pending` while the action runs, and surface a message if it throws.
// ChangeVaultPassword keeps its own staged flow and ShareAccess its state machine.
export function useAsyncAction() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function run(action: () => Promise<void>, fallbackMessage: string): Promise<void> {
    setError('');
    setPending(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : fallbackMessage);
    } finally {
      setPending(false);
    }
  }

  return { pending, error, setError, run };
}
