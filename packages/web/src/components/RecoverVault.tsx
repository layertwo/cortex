import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { ProgressBar } from '@astryxdesign/core/ProgressBar';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useSession } from '../auth/SessionContext';
import { identifyVaultForPhrase, normalizePhrase, PHRASE_ERROR } from '../vault/recovery';
import { parseRecoveryKit } from '../vault/recoveryKit';
import AuthFrame from './common/AuthFrame';
import PhraseInput, { PHRASE_LENGTH } from './common/PhraseInput';
import PasswordStrength from './common/PasswordStrength';
import RecoveryPhrase from './common/RecoveryPhrase';
import SubmitButton from './common/SubmitButton';

const STEPS = ['Phrase', 'New password', 'New phrase'] as const;
type Stage = 'phrase' | 'password' | 'sweep' | 'done';

// Forgot the vault password: prove ownership with the 24 words, pick a new password, let the
// sweep re-wrap every file, leave with a new phrase. Works on this device (the vault is found
// from local verifiers) or on a new one (a recovery kit supplies the vault ID).
export default function RecoverVault() {
  const { recoverVault, vaults } = useSession();
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>('phrase');
  const [words, setWords] = useState<string[]>(Array(PHRASE_LENGTH).fill(''));
  const [target, setTarget] = useState<{ vaultId: string; name?: string } | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [result, setResult] = useState<{ phrase: string; vaultId: string; name: string } | null>(null);
  const [replaced, setReplaced] = useState(false);
  const [error, setError] = useState('');
  const kitInput = useRef<HTMLInputElement>(null);

  const filled = words.filter(Boolean).length;
  const phrase = normalizePhrase(words);
  const targetName = target?.name ?? vaults.find((v) => v.vaultId === target?.vaultId)?.name;

  function onContinue() {
    setError('');
    if (target) {
      setStage('password');
      return;
    }
    const found = identifyVaultForPhrase(phrase, vaults.map((v) => v.vaultId));
    if (!found) {
      setError(PHRASE_ERROR);
      return;
    }
    setTarget({ vaultId: found });
    setStage('password');
  }

  async function onKit(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    try {
      const kit = parseRecoveryKit(await file.text());
      setWords(kit.words);
      setTarget({ vaultId: kit.vaultId, name: kit.name });
      setError('');
    } catch {
      setError("That file isn't a Cortex recovery kit.");
    }
  }

  async function onSetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Vault passwords do not match');
      return;
    }
    setStage('sweep');
    try {
      setResult(await recoverVault(phrase, password, (done, total) => setProgress({ done, total }), target ?? undefined));
      setStage('done');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Recovery failed';
      setError(message);
      setStage(message === PHRASE_ERROR ? 'phrase' : 'password');
    }
  }

  if (stage === 'done' && result) {
    return (
      <AuthFrame
        title="Your new recovery phrase"
        description="The old 24 words no longer work. Replace them wherever you kept them."
        rail={{ steps: STEPS, active: 2 }}
      >
        <RecoveryPhrase phrase={result.phrase} kit={{ name: result.name, vaultId: result.vaultId }} />
        <CheckboxInput label="I've replaced my old phrase" value={replaced} onChange={setReplaced} />
        <Button label="Open my vault" variant="primary" width="100%" isDisabled={!replaced} onClick={() => navigate('/')} />
      </AuthFrame>
    );
  }

  if (stage === 'sweep') {
    return (
      <AuthFrame
        title={`Re-securing ${targetName ?? 'your vault'}`}
        description="Every file's key is being re-wrapped with your new password. Keep this tab open."
        rail={{ steps: STEPS, active: 2 }}
      >
        <ProgressBar
          label="Re-encrypting files"
          value={progress.done}
          max={Math.max(progress.total, 1)}
          isIndeterminate={progress.total === 0}
          hasValueLabel
          formatValueLabel={(v, m) => `${v} of ${m}`}
        />
        <Text as="p" type="supporting">
          If this is interrupted you can resume it the next time you unlock. Nothing is lost part-way.
        </Text>
      </AuthFrame>
    );
  }

  if (stage === 'password') {
    // A kit identified a vault this device has no local record of: there was nothing to
    // prove the phrase against, so the acceptance above is unverified. Say so — the spec's
    // Risks section requires it, and re-securing an empty vault with a wrong phrase is
    // otherwise a silent no-op the user was never told about.
    const unverified = !!target && !vaults.some((v) => v.vaultId === target.vaultId);
    return (
      <AuthFrame title="Choose a new vault password" rail={{ steps: STEPS, active: 1 }}>
        <Banner status="success" title={`Phrase accepted. It opens ${targetName ?? 'this vault'}.`} />
        {unverified && (
          <Text as="p" type="supporting">
            If this vault has no files yet, we can't confirm the phrase; continuing will re-secure it with your new
            password.
          </Text>
        )}
        <form onSubmit={onSetPassword}>
          <VStack gap={3}>
            <TextInput
              label="New vault password"
              type="password"
              autoComplete="new-password"
              hasAutoFocus
              value={password}
              onChange={setPassword}
            />
            <PasswordStrength password={password} />
            <TextInput
              label="Confirm new vault password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={setConfirm}
              status={confirm && confirm !== password ? { type: 'error' } : undefined}
            />
            <Text as="p" type="supporting">
              Your old vault password stops working, and so does the old phrase. You'll get a new phrase on the
              next screen. Your files stay encrypted the whole time.
            </Text>
            {error && <Banner status="error" title={error} />}
            <SubmitButton label="Set password and re-secure" isDisabled={!password || !confirm} />
          </VStack>
        </form>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Enter your 24 words"
      description="Type them in order, or paste the whole phrase into the first box."
      rail={{ steps: STEPS, active: 0 }}
    >
      <PhraseInput words={words} onChange={setWords} />
      {error && <Banner status="error" title={error} />}
      <Button
        label={`Continue · ${filled} of ${PHRASE_LENGTH}`}
        variant="primary"
        width="100%"
        isDisabled={filled < PHRASE_LENGTH}
        onClick={onContinue}
      />
      <Button label="Use a recovery kit file" variant="ghost" size="sm" onClick={() => kitInput.current?.click()} />
      <input ref={kitInput} type="file" accept=".txt,text/plain" hidden aria-label="Recovery kit file" onChange={onKit} />
      {targetName && (
        <Text as="p" type="supporting">
          Recovery kit loaded for {targetName}.
        </Text>
      )}
    </AuthFrame>
  );
}
