import { useCallback, useEffect, useState } from 'react';
import { SideNav, SideNavHeading, SideNavItem, SideNavSection } from '@astryxdesign/core/SideNav';
import { Button } from '@astryxdesign/core/Button';
import { IconButton } from '@astryxdesign/core/IconButton';
import { Icon } from '@astryxdesign/core/Icon';
import { Banner } from '@astryxdesign/core/Banner';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { AlertDialog } from '@astryxdesign/core/AlertDialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { HStack } from '@astryxdesign/core/HStack';
import { VStack } from '@astryxdesign/core/VStack';
import { getVaultKeys } from '../vault/keyAccess';
import { listCollections, createCollection, deleteCollection } from '../api/collections';
import { encryptCollectionName, decryptCollectionName } from '../items/collectionMetadata';
import { useAsyncAction } from './common/useAsyncAction';

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
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const create = useAsyncAction();
  const [deleting, setDeleting] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);

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

  function closeCreate() {
    setCreating(false);
    setNewName('');
    create.setError('');
  }

  function onCreate() {
    const name = newName.trim();
    if (!name) return;
    void create.run(async () => {
      const { vaultId, metadataKey } = await getVaultKeys();
      await createCollection(vaultId, await encryptCollectionName(name, metadataKey));
      closeCreate();
      await load();
      onChanged?.();
    }, 'Could not create collection');
  }

  async function onDelete(row: Row) {
    setBusy(true);
    try {
      const { vaultId } = await getVaultKeys();
      await deleteCollection(row.id, vaultId);
      if (selected.kind === 'collection' && selected.id === row.id) onSelect({ kind: 'all' });
      await load();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete collection');
    } finally {
      // Close the confirmation either way so the sidebar banner is visible on failure.
      setDeleting(null);
      setBusy(false);
    }
  }

  return (
    <SideNav
      header={<SideNavHeading heading="Cortex" />}
      topContent={
        <Button label="New collection" size="sm" width="100%" onClick={() => setCreating(true)} />
      }
    >
      <SideNavItem
        label="All files"
        isSelected={selected.kind === 'all'}
        onClick={() => onSelect({ kind: 'all' })}
      />
      <SideNavSection title="Collections">
        {rows.map((r) => (
          <SideNavItem
            key={r.id}
            label={r.name}
            isSelected={selected.kind === 'collection' && selected.id === r.id}
            onClick={() => onSelect({ kind: 'collection', id: r.id, name: r.name })}
            actions={
              <IconButton
                label={`Delete ${r.name}`}
                tooltip="Delete"
                variant="ghost"
                icon={<Icon icon="close" />}
                onClick={() => setDeleting(r)}
              />
            }
          />
        ))}
      </SideNavSection>
      {error && <Banner status="error" title={error} />}

      <Dialog
        isOpen={creating}
        onOpenChange={(open) => {
          if (!open) closeCreate();
        }}
        purpose="form"
      >
        <Layout
          height="auto"
          header={<DialogHeader title="New collection" onOpenChange={() => closeCreate()} />}
          content={
            <LayoutContent>
              <VStack gap={3}>
                <TextInput
                  label="Collection name"
                  hasAutoFocus
                  value={newName}
                  onChange={setNewName}
                  onEnter={onCreate}
                />
                {create.error && <Banner status="error" title={create.error} />}
              </VStack>
            </LayoutContent>
          }
          footer={
            <LayoutFooter>
              <HStack gap={2} hAlign="end">
                <Button label="Cancel" variant="ghost" onClick={closeCreate} />
                <Button
                  label="Create"
                  variant="primary"
                  isLoading={create.pending}
                  isDisabled={!newName.trim()}
                  onClick={onCreate}
                />
              </HStack>
            </LayoutFooter>
          }
        />
      </Dialog>

      <AlertDialog
        isOpen={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title={`Delete "${deleting?.name ?? ''}"?`}
        description="Files in this collection stay in your vault."
        actionLabel="Delete collection"
        isActionLoading={busy}
        onAction={() => {
          if (deleting) void onDelete(deleting);
        }}
      />
    </SideNav>
  );
}

function safeName(blob: Uint8Array, metadataKey: Uint8Array): string {
  try {
    return decryptCollectionName(blob, metadataKey);
  } catch {
    return '(unreadable)';
  }
}
