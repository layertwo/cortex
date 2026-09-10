import { useState } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { ProgressBar } from '@astryxdesign/core/ProgressBar';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import RecoveryPhrase from './common/RecoveryPhrase';

type Stage = 'form' | 'sweep' | 'phrase';

const TITLES: Record<Stage, string> = {
  form: 'Change vault password',
  sweep: 'Changing vault password…',
  phrase: 'Save your new recovery phrase',
};

// The submit button lives in the dialog footer, outside the <form>; `form={FORM_ID}`
// associates it with the form so Enter and click both submit.
const FORM_ID = 'change-vault-password-form';

// Tolerates extra/collapsed whitespace between words so a re-typed phrase compares equal
// to the original even if the user's spacing doesn't match exactly.
const normalize = (s: string) => s.trim().split(/\s+/).join(' ');

// Rendered as an always-open dialog; the parent mounts it to open and calls onDone to
// close. Once the sweep starts the dialog cannot be dismissed (purpose="required").
export default function ChangeVaultPassword({ onDone }: { onDone: () => void }) {
  const { changeVaultPassword } = useSession();
  const [stage, setStage] = useState<Stage>('form');
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [phrase, setPhrase] = useState('');
  const [phraseInput, setPhraseInput] = useState('');
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (next !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setStage('sweep');
    try {
      const newPhrase = await changeVaultPassword(current, next, (done, total) =>
        setProgress({ done, total }),
      );
      setPhrase(newPhrase);
      setStage('phrase');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password change failed');
      setStage('form');
    }
  }

  function handleComplete() {
    if (normalize(phraseInput) !== normalize(phrase)) {
      setError('Recovery phrase does not match — copy it exactly');
      return;
    }
    onDone();
  }

  const dismissable = stage === 'form';

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => {
        if (!open && dismissable) onDone();
      }}
      purpose={dismissable ? 'form' : 'required'}
      width={480}
    >
      <Layout
        height="auto"
        header={
          <DialogHeader title={TITLES[stage]} onOpenChange={dismissable ? () => onDone() : undefined} />
        }
        content={
          <LayoutContent>
            {stage === 'form' && (
              <form id={FORM_ID} onSubmit={handleSubmit}>
                <VStack gap={3}>
                  <TextInput
                    label="Current vault password"
                    type="password"
                    autoComplete="current-password"
                    hasAutoFocus
                    value={current}
                    onChange={setCurrent}
                  />
                  <TextInput
                    label="New vault password"
                    type="password"
                    autoComplete="new-password"
                    value={next}
                    onChange={setNext}
                  />
                  <TextInput
                    label="Confirm new password"
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
            {stage === 'sweep' && (
              <VStack gap={3}>
                <Text as="p">Keep this tab open — you can safely resume if interrupted.</Text>
                <ProgressBar
                  label="Re-encrypting files"
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
                <TextInput
                  label="Type your new recovery phrase to confirm"
                  value={phraseInput}
                  onChange={setPhraseInput}
                />
                {error && <Banner status="error" title={error} />}
              </VStack>
            )}
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              {stage === 'form' && <Button label="Cancel" variant="ghost" onClick={onDone} />}
              {stage === 'form' && (
                <Button
                  label="Change password"
                  variant="primary"
                  type="submit"
                  form={FORM_ID}
                  isDisabled={!current || !next || !confirm}
                />
              )}
              {stage === 'phrase' && (
                <Button label="Complete password change" variant="primary" onClick={handleComplete} />
              )}
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
