import { Center } from '@astryxdesign/core/Center';
import { VStack } from '@astryxdesign/core/VStack';
import { Heading } from '@astryxdesign/core/Heading';
import { Text } from '@astryxdesign/core/Text';
import { Button } from '@astryxdesign/core/Button';
import { useSession } from '../auth/SessionContext';

// Shown when there is no OIDC session (first visit, expired token, or a failed callback).
export default function SignIn() {
  const { signIn } = useSession();
  return (
    <Center minHeight="100dvh" padding={6}>
      <VStack gap={4} hAlign="start" maxWidth={420}>
        <Heading level={1}>Sign in to Cortex</Heading>
        <Text as="p" color="secondary">
          Your vault password stays separate; signing in only confirms who you are.
        </Text>
        <Button label="Sign in" variant="primary" onClick={() => void signIn()} />
      </VStack>
    </Center>
  );
}
