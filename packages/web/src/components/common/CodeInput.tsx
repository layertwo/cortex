import { useRef, type ClipboardEvent, type KeyboardEvent } from 'react';
import { TextInput } from '@astryxdesign/core/TextInput';
import { HStack } from '@astryxdesign/core/HStack';

const LENGTH = 6;

// One box per digit. Typing advances, Backspace on an empty box retreats, and pasting
// distributes the whole code. Astryx has no one-time-code component, so this composes
// TextInputs with visually hidden labels ("Digit 1"…) inside a named group.
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
  const digits = Array.from({ length: LENGTH }, (_, i) => value[i] ?? '');

  // Editing a completed code deliberately re-fires onComplete so a rejected code can be
  // corrected and resubmitted.
  function commit(code: string) {
    onChange(code);
    if (code.length === LENGTH) onComplete?.(code);
  }

  function setAt(i: number, raw: string) {
    const d = raw.replace(/\D/g, '').slice(-1);
    commit(digits.map((x, j) => (j === i ? d : x)).join(''));
    if (d && i < LENGTH - 1) refs.current[i + 1]?.focus();
  }

  function onKeyDown(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !digits[i] && i > 0) refs.current[i - 1]?.focus();
  }

  function onPaste(e: ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData('text').replace(/\D/g, '');
    if (!text) return;
    e.preventDefault();
    commit(text.slice(0, LENGTH));
    refs.current[Math.min(text.length, LENGTH - 1)]?.focus();
  }

  return (
    <HStack gap={1.5} role="group" aria-label="Verification code">
      {digits.map((d, i) => (
        <TextInput
          key={i}
          ref={(el) => void (refs.current[i] = el)}
          label={`Digit ${i + 1}`}
          isLabelHidden
          value={d}
          onChange={(v) => setAt(i, v)}
          onKeyDown={(e) => onKeyDown(i, e)}
          onPaste={onPaste}
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          hasAutoFocus={i === 0}
          width={44}
          {...({ inputMode: 'numeric', maxLength: 1 } as object)}
        />
      ))}
    </HStack>
  );
}
