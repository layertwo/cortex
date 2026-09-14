import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import PasswordStrength from './common/PasswordStrength';
import RecoveryPhrase from './common/RecoveryPhrase';
import { useAsyncAction } from './common/useAsyncAction';

const FORM_ID = 'new-vault-form';

// Create another vault from inside the app. Same two beats as first-run setup: name and
// password, then the recovery phrase. The session activates the new vault on success, so
// the dashboard behind switches to it when this closes.
export default function NewVaultDialog({ onClose }: { onClose: () => void }) {
  const { setupVault, activeVault } = useSession();
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [phrase, setPhrase] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const { pending, error, setError, run } = useAsyncAction();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError('Vault passwords do not match');
      return;
    }
    void run(async () => setPhrase(await setupVault(password, name)), 'Could not create vault');
  }

  const showingPhrase = phrase !== null;

  return (
    <Dialog isOpen onOpenChange={(open) => !open && !showingPhrase && onClose()} purpose={showingPhrase ? 'required' : 'form'} width={480}>
      <Layout
        height="auto"
        header={
          <DialogHeader
            title={showingPhrase ? `Recovery phrase for ${name.trim() || 'your vault'}` : 'New vault'}
            onOpenChange={showingPhrase ? undefined : () => onClose()}
          />
        }
        content={
          <LayoutContent>
            {showingPhrase ? (
              <VStack gap={3}>
                <Text as="p">Write these 24 words down. They are the only way back in if you forget this vault's password.</Text>
                <RecoveryPhrase
                  phrase={phrase}
                  kit={activeVault ? { name: activeVault.name, vaultId: activeVault.vaultId } : undefined}
                />
                <CheckboxInput label="I have saved my recovery phrase" value={saved} onChange={setSaved} />
              </VStack>
            ) : (
              <form id={FORM_ID} onSubmit={onSubmit}>
                <VStack gap={3}>
                  <Text as="p" color="secondary">
                    A separate space with its own password and recovery phrase. Files can't move between vaults.
                  </Text>
                  <TextInput label="Vault name" hasAutoFocus value={name} onChange={setName} />
                  <TextInput label="Vault password" type="password" autoComplete="new-password" value={password} onChange={setPassword} />
                  <PasswordStrength password={password} />
                  <TextInput
                    label="Confirm vault password"
                    type="password"
                    autoComplete="new-password"
                    value={confirm}
                    onChange={setConfirm}
                    status={confirm && confirm !== password ? { type: 'error' } : undefined}
                  />
                  {error && <Banner status="error" title={error} />}
                </VStack>
              </form>
            )}
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              {showingPhrase ? (
                <Button label="Done" variant="primary" isDisabled={!saved} onClick={onClose} />
              ) : (
                <>
                  <Button label="Cancel" variant="ghost" onClick={onClose} />
                  <Button
                    label="Create vault"
                    variant="primary"
                    type="submit"
                    form={FORM_ID}
                    isLoading={pending}
                    isDisabled={!name.trim() || !password || !confirm}
                  />
                </>
              )}
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
