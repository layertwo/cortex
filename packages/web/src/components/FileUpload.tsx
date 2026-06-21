import { useState } from 'react';
import { getVaultKeys } from '../vault/keyAccess';
import { encryptFileForUpload } from '../items/itemCrypto';
import { initiateUpload, putToS3, completeUpload } from '../api/items';

export const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024;

export default function FileUpload({ onUploaded }: { onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file
    if (!file) return;
    setError('');
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError("Files over 100 MB aren't supported yet — large-file streaming is coming.");
      return;
    }
    setBusy(true);
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const keys = await getVaultKeys();
      const { blob, encryptedMetadata } = await encryptFileForUpload(
        bytes, file.name, file.type || 'application/octet-stream', keys,
      );
      const { itemId, uploadUrl } = await initiateUpload({
        vaultId: keys.vaultId,
        encryptedMetadata,
        sizeBytes: blob.length,
      });
      await putToS3(uploadUrl, blob);
      await completeUpload(itemId);
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
      {busy && <p>Encrypting and uploading…</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
