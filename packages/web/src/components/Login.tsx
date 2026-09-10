import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function Login() {
  const { signInAccount } = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { pending, error, run } = useAsyncAction();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await signInAccount(email, password);
      // Land on '/'; the RequireAuth + RequireVault guards forward to vault unlock/setup.
      navigate('/');
    }, 'Login failed');
  }

  return (
    <AuthFrame title="Log in">
      <form onSubmit={onSubmit}>
        <VStack gap={3}>
          <TextInput
            label="Email"
            type="email"
            autoComplete="email"
            hasAutoFocus
            value={email}
            onChange={setEmail}
          />
          <TextInput
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
          />
          {error && <Banner status="error" title={error} />}
          <SubmitButton label="Log in" isLoading={pending} isDisabled={!email || !password} />
        </VStack>
      </form>
      <HStack gap={3} hAlign="between">
        <Link href="/forgot" isStandalone>
          Forgot password?
        </Link>
        <Link href="/signup" isStandalone>
          Create account
        </Link>
      </HStack>
    </AuthFrame>
  );
}
