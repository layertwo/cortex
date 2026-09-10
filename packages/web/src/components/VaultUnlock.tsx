import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { VStack } from '@astryxdesign/core/VStack';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function VaultUnlock() {
  const { unlockVault } = useSession();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const { pending, error, run } = useAsyncAction();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await unlockVault(password);
      navigate('/');
    }, 'Unlock failed');
  }

  return (
    <AuthFrame title="Unlock your vault">
      <form onSubmit={onSubmit}>
        <VStack gap={3}>
          <TextInput
            label="Vault password"
            type="password"
            autoComplete="current-password"
            hasAutoFocus
            value={password}
            onChange={setPassword}
          />
          {error && <Banner status="error" title={error} />}
          <SubmitButton label="Unlock" isLoading={pending} isDisabled={!password} />
        </VStack>
      </form>
    </AuthFrame>
  );
}
