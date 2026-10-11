import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';

// The submit button lives in the dialog footer, outside the <form>; `form={FORM_ID}`
// associates it with the form so Enter and click both submit.
const FORM_ID = 'change-vault-password-form';

// A pure re-wrap of the vault's VMK envelopes: no file sweep and no new recovery phrase. Rendered
// as an always-open dialog; the parent mounts it to open and calls onDone to close.
export default function ChangeVaultPassword({ onDone }: { onDone: () => void }) {
  const { changeVaultPassword } = useSession();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (next !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setPending(true);
    try {
      await changeVaultPassword(current, next);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password change failed');
      setPending(false);
    }
  }

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => !open && !pending && onDone()}
      purpose={pending ? 'required' : 'form'}
      width={480}
    >
      <Layout
        height="auto"
        header={<DialogHeader title="Change vault password" onOpenChange={pending ? undefined : () => onDone()} />}
        content={
          <LayoutContent>
            <form id={FORM_ID} onSubmit={handleSubmit}>
              <VStack gap={3}>
                <Text as="p">
                  Your files stay encrypted as they are. This only changes the password that opens your vault;
                  your recovery phrase stays the same.
                </Text>
                <TextInput
                  label="Current vault password"
                  type="password"
                  autoComplete="current-password"
                  hasAutoFocus
                  value={current}
                  onChange={setCurrent}
                  isDisabled={pending}
                />
                <TextInput
                  label="New vault password"
                  type="password"
                  autoComplete="new-password"
                  value={next}
                  onChange={setNext}
                  isDisabled={pending}
                />
                <TextInput
                  label="Confirm new password"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={setConfirm}
                  isDisabled={pending}
                  status={confirm && confirm !== next ? { type: 'error' } : undefined}
                />
                {error && <Banner status="error" title={error} />}
              </VStack>
            </form>
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              <Button label="Cancel" variant="ghost" onClick={onDone} isDisabled={pending} />
              <Button
                label="Change password"
                variant="primary"
                type="submit"
                form={FORM_ID}
                isDisabled={!current || !next || !confirm || pending}
              />
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
