import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { VStack } from '@astryxdesign/core/VStack';
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
      title="Reset account password"
      description="This resets your account login only. Your vault password is separate."
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
    </AuthFrame>
  );
}
