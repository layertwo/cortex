import { Card } from '@astryxdesign/core/Card';
import { Grid } from '@astryxdesign/core/Grid';
import { VStack } from '@astryxdesign/core/VStack';
import { Text } from '@astryxdesign/core/Text';

const CARDS = [
  { big: '0 bytes', small: 'readable by us. Files are encrypted before upload.' },
  { big: '24 words', small: 'A recovery phrase only you hold.' },
  { big: 'Any file', small: 'Photos, videos, PDFs, notes. Up to 5 GB each.' },
  { big: 'Your key', small: 'A vault password that never leaves your device.' },
];

// Four small proof cards shown beside the sign-up card on wide screens.
export default function SignupProof() {
  return (
    <Grid columns={2} gap={2} width={260} aria-label="Why Cortex">
      {CARDS.map((c) => (
        <Card key={c.big} padding={3} variant="transparent" className="auth-glass">
          <VStack gap={1}>
            <Text weight="bold" size="lg" color="accent">
              {c.big}
            </Text>
            <Text type="supporting">{c.small}</Text>
          </VStack>
        </Card>
      ))}
    </Grid>
  );
}
