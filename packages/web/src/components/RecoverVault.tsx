import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useSession } from '../auth/SessionContext';
import { identifyVaultForPhrase, normalizePhrase, PHRASE_ERROR } from '../vault/recovery';
import { parseRecoveryKit } from '../vault/recoveryKit';
import AuthFrame from './common/AuthFrame';
import PhraseInput, { PHRASE_LENGTH } from './common/PhraseInput';
import PasswordStrength from './common/PasswordStrength';
import SubmitButton from './common/SubmitButton';

const STEPS = ['Phrase', 'New password'] as const;
type Stage = 'phrase' | 'password' | 'done';

// Forgot the vault password: prove ownership with the 24 words, then set a new password. The
// phrase encodes the VMK, so it is unchanged: only the password that wraps it changes. Works on
// this device (the vault is identified from its encrypted name) or on a new one (a recovery kit
// supplies the vault ID).
export default function RecoverVault() {
  const { recoverVault, vaults } = useSession();
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>('phrase');
  const [words, setWords] = useState<string[]>(Array(PHRASE_LENGTH).fill(''));
  const [target, setTarget] = useState<{ vaultId: string; name?: string } | null>(null);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [done, setDone] = useState<{ vaultId: string; name: string } | null>(null);
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
    const found = identifyVaultForPhrase(
      phrase,
      vaults.map((v) => ({ vaultId: v.vaultId, encryptedName: v.encryptedName })),
    );
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
    try {
      const result = await recoverVault(phrase, password, target ?? undefined);
      setDone({ vaultId: result.vaultId, name: result.name });
      setStage('done');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Recovery failed';
      setError(message);
      setStage(message === PHRASE_ERROR ? 'phrase' : 'password');
    }
  }

  if (stage === 'done' && done) {
    return (
      <AuthFrame
        title="Your vault is restored"
        description="Your recovery phrase is unchanged — keep the same 24 words where you had them."
        rail={{ steps: STEPS, active: 1 }}
      >
        <Banner status="success" title={`You can now open ${done.name}.`} />
        <Button label="Open my vault" variant="primary" width="100%" onClick={() => navigate('/')} />
      </AuthFrame>
    );
  }

  if (stage === 'password') {
    // A kit identified a vault this device has no local record of: there was nothing to prove
    // the phrase against, so the acceptance above is unverified. Say so — re-wrapping an empty
    // vault with a wrong phrase is otherwise a silent no-op the user was never told about.
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
              Your old vault password stops working. Your files stay encrypted the whole time, and your 24 words
              keep working.
            </Text>
            {error && <Banner status="error" title={error} />}
            <SubmitButton label="Set new password" isDisabled={!password || !confirm} />
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
