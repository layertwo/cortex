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
import { useAsyncAction } from './common/useAsyncAction';

// The footer submit lives outside the <form>; `form={FORM_ID}` associates it so Enter
// and click both submit.
const FORM_ID = 'change-account-password-form';

// Rendered as an always-open dialog; the parent mounts it to open and calls onDone to close.
export default function ChangeAccountPassword({ onDone }: { onDone: () => void }) {
  const { changeAccountPassword } = useSession();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [changed, setChanged] = useState(false);
  const { pending, error, setError, run } = useAsyncAction();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (next !== confirm) {
      setError('Passwords do not match');
      return;
    }
    void run(async () => {
      await changeAccountPassword(current, next);
      setChanged(true);
    }, 'Could not change the account password');
  }

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => {
        if (!open && !pending) onDone();
      }}
      purpose="form"
      width={480}
    >
      <Layout
        height="auto"
        header={
          <DialogHeader
            title="Change account password"
            onOpenChange={() => {
              if (!pending) onDone();
            }}
          />
        }
        content={
          <LayoutContent>
            {changed ? (
              <Banner
                status="success"
                title="Account password changed"
                description="Your vault password and encryption keys are unchanged."
              />
            ) : (
              <form id={FORM_ID} onSubmit={handleSubmit}>
                <VStack gap={3}>
                  <Text as="p" type="supporting">
                    This changes your sign-in password only. Your vault password and files are
                    not affected.
                  </Text>
                  <TextInput
                    label="Current account password"
                    type="password"
                    autoComplete="current-password"
                    hasAutoFocus
                    value={current}
                    onChange={setCurrent}
                  />
                  <TextInput
                    label="New account password"
                    type="password"
                    autoComplete="new-password"
                    value={next}
                    onChange={setNext}
                  />
                  <TextInput
                    label="Confirm new account password"
                    type="password"
                    autoComplete="new-password"
                    value={confirm}
                    onChange={setConfirm}
                    status={confirm && confirm !== next ? { type: 'error' } : undefined}
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
              {changed ? (
                <Button label="Done" variant="primary" onClick={onDone} />
              ) : (
                <>
                  <Button label="Cancel" variant="ghost" isDisabled={pending} onClick={onDone} />
                  <Button
                    label="Change account password"
                    variant="primary"
                    type="submit"
                    form={FORM_ID}
                    isLoading={pending}
                    isDisabled={!current || !next || !confirm}
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
