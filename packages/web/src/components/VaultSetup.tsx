import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { VStack } from '@astryxdesign/core/VStack';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import RecoveryPhrase from './common/RecoveryPhrase';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function VaultSetup() {
  const { setupVault } = useSession();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [recovery, setRecovery] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const { pending, error, setError, run } = useAsyncAction();

  function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError('Vault passwords do not match');
      return;
    }
    void run(async () => {
      setRecovery(await setupVault(password));
    }, 'Vault setup failed');
  }

  if (recovery) {
    return (
      <AuthFrame
        title="Save your recovery phrase"
        description="This 24-word phrase is the only way to recover your vault if you forget your vault password. Store it offline. It will not be shown again."
      >
        <RecoveryPhrase phrase={recovery} />
        <CheckboxInput label="I have saved my recovery phrase" value={saved} onChange={setSaved} />
        <Button
          label="Continue"
          variant="primary"
          width="100%"
          isDisabled={!saved}
          onClick={() => navigate('/')}
        />
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Set up your vault" description="Use a different password than your account password.">
      <form onSubmit={onCreate}>
        <VStack gap={3}>
          <TextInput
            label="Vault password"
            type="password"
            autoComplete="new-password"
            hasAutoFocus
            value={password}
            onChange={setPassword}
          />
          <TextInput
            label="Confirm vault password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={setConfirm}
            status={confirm && confirm !== password ? { type: 'error' } : undefined}
          />
          {error && <Banner status="error" title={error} />}
          <SubmitButton label="Create vault" isLoading={pending} isDisabled={!password || !confirm} />
        </VStack>
      </form>
    </AuthFrame>
  );
}
