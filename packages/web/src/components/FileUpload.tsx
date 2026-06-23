import { useState } from 'react';
import { getVaultKeys } from '../vault/keyAccess';
import { uploadFileStreaming } from '../items/streamingUpload';

// Soft ceiling ~5 GB. S3 multipart's hard cap at 8 MiB parts is ~80 GB; we guard
// well below that and show a clear message instead of letting a huge file hang.
export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024;

export default function FileUpload({ onUploaded }: { onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file
    if (!file) return;
    setError('');
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError('Files over 5 GB aren’t supported.');
      return;
    }
    setBusy(true);
    setProgress(0);
    try {
      const keys = await getVaultKeys();
      await uploadFileStreaming(file, keys, setProgress);
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <label>
        Upload file
        <input type="file" onChange={onChange} disabled={busy} />
      </label>
      {busy && <p>Encrypting and uploading… {Math.round(progress * 100)}%</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
