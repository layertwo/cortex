import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import type { VaultEntry } from '../vault/registry';

// Held as a draft so a select-all-and-clear doesn't get refilled by the controlled
// registry value on every keystroke (it commits — and can be rejected — only on
// blur/Enter). `key={name}` at the call site resets the draft when the name changes
// from outside (e.g. a successful commit, or another tab renaming it).
function RenameField({ name, onCommit }: { name: string; onCommit: (name: string) => void }) {
  const [draft, setDraft] = useState(name);
  function commit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== name) onCommit(trimmed);
    else setDraft(name);
  }
  return (
    <TextInput
      label={`Rename ${name}`}
      isLabelHidden
      size="sm"
      width={200}
      value={draft}
      onChange={setDraft}
      onBlur={commit}
      onEnter={commit}
    />
  );
}

// Rename any vault (device-local until the backend stores names), unlock the locked ones,
// change the open vault's password. No delete in this pass (design follow-up 3).
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
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form" width={520}>
      <Layout
        height="auto"
        header={<DialogHeader title="Manage vaults" onOpenChange={() => onClose()} />}
        content={
          <LayoutContent>
            <VStack gap={3}>
              {vaults.map((v) => {
                const isOpen = v.vaultId === activeVault?.vaultId;
                return (
                  <HStack key={v.vaultId} gap={3} vAlign="end" wrap="wrap">
                    <RenameField key={v.name} name={v.name} onCommit={(name) => renameVault(v.vaultId, name)} />
                    <Text type="supporting">{isOpen ? 'Open' : 'Locked'}</Text>
                    {isOpen ? (
                      <Button label="Change password" size="sm" onClick={onChangePassword} />
                    ) : (
                      <Button label={`Unlock ${v.name}`} size="sm" onClick={() => onUnlock(v)} />
                    )}
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
  );
}
