import { HStack } from '@astryxdesign/core/HStack';
import { Text } from '@astryxdesign/core/Text';
import Mark from './Mark';

const SIZES = { sm: { mark: 18, text: 'base' }, md: { mark: 22, text: 'lg' } } as const;

// Mark + name. The mark takes the accent colour; the name is Inter bold, tight tracking.
export default function Wordmark({ size = 'md' }: { size?: keyof typeof SIZES }) {
  const s = SIZES[size];
  return (
    <HStack as="span" gap={1.5} vAlign="center" data-testid="wordmark">
      <Mark size={s.mark} />
      <Text weight="bold" size={s.text} style={{ letterSpacing: '-0.02em' }}>
        Cortex
      </Text>
    </HStack>
  );
}
