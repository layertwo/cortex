import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { useSession } from '../auth/SessionContext';
import { DEFAULT_VAULT_NAME } from '../vault/registry';
import AuthFrame from './common/AuthFrame';
import { SETUP_STEPS } from './common/SetupRail';
import PasswordStrength from './common/PasswordStrength';
import RecoveryPhrase from './common/RecoveryPhrase';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function VaultSetup() {
  const { setupVault, activeVault } = useSession();
  const navigate = useNavigate();
  const [name, setName] = useState(DEFAULT_VAULT_NAME);
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
      setRecovery(await setupVault(password, name));
    }, 'Vault setup failed');
  }

  if (recovery) {
    return (
      <AuthFrame
        title="Write these 24 words down"
        description="They are the only way back in if you forget your vault password. Store them offline; they will not be shown again."
        rail={{ steps: SETUP_STEPS, active: 3 }}
      >
        <RecoveryPhrase phrase={recovery} kit={activeVault ?? undefined} />
        <CheckboxInput label="I have saved my recovery phrase" value={saved} onChange={setSaved} />
        <Button
          label="Open my vault"
          variant="primary"
          width="100%"
          isDisabled={!saved}
          onClick={() => navigate('/')}
        />
      </AuthFrame>
    );
  }

  return (
    <AuthFrame
      title="Set up your vault"
      description="This password encrypts everything and can't be reset, only recovered with your phrase. You can add more vaults later."
      rail={{ steps: SETUP_STEPS, active: 2 }}
    >
      <form onSubmit={onCreate}>
        <VStack gap={3}>
          <TextInput label="Vault name" value={name} onChange={setName} />
          <TextInput
            label="Vault password"
            type="password"
            autoComplete="new-password"
            hasAutoFocus
            value={password}
            onChange={setPassword}
          />
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
          <SubmitButton label="Create vault" isLoading={pending} isDisabled={!password || !confirm} />
        </VStack>
      </form>
      <Text as="p" type="supporting">
        Already have a vault on another device? <Link href="/vault/recover">Restore it from your recovery kit</Link>.
      </Text>
    </AuthFrame>
  );
}
