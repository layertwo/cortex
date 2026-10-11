import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { ProgressBar } from '@astryxdesign/core/ProgressBar';
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { ROTATION_INCOMPLETE, useSession } from '../auth/SessionContext';
import RecoveryPhrase from './common/RecoveryPhrase';

type Stage = 'form' | 'sweep' | 'phrase';

const TITLES: Record<Stage, string> = {
  form: 'Rotate encryption keys',
  sweep: 'Rotating encryption keys…',
  phrase: 'Save your new recovery phrase',
};

const FORM_ID = 'rotate-keys-form';

// A deliberate, rare action: mint a new vault master key and re-wrap every file's key onto it.
// The password is re-entered as a confirmation gate. Rendered as an always-open dialog.
export default function RotateKeysDialog({ onDone }: { onDone: () => void }) {
  const { rotateEncryptionKeys } = useSession();
  const [stage, setStage] = useState<Stage>('form');
  const [password, setPassword] = useState('');
  const [phrase, setPhrase] = useState('');
  const [saved, setSaved] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setStage('sweep');
    try {
      setPhrase(await rotateEncryptionKeys(password, (done, total) => setProgress({ done, total })));
      setStage('phrase');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Key rotation failed';
      // A straggler left the rotation IN_PROGRESS and resumable: surface that plainly.
      setError(message === ROTATION_INCOMPLETE ? `${message}. Try again to finish it.` : message);
      setStage('form');
    }
  }

  const dismissable = stage === 'form' || (stage === 'phrase' && saved);

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => !open && dismissable && onDone()}
      purpose={dismissable ? 'form' : 'required'}
      width={480}
    >
      <Layout
        height="auto"
        header={<DialogHeader title={TITLES[stage]} onOpenChange={dismissable ? () => onDone() : undefined} />}
        content={
          <LayoutContent>
            {stage === 'form' && (
              <form id={FORM_ID} onSubmit={handleSubmit}>
                <VStack gap={3}>
                  <Text as="p">
                    This generates a brand-new vault master key and re-wraps every file's key onto it. Your old
                    recovery phrase stops working, and you'll get a new one. Your current password stays the same.
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
                </VStack>
              </form>
            )}
            {stage === 'sweep' && (
              <VStack gap={3}>
                <Text as="p">Keep this tab open — you can safely resume if interrupted.</Text>
                <ProgressBar
                  label="Re-keying files"
                  value={progress.done}
                  max={Math.max(progress.total, 1)}
                  isIndeterminate={progress.total === 0}
                  hasValueLabel
                  formatValueLabel={(v, m) => `${v} of ${m}`}
                />
              </VStack>
            )}
            {stage === 'phrase' && (
              <VStack gap={3}>
                <Text as="p">
                  Your old recovery phrase no longer works. Save this new one before continuing.
                </Text>
                <RecoveryPhrase phrase={phrase} />
                <CheckboxInput label="I have saved my new recovery phrase" value={saved} onChange={setSaved} />
              </VStack>
            )}
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              {stage === 'form' && <Button label="Cancel" variant="ghost" onClick={onDone} />}
              {stage === 'form' && (
                <Button label="Rotate keys" variant="primary" type="submit" form={FORM_ID} isDisabled={!password} />
              )}
              {stage === 'phrase' && (
                <Button label="Done" variant="primary" isDisabled={!saved} onClick={onDone} />
              )}
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
