import { useCallback, useEffect, useState } from 'react';
import { encryptTagForSearch } from '@cortex/encryption';
import { Table, proportional, pixel, type TableColumn } from '@astryxdesign/core/Table';
import { MoreMenu } from '@astryxdesign/core/MoreMenu';
import { Token } from '@astryxdesign/core/Token';
import { Text } from '@astryxdesign/core/Text';
import { HStack } from '@astryxdesign/core/HStack';
import { VStack } from '@astryxdesign/core/VStack';
import { EmptyState } from '@astryxdesign/core/EmptyState';
import { Banner } from '@astryxdesign/core/Banner';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { AlertDialog } from '@astryxdesign/core/AlertDialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { getVaultKeys } from '../vault/keyAccess';
import { listItems, deleteItem, searchByTag, updateItemTags } from '../api/items';
import { getCollection, listCollections, addItemToCollection } from '../api/collections';
import { decryptMetadata, encryptMetadata, type FileMetadata } from '../items/metadata';
import { decryptCollectionName } from '../items/collectionMetadata';
import { pickSink, downloadFileStreaming } from '../items/streamingDownload';
import { formatBytes } from './common/formatBytes';
import { useAsyncAction } from './common/useAsyncAction';
import type { View } from './CollectionSidebar';

// Astryx's data-driven Table requires row types to extend Record<string, unknown>.
interface Row extends Record<string, unknown> {
  itemId: string;
  createdAt?: Date;
  meta: FileMetadata | null; // null = metadata failed to decrypt
  wrappedDek?: Uint8Array; // per-file wrapped DEK (MEDIA), from the item record
}

type Collection = { id: string; name: string };

const UNREADABLE = '(unreadable)';

