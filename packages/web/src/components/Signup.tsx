import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { validatePassword, validatePasswordStrength } from '@cortex/encryption';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { Link } from '@astryxdesign/core/Link';
import { VStack } from '@astryxdesign/core/VStack';
import { Text } from '@astryxdesign/core/Text';
import { useMediaQuery } from '@astryxdesign/core/hooks';
import { useSession } from '../auth/SessionContext';
import AuthFrame from './common/AuthFrame';
import PasswordStrength from './common/PasswordStrength';
import { SETUP_STEPS } from './common/SetupRail';
import SubmitButton from './common/SubmitButton';
import { useAsyncAction } from './common/useAsyncAction';
import SignupProof from './SignupProof';

export default function Signup() {
  const { signUpAccount } = useSession();
  const navigate = useNavigate();
  const fromLanding = !!(useLocation().state as { fromLanding?: boolean } | null)?.fromLanding;
  const wide = useMediaQuery('(min-width: 900px)');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const { pending, error, run } = useAsyncAction();
  const strengthOk = validatePasswordStrength(password).isValid;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void run(async () => {
      // Strength is already gated by the button; this adds the breach check.
      const result = await validatePassword(password);
      if (!result.isValid) {
        setErrors(result.errors);
        return;
      }
      setErrors([]);
      await signUpAccount(email, password);
      // The vault password is chosen later, during vault setup — not here.
      navigate('/verify', { state: { email } });
    }, 'Sign up failed');
  }

  return (
    <AuthFrame
      title="Create your account"
      description="This password logs you in. Your vault gets its own, next."
      rail={{ steps: SETUP_STEPS, active: 0 }}
      aside={wide ? <SignupProof /> : undefined}
      enter={fromLanding}
    >
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
            onChange={(next) => {
              setPassword(next);
              setErrors([]);
            }}
          />
          <PasswordStrength password={password} />
          {errors.length > 0 && (
            <Banner
              status="error"
              title="Choose a different password"
              description={errors.join(' ')}
            />
          )}
          {error && <Banner status="error" title={error} />}
          <SubmitButton
            label="Continue"
            isLoading={pending}
            isDisabled={!email || !strengthOk}
          />
        </VStack>
      </form>
      <Text as="p" color="secondary">
        Already have an account? <Link href="/login">Log in</Link>
      </Text>
    </AuthFrame>
  );
}
