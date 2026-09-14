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

// Resets the Cognito *account* password only. The vault password (which derives the
// encryption key client-side) is separate and unrecoverable here — that's BIP39 recovery.
export default function ForgotPassword() {
  const { requestPasswordReset, confirmPasswordReset } = useSession();
  const navigate = useNavigate();
  const [sent, setSent] = useState(false);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const { pending, error, run } = useAsyncAction();

  function onRequest(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await requestPasswordReset(email);
      setSent(true);
    }, 'Could not send reset code');
  }

  function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      await confirmPasswordReset(email, code, newPassword);
      navigate('/login');
    }, 'Reset failed');
  }

  return (
    <AuthFrame
      title="Reset your account password"
      description="We'll email you a reset code."
    >
      <form onSubmit={sent ? onConfirm : onRequest}>
        <VStack gap={3}>
          <TextInput
            label="Email"
            type="email"
            autoComplete="email"
            hasAutoFocus={!sent}
            value={email}
            onChange={setEmail}
            isDisabled={sent}
          />
          {sent && (
            <>
              <TextInput
                label="Reset code"
                autoComplete="one-time-code"
                hasAutoFocus
                value={code}
                onChange={setCode}
              />
              <TextInput
                label="New password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={setNewPassword}
              />
            </>
          )}
          {error && <Banner status="error" title={error} />}
          <SubmitButton
            label={sent ? 'Set new password' : 'Send reset code'}
            isLoading={pending}
            isDisabled={sent ? !code || !newPassword : !email}
          />
        </VStack>
      </form>
      <Link href="/login" isStandalone>
        Back to log in
      </Link>
      <Text as="p" type="supporting">
        This is your <b>account</b> password, the one you log in with. Your <b>vault</b> password is
        different and we can't reset it. If that's the one you forgot, log in and choose “Forgot your
        vault password?” to use your 24 words.
      </Text>
    </AuthFrame>
  );
}
