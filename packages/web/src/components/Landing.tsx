import { useNavigate } from 'react-router-dom';
import { Center } from '@astryxdesign/core/Center';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { Heading } from '@astryxdesign/core/Heading';
import { Text } from '@astryxdesign/core/Text';
import { Button } from '@astryxdesign/core/Button';
import Mark from './brand/Mark';

// Shown at "/" only when there is no session. Either button hands off to the auth card
// with `fromLanding`, which plays the slide-in (AuthFrame `enter`).
export default function Landing() {
  const navigate = useNavigate();
  const go = (path: string) => navigate(path, { state: { fromLanding: true } });
  return (
    <Center minHeight="100dvh" padding={6} className="auth-page">
      <VStack gap={5} hAlign="start" maxWidth={560}>
        <Mark size={56} />
        <Heading level={1} type="display-2">
          A vault for your memories.{' '}
          <Text as="span" type="inherit" color="accent">
            Only you
          </Text>{' '}
          hold the key.
        </Heading>
        <Text as="p" type="large" color="secondary">
          Photos, videos and files, encrypted on your device before they ever leave it.
        </Text>
        <HStack gap={2} wrap="wrap">
          <Button label="Create account" variant="primary" size="lg" onClick={() => go('/signup')} />
          <Button label="Log in" size="lg" onClick={() => go('/login')} />
        </HStack>
        <Text as="p" type="supporting" justify="center">
          End-to-end encrypted. Cortex never sees your files or your keys.
        </Text>
      </VStack>
    </Center>
  );
}
