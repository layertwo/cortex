import type { ReactNode } from 'react';
import { Center } from '@astryxdesign/core/Center';
import { Card } from '@astryxdesign/core/Card';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { Heading } from '@astryxdesign/core/Heading';
import { Text } from '@astryxdesign/core/Text';
import Wordmark from '../brand/Wordmark';
import SetupRail from './SetupRail';

// The frame for every screen outside the dashboard: mesh page, one glass card with the
// wordmark, an optional progress rail, one h1, optional supporting text, then the screen.
// `aside` renders beside the card (wraps underneath on narrow screens); `enter` plays the
// slide-in used when arriving from the landing hero.
export default function AuthFrame({
  title,
  description,
  children,
  rail,
  aside,
  enter = false,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  rail?: { steps: readonly string[]; active: number };
  aside?: ReactNode;
  enter?: boolean;
}) {
  return (
    <Center minHeight="100dvh" padding={4} className="auth-page">
      <VStack gap={3} hAlign="center">
        <HStack gap={6} wrap="wrap" hAlign="center" vAlign="center">
          <Card
            width={400}
            maxWidth="100%"
            padding={8}
            variant="transparent"
            className={enter ? 'auth-glass auth-enter' : 'auth-glass'}
          >
            <VStack gap={4}>
              <Wordmark size="sm" />
              {rail && <SetupRail steps={rail.steps} active={rail.active} />}
              <Heading level={1}>{title}</Heading>
              {description && (
                <Text as="p" color="secondary">
                  {description}
                </Text>
              )}
              {children}
            </VStack>
          </Card>
          {aside}
        </HStack>
        <Text as="p" type="supporting" justify="center">
          End-to-end encrypted. Cortex never sees your files or your keys.
        </Text>
      </VStack>
    </Center>
  );
}
