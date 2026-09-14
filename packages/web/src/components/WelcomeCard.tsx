import { useState } from 'react';
import { Card } from '@astryxdesign/core/Card';
import { Heading } from '@astryxdesign/core/Heading';
import { Text } from '@astryxdesign/core/Text';
import { Icon } from '@astryxdesign/core/Icon';
import { IconButton } from '@astryxdesign/core/IconButton';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';

const key = (vaultId: string) => `cortex_welcome_done:${vaultId}`;

// First-run checklist above the drop zone. Goes away on its own once the vault has a file
// and a collection, or when dismissed (remembered per vault on this device).
export default function WelcomeCard({
  vaultId,
  name,
  hasFiles,
  hasCollections,
}: {
  vaultId: string;
  name: string;
  hasFiles: boolean;
  hasCollections: boolean;
}) {
  // Lazy useState only reads localStorage once; the Dashboard call site passes
  // key={vaultId} so switching vaults remounts this component instead.
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(key(vaultId)) === '1');
  if (dismissed || (hasFiles && hasCollections)) return null;

  const steps: Array<[string, boolean]> = [
    ['Recovery phrase saved', true],
    ['Upload your first file', hasFiles],
    ['Create a collection', hasCollections],
  ];

  function dismiss() {
    localStorage.setItem(key(vaultId), '1');
    setDismissed(true);
  }

  return (
    <Card padding={4} variant="purple">
      <HStack gap={3} vAlign="start">
        <VStack gap={2} width="100%">
          <Heading level={2}>{`Your vault is ready${name ? `, ${name}` : ''}.`}</Heading>
          <Text as="p" color="secondary">
            Three things to make it yours:
          </Text>
          <ul style={{ margin: 0, paddingInlineStart: 0, listStyle: 'none', display: 'grid', gap: 'var(--spacing-1)' }}>
            {steps.map(([label, done]) => (
              <li key={label} data-done={String(done)} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                <Icon icon={done ? 'success' : 'clock'} color={done ? 'success' : 'secondary'} size="sm" />
                <Text color={done ? 'secondary' : 'primary'}>{label}</Text>
              </li>
            ))}
          </ul>
        </VStack>
        <IconButton label="Dismiss welcome" variant="ghost" size="sm" icon={<Icon icon="close" />} onClick={dismiss} />
      </HStack>
    </Card>
  );
}
