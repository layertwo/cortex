import { CodeBlock } from '@astryxdesign/core/CodeBlock';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { Button } from '@astryxdesign/core/Button';
import { useClipboard } from '@astryxdesign/core/hooks';
import { buildRecoveryKit, downloadRecoveryKit } from '../../vault/recoveryKit';

// Three words per line: 24 BIP39 words read as eight short rows instead of one wall of
// text. The existing tests assert on whole rows ('word1 word2 word3').
export function phraseRows(phrase: string): string {
  const words = phrase.trim().split(/\s+/);
  return Array.from({ length: Math.ceil(words.length / 3) }, (_, i) =>
    words.slice(i * 3, i * 3 + 3).join(' '),
  ).join('\n');
}

// CodeBlock renders each line as its own element; its own "Copy code" button would copy
// the multi-line display text, so copying is done here with the original single-line phrase.
// `kit` enables "Download recovery kit" (words + vault name + vault ID as a .txt file).
export default function RecoveryPhrase({
  phrase,
  kit,
}: {
  phrase: string;
  kit?: { name: string; vaultId: string };
}) {
  const { copy, isCopied } = useClipboard();
  return (
    <VStack gap={2}>
      <CodeBlock
        title="Recovery phrase"
        code={phraseRows(phrase)}
        hasCopyButton={false}
        isWrapped
        width="100%"
      />
      <HStack gap={2} wrap="wrap">
        <Button label={isCopied ? 'Copied' : 'Copy words'} size="sm" onClick={() => void copy(phrase)} />
        {kit && (
          <Button
            label="Download recovery kit"
            size="sm"
            onClick={() =>
              downloadRecoveryKit(buildRecoveryKit({ ...kit, phrase, createdAt: new Date() }), kit.name)
            }
          />
        )}
      </HStack>
    </VStack>
  );
}
