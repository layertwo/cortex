import { useCallback, useEffect, useState } from 'react';
import { encryptTagForSearch } from '@cortex/encryption';
import { getVaultKeys } from '../vault/keyAccess';
import { listItems, getDownloadUrl, deleteItem, searchByTag, updateItemTags } from '../api/items';
import { getCollection, listCollections, addItemToCollection } from '../api/collections';
import { decryptMetadata, encryptMetadata, type FileMetadata } from '../items/metadata';
import { decryptDownloadedBlob } from '../items/itemCrypto';
import { decryptCollectionName } from '../items/collectionMetadata';
import { pickSink, downloadFileStreaming } from '../items/streamingDownload';
import type { View } from './CollectionSidebar';

interface Row {
  itemId: string;
  createdAt?: Date;
  meta: FileMetadata | null; // null = metadata failed to decrypt
}

export default function FileList({ view, refreshKey }: { view: View; refreshKey: number }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const { vaultId, metadataKey } = await getVaultKeys();
      // All three sources return ItemData[]; the view picks which.
      const items =
        view.kind === 'collection'
          ? await getCollection(view.id, vaultId)
          : view.kind === 'tag'
            ? await searchByTag(vaultId, view.encryptedTag)
            : await listItems(vaultId);
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
  }, [view]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function onDownload(row: Row) {
    if (!row.meta) return;
    setError('');
    try {
      // streamVersion is already known from the decrypted metadata — branch with
      // no await so the user gesture survives for showSaveFilePicker.
      if (row.meta.streamVersion === undefined) {
        // Legacy (pre-2.5c) whole-buffer object.
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
        return;
      }
      // Chunked stream: pick the sink FIRST (preserves the click's user activation).
      const sink = await pickSink(row.meta.name, row.meta.contentType);
      const { kek } = await getVaultKeys();
      await downloadFileStreaming(row.itemId, row.meta, kek, sink);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return; // user cancelled the save dialog
      setError(err instanceof Error ? err.message : 'Download failed');
    }
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
          {row.meta?.tags?.map((t) => (
            <span key={t} className="tag-chip"> #{t}</span>
          ))}
          {row.createdAt && <span> · {row.createdAt.toLocaleDateString()}</span>}
          <button onClick={() => onDownload(row)} disabled={!row.meta}>Download</button>
          <button onClick={() => onDelete(row.itemId)}>Delete</button>
          {row.meta && <AddToCollection itemId={row.itemId} onChanged={load} />}
          {row.meta && <EditTags itemId={row.itemId} meta={row.meta} onChanged={load} />}
        </li>
      ))}
    </ul>
  );
}

function AddToCollection({ itemId, onChanged }: { itemId: string; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [cols, setCols] = useState<{ id: string; name: string }[]>([]);

  async function openMenu() {
    const { vaultId, metadataKey } = await getVaultKeys();
    const list = await listCollections(vaultId);
    setCols(
      list.map((c) => ({
        id: c.collectionId!,
        name: c.encryptedMetadata ? tryName(c.encryptedMetadata, metadataKey) : '(unreadable)',
      })),
    );
    setOpen(true);
  }

  async function add(collectionId: string) {
    const { vaultId } = await getVaultKeys();
    await addItemToCollection(collectionId, vaultId, itemId);
    setOpen(false);
    onChanged();
  }

  return (
    <span>
      <button onClick={openMenu}>Add to collection</button>
      {open && (
        <ul role="menu">
          {cols.map((c) => (
            <li key={c.id}>
              <button role="menuitem" onClick={() => add(c.id)}>{c.name}</button>
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}

// Edit an existing item's tags. Rewrites the readable copy (metadata) and the
// one-way HMAC search index together — same dual-write as upload, so the index
// never drifts from the chips. An empty result sends encryptedTags: [], which the
// backend reads as "clear all tags" (a present-but-empty list, not an absent field).
function EditTags({
  itemId,
  meta,
  onChanged,
}: {
  itemId: string;
  meta: FileMetadata;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState((meta.tags ?? []).join(', '));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function save() {
    setBusy(true);
    setErr('');
    try {
      const { vaultId, metadataKey } = await getVaultKeys();
      const tags = value.split(',').map((t) => t.trim()).filter(Boolean);
      const updated: FileMetadata = { ...meta };
      if (tags.length) updated.tags = tags;
      else delete updated.tags;
      const encryptedMetadata = await encryptMetadata(updated, metadataKey);
      const encryptedTags = tags.map((t) => encryptTagForSearch(t, metadataKey, vaultId));
      await updateItemTags(itemId, encryptedMetadata, encryptedTags);
      setOpen(false);
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setBusy(false);
    }
  }

  if (!open) return <button onClick={() => setOpen(true)}>Edit tags</button>;
  return (
    <span>
      <input
        aria-label="edit tags"
        value={value}
        placeholder="tags, comma separated"
        onChange={(e) => setValue(e.target.value)}
      />
      <button onClick={save} disabled={busy}>Save</button>
      <button
        onClick={() => {
          setValue((meta.tags ?? []).join(', '));
          setErr('');
          setOpen(false);
        }}
        disabled={busy}
      >
        Cancel
      </button>
      {err && <span role="alert"> {err}</span>}
    </span>
  );
}

function tryName(blob: Uint8Array, metadataKey: Uint8Array): string {
  try {
    return decryptCollectionName(blob, metadataKey);
  } catch {
    return '(unreadable)';
  }
}
