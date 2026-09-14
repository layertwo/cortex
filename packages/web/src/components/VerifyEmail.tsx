import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Button } from '@astryxdesign/core/Button';
import { Link } from '@astryxdesign/core/Link';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import { SETUP_STEPS } from './common/SetupRail';
import CodeInput from './common/CodeInput';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';

export default function VerifyEmail() {
  const { confirmAccount, resendCode } = useSession();
  const navigate = useNavigate();
  const passedEmail = (useLocation().state as { email?: string } | null)?.email ?? '';
  const [email, setEmail] = useState(passedEmail);
  const [code, setCode] = useState('');
  const [resent, setResent] = useState(false);
  const { pending, error, run } = useAsyncAction();
  const resend = useAsyncAction();

  function submit(c = code) {
    void run(async () => {
      await confirmAccount(email, c);
      navigate('/login');
    }, 'Verification failed');
  }

  return (
    <AuthFrame
      title="Check your inbox"
      description={passedEmail ? `We sent a six-digit code to ${passedEmail}.` : 'Enter the code we emailed you.'}
      rail={{ steps: SETUP_STEPS, active: 1 }}
    >
      <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <VStack gap={3}>
          {!passedEmail && (
            <TextInput label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} />
          )}
          <CodeInput value={code} onChange={setCode} onComplete={submit} />
          {error && <Banner status="error" title={error} />}
          {resent && <Banner status="success" title="A new code is on its way." />}
          {resend.error && <Banner status="error" title={resend.error} />}
          <SubmitButton label="Verify" isLoading={pending} isDisabled={!email || code.length < 6} />
        </VStack>
      </form>
      <HStack gap={3} hAlign="between" vAlign="center">
        <Button
          label="Resend code"
          variant="ghost"
          size="sm"
          isDisabled={!email || resend.pending}
          onClick={() =>
            void resend.run(async () => {
              await resendCode(email);
              setResent(true);
            }, 'Could not resend the code')
          }
        />
        <Link href="/login" isStandalone>
          Back to log in
        </Link>
      </HStack>
    </AuthFrame>
  );
}