export default function FileList({ view, refreshKey }: { view: View; refreshKey: number }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Row | null>(null);
  const [deleting, setDeleting] = useState<Row | null>(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const { vaultId, metadataKey } = await getVaultKeys();
      // All three sources return ItemData[]; the view picks which. Collections load
      // alongside so the row menu's "Add to collection" list is ready when it opens.
      const [items, cols] = await Promise.all([
        view.kind === 'collection'
          ? getCollection(view.id, vaultId)
          : view.kind === 'tag'
            ? searchByTag(vaultId, view.encryptedTag)
            : listItems(vaultId),
        listCollections(vaultId).catch(() => []),
      ]);
      setRows(
        items.map((it) => {
          let meta: FileMetadata | null = null;
          try {
            if (it.encryptedMetadata) meta = decryptMetadata(it.encryptedMetadata, metadataKey);
          } catch {
            // metadata won't decrypt → show the row as unreadable
          }
          return { itemId: it.itemId!, createdAt: it.createdAt, meta, wrappedDek: it.wrappedDek };
        }),
      );
      setCollections(
        cols.map((c) => ({
          id: c.collectionId!,
          name: c.encryptedMetadata ? tryName(c.encryptedMetadata, metadataKey) : UNREADABLE,
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load files');
    }
  }, [view]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function onDownload(row: Row) {
    if (!row.meta || !row.wrappedDek) return;
    setError('');
    try {
      // Pick the sink FIRST (preserves the click's user activation for showSaveFilePicker).
      const sink = await pickSink(row.meta.name, row.meta.contentType);
      const { kek } = await getVaultKeys();
      await downloadFileStreaming(row.itemId, row.meta, row.wrappedDek, kek, sink);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return; // user cancelled the save dialog
      setError(err instanceof Error ? err.message : 'Download failed');
    }
  }

  async function onDelete(row: Row) {
    try {
      await deleteItem(row.itemId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeleting(null);
    }
  }

  async function addToCollection(row: Row, collectionId: string) {
    try {
      const { vaultId } = await getVaultKeys();
      await addItemToCollection(collectionId, vaultId, row.itemId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add to collection');
    }
  }

  const nameOf = (row: Row) => row.meta?.name ?? UNREADABLE;

  const columns: TableColumn<Row>[] = [
    {
      key: 'name',
      header: 'Name',
      width: proportional(3),
      renderCell: (row) =>
        row.meta ? <Text>{row.meta.name}</Text> : <Text color="secondary">{UNREADABLE}</Text>,
    },
    {
      key: 'size',
      header: 'Size',
      width: pixel(110),
      renderCell: (row) => (row.meta ? <Text hasTabularNumbers>{formatBytes(row.meta.size)}</Text> : null),
    },
    {
      key: 'tags',
      header: 'Tags',
      width: proportional(2),
      renderCell: (row) => (
        <HStack gap={1} wrap="wrap">
          {(row.meta?.tags ?? []).map((t) => (
            <Token key={t} label={t} size="sm" />
          ))}
        </HStack>
      ),
    },
    {
      key: 'createdAt',
      header: 'Uploaded',
      width: pixel(130),
      renderCell: (row) => <Text type="supporting">{row.createdAt?.toLocaleDateString()}</Text>,
    },
    {
      key: 'actions',
      header: '',
      width: pixel(56),
      align: 'end',
      renderCell: (row) => (
        <MoreMenu
          label={`Actions for ${nameOf(row)}`}
          size="sm"
          alignment="end"
          items={[
            {
              label: 'Download',
              isDisabled: !row.meta || !row.wrappedDek,
              onClick: () => void onDownload(row),
            },
            {
              label: 'Add to collection',
              isDisabled: !row.meta || collections.length === 0,
              items: collections.map((c) => ({
                id: c.id,
                label: c.name,
                onClick: () => void addToCollection(row, c.id),
              })),
            },
            { label: 'Edit tags', isDisabled: !row.meta, onClick: () => setEditing(row) },
            { type: 'divider' },
            { label: 'Delete', variant: 'destructive', onClick: () => setDeleting(row) },
          ]}
        />
      ),
    },
  ];

  if (error && rows.length === 0) return <Banner status="error" title={error} />;
  if (rows.length === 0) {
    return <EmptyState title="No files yet" description="Upload a file to get started." />;
  }

  return (
    <VStack gap={2}>
      {error && <Banner status="error" title={error} />}
      <Table aria-label="Files" data={rows} columns={columns} idKey="itemId" hasHover />
      {editing?.meta && (
        <EditTagsDialog
          itemId={editing.itemId}
          meta={editing.meta}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void load();
          }}
        />
      )}
      <AlertDialog
        isOpen={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title={`Delete "${deleting ? nameOf(deleting) : ''}"?`}
        description="The file is permanently removed from your vault. This cannot be undone."
        actionLabel="Delete file"
        onAction={() => {
          if (deleting) void onDelete(deleting);
        }}
      />
    </VStack>
  );
}

// Edit an existing item's tags. Rewrites the readable copy (metadata) and the
// one-way HMAC search index together — same dual-write as upload, so the index
// never drifts from the chips. An empty result sends encryptedTags: [], which the
// backend reads as "clear all tags" (a present-but-empty list, not an absent field).
function EditTagsDialog({
  itemId,
  meta,
  onClose,
  onSaved,
}: {
  itemId: string;
  meta: FileMetadata;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [value, setValue] = useState((meta.tags ?? []).join(', '));
  const { pending, error: err, run } = useAsyncAction();

  function save() {
    void run(async () => {
      const { vaultId, metadataKey } = await getVaultKeys();
      const tags = value.split(',').map((t) => t.trim()).filter(Boolean);
      // tags: undefined drops the key on JSON.stringify (encryptMetadata) when empty.
      const updated: FileMetadata = { ...meta, tags: tags.length ? tags : undefined };
      const encryptedMetadata = await encryptMetadata(updated, metadataKey);
      const encryptedTags = tags.map((t) => encryptTagForSearch(t, metadataKey, vaultId));
      await updateItemTags(itemId, encryptedMetadata, encryptedTags);
      onSaved();
    }, 'Save failed');
  }

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      purpose="form"
    >
      <Layout
        height="auto"
        header={<DialogHeader title="Edit tags" onOpenChange={() => onClose()} />}
        content={
          <LayoutContent>
            <VStack gap={3}>
              <TextInput
                label="Edit tags"
                description="Comma separated"
                hasAutoFocus
                value={value}
                onChange={setValue}
                onEnter={save}
              />
              {err && <Banner status="error" title={err} />}
            </VStack>
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              <Button label="Cancel" variant="ghost" onClick={onClose} />
              <Button label="Save" variant="primary" isLoading={pending} onClick={save} />
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}

function tryName(blob: Uint8Array, metadataKey: Uint8Array): string {
  try {
    return decryptCollectionName(blob, metadataKey);
  } catch {
    return UNREADABLE;
  }
}
