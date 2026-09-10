import type { ReactNode } from 'react';
import { Center } from '@astryxdesign/core/Center';
import { Card } from '@astryxdesign/core/Card';
import { VStack } from '@astryxdesign/core/VStack';
import { Heading } from '@astryxdesign/core/Heading';
import { Text } from '@astryxdesign/core/Text';

// The "Login Card" frame shared by every screen outside the dashboard: a single
// centered card, one h1, optional supporting text, then whatever the screen renders.
export default function AuthFrame({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    // Standalone pages paint the body background themselves (no AppShell); the card
    // then reads as a card instead of a white box on a white page.
    <Center minHeight="100dvh" padding={4} style={{ backgroundColor: 'var(--color-background-body)' }}>
      <Card width={400} maxWidth="100%" padding={8} elevation="low">
        <VStack gap={4}>
          <Heading level={1}>{title}</Heading>
          {description && (
            <Text as="p" color="secondary">
              {description}
            </Text>
          )}
          {children}
        </VStack>
      </Card>
    </Center>
  );
}
