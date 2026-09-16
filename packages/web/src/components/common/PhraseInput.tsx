import { useRef, useState, type ClipboardEvent, type KeyboardEvent } from 'react';
import { TextInput } from '@astryxdesign/core/TextInput';
import { CheckboxInput } from '@astryxdesign/core/CheckboxInput';
import { Grid } from '@astryxdesign/core/Grid';
import { VStack } from '@astryxdesign/core/VStack';

export const PHRASE_LENGTH = 24;

// 24 boxes that behave like password fields: masked until "Show words", paste distributes,
// space advances. Deliberately no autocomplete, no wordlist check and no per-word feedback;
// the phrase is judged only when the user continues, with one generic message.
export default function PhraseInput({
  words,
  onChange,
}: {
  words: string[];
  onChange: (words: string[]) => void;
}) {
  const [show, setShow] = useState(false);
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  function setAt(i: number, value: string) {
    const next = [...words];
    next[i] = value.trim().toLowerCase();
    onChange(next);
  }

  function onKeyDown(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === ' ' && words[i]) {
      e.preventDefault();
      refs.current[Math.min(i + 1, PHRASE_LENGTH - 1)]?.focus();
    }
    if (e.key === 'Backspace' && !words[i] && i > 0) refs.current[i - 1]?.focus();
  }

  function onPaste(i: number, e: ClipboardEvent<HTMLElement>) {
    const pasted = e.clipboardData.getData('text').trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (pasted.length < 2) return; // single word: let the normal change handler take it
    e.preventDefault();
    const next = [...words];
    pasted.slice(0, PHRASE_LENGTH - i).forEach((w, k) => {
      next[i + k] = w;
    });
    onChange(next);
    const nextEmpty = next.findIndex((w, j) => j >= i && !w);
    refs.current[nextEmpty === -1 ? PHRASE_LENGTH - 1 : nextEmpty]?.focus();
  }

  return (
    <VStack gap={2}>
      <Grid role="group" aria-label="Recovery phrase" className="phrase-grid" columns={3} gap={1.5}>
        {Array.from({ length: PHRASE_LENGTH }, (_, i) => (
          <TextInput
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            label={`Word ${i + 1}`}
            isLabelHidden
            placeholder={String(i + 1)}
            type={show ? 'text' : 'password'}
            autoComplete="off"
            size="sm"
            value={words[i] ?? ''}
            onChange={(v) => setAt(i, v)}
            onKeyDown={(e) => onKeyDown(i, e)}
            onPaste={(e) => onPaste(i, e)}
          />
        ))}
      </Grid>
      <CheckboxInput label="Show words" size="sm" value={show} onChange={setShow} />
    </VStack>
  );
}
