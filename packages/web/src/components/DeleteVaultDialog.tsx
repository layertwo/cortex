import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession, DELETE_REFUSED } from '../auth/SessionContext';
import type { VaultEntry } from '../vault/registry';

const FORM_ID = 'delete-vault-form';

// Password-confirmed delete (spec §7). Astryx AlertDialog has no slot for the password
// field, so this composes Dialog + Layout with a destructive primary that never closes on
// its own. Every error stops the loop and stays visible; the primary then reads "Retry"
// (the server sweep is idempotent) except after a 409, which a retry cannot fix, or after
// the fail-closed refusal, which no retry on this device can fix.
export default function DeleteVaultDialog({ vault, onClose }: { vault: VaultEntry; onClose: () => void }) {
  const { deleteVault } = useSession();
  const [password, setPassword] = useState('');
  const [removed, setRemoved] = useState<number | null>(null); // non-null while deleting
  const [error, setError] = useState<{ message: string; retry: boolean } | null>(null);
  const pending = removed !== null;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setRemoved(0);
    try {
      await deleteVault(vault.vaultId, password, setRemoved);
      onClose();
    } catch (err) {
      const failure = err instanceof Error ? err : new Error('Delete failed');
      setRemoved(null);
      setError({
        message: failure.message,
        retry: failure.name !== 'ConflictError' && failure.message !== DELETE_REFUSED,
      });
    }
  }

  return (
    <Dialog isOpen onOpenChange={(open) => !open && !pending && onClose()} purpose="form">
      <Layout
        height="auto"
        header={<DialogHeader title={`Delete ${vault.name}`} onOpenChange={() => !pending && onClose()} />}
        content={
          <LayoutContent>
            <form id={FORM_ID} onSubmit={onSubmit}>
              <VStack gap={3}>
                <Text as="p" color="secondary">
                  Deletes every file, collection and share in this vault. This cannot be undone.
                </Text>
                <TextInput
                  label="Vault password"
                  type="password"
                  autoComplete="current-password"
                  hasAutoFocus
                  value={password}
                  onChange={setPassword}
                  isDisabled={pending}
                />
                {pending && <Text as="p">{`Deleting… ${removed} files removed`}</Text>}
                {error && <Banner status="error" title={error.message} />}
              </VStack>
            </form>
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              <Button label="Cancel" variant="ghost" onClick={onClose} isDisabled={pending} />
              <Button
                label={error?.retry ? 'Retry' : 'Delete vault'}
                variant="destructive"
                type="submit"
                form={FORM_ID}
                isDisabled={!password || pending}
              />
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
