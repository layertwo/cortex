import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { VStack } from '@astryxdesign/core/VStack';
import { Text } from '@astryxdesign/core/Text';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function Signup() {
  const { signUpAccount } = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { pending, error, run } = useAsyncAction();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await signUpAccount(email, password);
      // The vault password is chosen later, during vault setup — not here.
      navigate('/verify', { state: { email } });
    }, 'Sign up failed');
  }

  return (
    <AuthFrame title="Create your Cortex account">
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
            autoComplete="new-password"
            value={password}
            onChange={setPassword}
          />
          {error && <Banner status="error" title={error} />}
          <SubmitButton label="Sign up" isLoading={pending} isDisabled={!email || !password} />
        </VStack>
      </form>
      <Text as="p" color="secondary">
        Already have an account? <Link href="/login">Log in</Link>
      </Text>
    </AuthFrame>
  );
}
