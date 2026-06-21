import { useCallback, useEffect, useState } from 'react';
import { getVaultKeys } from '../vault/keyAccess';
import { listItems, getDownloadUrl, deleteItem } from '../api/items';
import { decryptMetadata, type FileMetadata } from '../items/metadata';
import { decryptDownloadedBlob } from '../items/itemCrypto';

interface Row {
  itemId: string;
  createdAt?: Date; // generated ItemData.createdAt is a Date (not epoch seconds)
  meta: FileMetadata | null; // null = metadata failed to decrypt
}

export default function FileList({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { vaultId, metadataKey } = await getVaultKeys();
      const items = await listItems(vaultId);
      setRows(
        items.map((it) => {
          let meta: FileMetadata | null = null;
          try {
            if (it.encryptedMetadata) meta = decryptMetadata(it.encryptedMetadata, metadataKey);
          } catch {
            // metadata won't decrypt → show the row as unreadable
          }
          return { itemId: it.itemId!, createdAt: it.createdAt, meta };
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load files');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function onDownload(row: Row) {
    if (!row.meta) return;
    const { kek } = await getVaultKeys();
    const url = await getDownloadUrl(row.itemId);
    const blob = new Uint8Array(await (await fetch(url)).arrayBuffer());
    const plain = decryptDownloadedBlob(blob, row.meta, kek);
    const objectUrl = URL.createObjectURL(new Blob([plain as BlobPart], { type: row.meta.contentType }));
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = row.meta.name;
    a.click();
    URL.revokeObjectURL(objectUrl);
  }

  async function onDelete(itemId: string) {
    await deleteItem(itemId);
    await load();
  }

  if (error) return <p role="alert">{error}</p>;
  if (rows.length === 0) return <p>No files yet.</p>;

  return (
    <ul>
      {rows.map((row) => (
        <li key={row.itemId}>
          <span>{row.meta ? row.meta.name : '(unreadable)'}</span>
          {row.meta && <span> · {row.meta.size} bytes</span>}
          {row.createdAt && <span> · {row.createdAt.toLocaleDateString()}</span>}
          <button onClick={() => onDownload(row)} disabled={!row.meta}>Download</button>
          <button onClick={() => onDelete(row.itemId)}>Delete</button>
        </li>
      ))}
    </ul>
  );
}
