import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { VStack } from '@astryxdesign/core/VStack';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function VerifyEmail() {
  const { confirmAccount } = useSession();
  const navigate = useNavigate();
  const passedEmail = (useLocation().state as { email?: string } | null)?.email ?? '';
  const [email, setEmail] = useState(passedEmail);
  const [code, setCode] = useState('');
  const { pending, error, run } = useAsyncAction();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await confirmAccount(email, code);
      navigate('/login');
    }, 'Verification failed');
  }

  return (
    <AuthFrame title="Verify your email" description="Enter the code we emailed you.">
      <form onSubmit={onSubmit}>
        <VStack gap={3}>
          <TextInput label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} />
          <TextInput
            label="Verification code"
            autoComplete="one-time-code"
            hasAutoFocus={!!passedEmail}
            value={code}
            onChange={setCode}
          />
          {error && <Banner status="error" title={error} />}
          <SubmitButton label="Verify" isLoading={pending} isDisabled={!email || !code} />
        </VStack>
      </form>
      <Link href="/login" isStandalone>
        Back to log in
      </Link>
    </AuthFrame>
  );
}
