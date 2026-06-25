import { useCallback, useEffect, useState } from 'react';
import { getVaultKeys } from '../vault/keyAccess';
import { listCollections, createCollection, deleteCollection } from '../api/collections';
import { encryptCollectionName, decryptCollectionName } from '../items/collectionMetadata';

export type View =
  | { kind: 'all' }
  | { kind: 'collection'; id: string; name: string }
  | { kind: 'tag'; encryptedTag: string; label: string };

type Row = { id: string; name: string };

export default function CollectionSidebar({
  selected,
  onSelect,
  refreshKey,
  onChanged,
}: {
  selected: View;
  onSelect: (v: View) => void;
  refreshKey: number;
  onChanged?: () => void;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { vaultId, metadataKey } = await getVaultKeys();
      const cols = await listCollections(vaultId);
      setRows(
        cols.map((c) => ({
          id: c.collectionId!,
          name: c.encryptedMetadata ? safeName(c.encryptedMetadata, metadataKey) : '(unreadable)',
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load collections');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function onCreate() {
    const name = window.prompt('Collection name')?.trim();
    if (!name) return;
    const { vaultId, metadataKey } = await getVaultKeys();
    await createCollection(vaultId, await encryptCollectionName(name, metadataKey));
    await load();
    onChanged?.();
  }

  async function onDelete(id: string) {
    const { vaultId } = await getVaultKeys();
    await deleteCollection(id, vaultId);
    if (selected.kind === 'collection' && selected.id === id) onSelect({ kind: 'all' });
    await load();
    onChanged?.();
  }

  return (
    <nav aria-label="collections">
      <button onClick={() => onSelect({ kind: 'all' })} aria-current={selected.kind === 'all'}>
        All files
      </button>
      <ul>
        {rows.map((r) => (
          <li key={r.id}>
            <button
              onClick={() => onSelect({ kind: 'collection', id: r.id, name: r.name })}
              aria-current={selected.kind === 'collection' && selected.id === r.id}
            >
              {r.name}
            </button>
            <button aria-label={`delete ${r.name}`} onClick={() => onDelete(r.id)}>
              ×
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onCreate}>+ New collection</button>
      {error && <p role="alert">{error}</p>}
    </nav>
  );
}

function safeName(blob: Uint8Array, metadataKey: Uint8Array): string {
  try {
    return decryptCollectionName(blob, metadataKey);
  } catch {
    return '(unreadable)';
  }
}
