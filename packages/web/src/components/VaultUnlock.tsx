import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Button } from '@astryxdesign/core/Button';
import { Link } from '@astryxdesign/core/Link';
import { RadioList, RadioListItem } from '@astryxdesign/core/RadioList';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession, WRONG_VAULT_PASSWORD } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

function opened(ts?: number): string {
  return ts ? `Opened ${new Date(ts).toLocaleDateString()}` : 'Never opened on this device';
}

export default function VaultUnlock() {
  const { unlockVault, vaults, activeVault, logout } = useSession();
  const navigate = useNavigate();
  const [vaultId, setVaultId] = useState(activeVault?.vaultId ?? vaults[0]?.vaultId ?? '');
  const [password, setPassword] = useState('');
  const { pending, error, run } = useAsyncAction();
  const chosen = vaults.find((v) => v.vaultId === vaultId);
  const many = vaults.length > 1;
  const wrong = error === WRONG_VAULT_PASSWORD;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await unlockVault(password, vaultId || undefined);
      navigate('/');
    }, 'Unlock failed');
  }

  return (
    <AuthFrame title="Unlock your vault" description={many ? 'Choose a vault to unlock.' : 'Welcome back.'}>
      <form onSubmit={onSubmit}>
        <VStack gap={3}>
          {many && (
            <RadioList label="Vault" value={vaultId} onChange={setVaultId}>
              {vaults.map((v) => (
                <RadioListItem key={v.vaultId} value={v.vaultId} label={v.name} description={opened(v.lastOpened)} />
              ))}
            </RadioList>
          )}
          <TextInput
            label={many && chosen ? `Vault password for ${chosen.name}` : 'Vault password'}
            type="password"
            autoComplete="current-password"
            hasAutoFocus
            value={password}
            onChange={setPassword}
          />
          {error && (
            <Banner
              status="error"
              title={wrong ? `That isn't the vault password for ${chosen?.name ?? 'this vault'}.` : error}
              endContent={wrong && <Link href="/vault/recover">Recover with your 24 words</Link>}
            />
          )}
          <SubmitButton label="Unlock" isLoading={pending} isDisabled={!password} />
        </VStack>
      </form>
      <HStack gap={3} hAlign="between" vAlign="center">
        <Link href="/vault/recover" isStandalone>
          Forgot your vault password?
        </Link>
        <Button label="Log out" variant="ghost" size="sm" onClick={() => void logout()} />
      </HStack>
    </AuthFrame>
  );
}
