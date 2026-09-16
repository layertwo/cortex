import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Text } from '@astryxdesign/core/Text';
import { Banner } from '@astryxdesign/core/Banner';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import type { VaultEntry } from '../vault/registry';
import DeleteVaultDialog from './DeleteVaultDialog';

// Held as a draft so a select-all-and-clear doesn't get refilled by the controlled
// registry value on every keystroke (it commits, and can be rejected, only on
// blur/Enter). `key={name}` at the call site resets the draft when the name changes
// from outside (e.g. a successful commit, or another tab renaming it). A locked vault
// cannot be renamed: the name is encrypted under keys this device does not hold.
function RenameField({
  name,
  isLocked,
  onCommit,
}: {
  name: string;
  isLocked: boolean;
  onCommit: (name: string) => void;
}) {
  const [draft, setDraft] = useState(name);
  function commit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== name) onCommit(trimmed);
    else setDraft(name);
  }
  return (
    <VStack gap={0.5}>
      <TextInput
        label={`Rename ${name}`}
        isLabelHidden
        size="sm"
        width={200}
        isDisabled={isLocked}
        value={draft}
        onChange={setDraft}
        onBlur={commit}
        onEnter={commit}
      />
      {/* Astryx's TextInput forwards `description` into a screen-reader-only span whenever
          isLabelHidden is set (dist/Field/FieldLabel.js), so the hint must be a plain visible
          sibling instead, not the `description` prop. */}
      {isLocked && <Text type="supporting">Unlock to rename</Text>}
    </VStack>
  );
}

// Rename the open vault, unlock the locked ones, change the open vault's password, or delete
// a vault after confirming its password in DeleteVaultDialog (spec §7).
export default function ManageVaultsDialog({
  onClose,
  onUnlock,
  onChangePassword,
  onNew,
}: {
  onClose: () => void;
  onUnlock: (vault: VaultEntry) => void;
  onChangePassword: () => void;
  onNew: () => void;
}) {
  const { vaults, activeVault, renameVault } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<VaultEntry | null>(null);
  function rename(vaultId: string, name: string) {
    setError(null);
    renameVault(vaultId, name).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }
  return (
    <>
      <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={520}>
        <Layout
          height="auto"
          header={<DialogHeader title="Manage vaults" onOpenChange={() => onClose()} />}
          content={
            <LayoutContent>
              <VStack gap={3}>
                {error && <Banner status="error" title={error} />}
                {vaults.map((v) => {
                  const isOpen = v.vaultId === activeVault?.vaultId;
                  return (
                    <HStack key={v.vaultId} gap={3} vAlign="end" wrap="wrap">
                      <RenameField key={v.name} name={v.name} isLocked={!isOpen} onCommit={(name) => rename(v.vaultId, name)} />
                      <Text type="supporting">{isOpen ? 'Open' : 'Locked'}</Text>
                      {isOpen ? (
                        <Button label="Change password" size="sm" onClick={onChangePassword} />
                      ) : (
                        <Button label={`Unlock ${v.name}`} size="sm" onClick={() => onUnlock(v)} />
                      )}
                      <Button label={`Delete ${v.name}`} size="sm" variant="ghost" onClick={() => setDeleting(v)} />
                    </HStack>
                  );
                })}
              </VStack>
            </LayoutContent>
          }
          footer={
            <LayoutFooter>
              <HStack gap={2} hAlign="between">
                <Button label="New vault" variant="ghost" onClick={onNew} />
                <Button label="Done" variant="primary" onClick={onClose} />
              </HStack>
            </LayoutFooter>
          }
        />
      </Dialog>
      {deleting && <DeleteVaultDialog vault={deleting} onClose={() => setDeleting(null)} />}
    </>
  );
}
