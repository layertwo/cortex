import { CodeBlock } from '@astryxdesign/core/CodeBlock';
import { VStack } from '@astryxdesign/core/VStack';
import { Button } from '@astryxdesign/core/Button';
import { useClipboard } from '@astryxdesign/core/hooks';

// Three words per line: 24 BIP39 words read as eight short rows instead of one wall of
// text. The existing tests assert on whole rows ('word1 word2 word3').
export function phraseRows(phrase: string): string {
  const words = phrase.trim().split(/\s+/);
  return Array.from({ length: Math.ceil(words.length / 3) }, (_, i) =>
    words.slice(i * 3, i * 3 + 3).join(' '),
  ).join('\n');
}

// CodeBlock renders each line as its own element; its own "Copy code" button would copy
// just the multi-line display text, not the single-line phrase, so it's disabled here in
// favor of our own button that copies the original `phrase`.
export default function RecoveryPhrase({ phrase }: { phrase: string }) {
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
      <Button
        label={isCopied ? 'Copied' : 'Copy recovery phrase'}
        size="sm"
        onClick={() => void copy(phrase)}
      />
    </VStack>
  );
}
