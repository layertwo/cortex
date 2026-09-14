import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import type { VaultEntry } from '../vault/registry';
import { useAsyncAction } from './common/useAsyncAction';

const FORM_ID = 'unlock-vault-form';

// In-place unlock for switching to a vault whose keys are not on this device yet.
export default function UnlockVaultDialog({
  vault,
  onClose,
}: {
  vault: VaultEntry;
  onClose: () => void;
}) {
  const { unlockVault } = useSession();
  const [password, setPassword] = useState('');
  const { pending, error, run } = useAsyncAction();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await unlockVault(password, vault.vaultId);
      onClose();
    }, 'Unlock failed');
  }

  return (
    <Dialog isOpen onOpenChange={(open) => !open && onClose()} purpose="form">
      <Layout
        height="auto"
        header={<DialogHeader title={`Unlock ${vault.name}`} onOpenChange={() => onClose()} />}
        content={
          <LayoutContent>
            <form id={FORM_ID} onSubmit={onSubmit}>
              <VStack gap={3}>
                <Text as="p" color="secondary">
                  This vault has its own password. Enter it to switch.
                </Text>
                <TextInput
                  label="Vault password"
                  type="password"
                  autoComplete="current-password"
                  hasAutoFocus
                  value={password}
                  onChange={setPassword}
                />
                {error && <Banner status="error" title={error} />}
                <Link href="/vault/recover" isStandalone>
                  Forgot your vault password?
                </Link>
              </VStack>
            </form>
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              <Button label="Cancel" variant="ghost" onClick={onClose} />
              <Button label="Unlock and switch" variant="primary" type="submit" form={FORM_ID} isLoading={pending} isDisabled={!password} />
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
