import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from 'react';
import { TextInput } from '@astryxdesign/core/TextInput';
import { HStack } from '@astryxdesign/core/HStack';

const LENGTH = 6;

// One box per digit, held as component state (not derived from `value`) so a digit typed
// into a box past a gap doesn't collapse into the first empty box: joining a sparse array
// of digits loses position information, which was the bug. Typing advances, Backspace on an
// empty box retreats, and pasting starting at any box distributes from there. Astryx has no
// one-time-code component, so this composes TextInputs with visually hidden labels
// ("Digit 1"…) inside a named group.
export default function CodeInput({
  value,
  onChange,
  onComplete,
}: {
  value: string;
  onChange: (value: string) => void;
  onComplete?: (code: string) => void;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const [boxes, setBoxes] = useState<string[]>(() => Array.from({ length: LENGTH }, (_, i) => value[i] ?? ''));

  // `boxes` is the source of truth while the user types, so a gap between digits survives
  // instead of collapsing (joining a sparse array loses position). This effect only re-seeds
  // `boxes` when the parent hands down a value they don't already spell — a reset to '' after
  // a rejected code, or a prefilled code the parent sets after mount (e.g. from a deep link).
  useEffect(() => {
    if (value !== boxes.join('')) setBoxes(Array.from({ length: LENGTH }, (_, i) => value[i] ?? ''));
  }, [value]);

  // Editing a completed code deliberately re-fires onComplete so a rejected code can be
  // corrected and resubmitted.
  function commit(next: string[]) {
    setBoxes(next);
    const code = next.join('');
    onChange(code);
    if (next.every(Boolean)) onComplete?.(code);
  }

  // Writes `digits` into boxes i.. (dropping any past the end) and focuses the next empty box.
  // Shared by paste and by a browser autofill that drops a whole code into one box.
  function fill(i: number, digits: string[]) {
    const take = digits.slice(0, LENGTH - i);
    const next = boxes.map((x, j) => (j >= i && j < i + take.length ? take[j - i] : x));
    commit(next);
    const nextEmpty = next.findIndex((x, j) => j >= i && !x);
    refs.current[nextEmpty === -1 ? LENGTH - 1 : nextEmpty]?.focus();
  }

  function setAt(i: number, raw: string) {
    const d = raw.replace(/\D/g, '');
    if (d.length > 1) return fill(i, d.split(''));
    commit(boxes.map((x, j) => (j === i ? d : x)));
    if (d && i < LENGTH - 1) refs.current[i + 1]?.focus();
  }

  function onKeyDown(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !boxes[i] && i > 0) refs.current[i - 1]?.focus();
  }

  function onPaste(i: number, e: ClipboardEvent<HTMLElement>) {
    const digits = e.clipboardData.getData('text').replace(/\D/g, '');
    if (!digits) return;
    e.preventDefault();
    fill(i, digits.split(''));
  }

  return (
    <HStack gap={1.5} role="group" aria-label="Verification code">
      {boxes.map((d, i) => (
        <TextInput
          key={i}
          ref={(el) => void (refs.current[i] = el)}
          label={`Digit ${i + 1}`}
          isLabelHidden
          value={d}
          onChange={(v) => setAt(i, v)}
          onKeyDown={(e) => onKeyDown(i, e)}
          onPaste={(e) => onPaste(i, e)}
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          hasAutoFocus={i === 0}
          width={44}
          {...({ inputMode: 'numeric', maxLength: 1 } as object)}
        />
      ))}
    </HStack>
  );
}
