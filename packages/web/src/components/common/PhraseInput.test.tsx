import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import PhraseInput from './PhraseInput';

const WORDS = Array.from({ length: 24 }, (_, i) => `w${i + 1}`);

function Harness({ onChange }: { onChange?: (w: string[]) => void }) {
  const [words, setWords] = useState<string[]>(Array(24).fill(''));
  return (
    <PhraseInput
      words={words}
      onChange={(w) => {
        setWords(w);
        onChange?.(w);
      }}
    />
  );
}

describe('PhraseInput', () => {
  it('renders 24 masked boxes in a named group', () => {
    render(<Harness />);
    expect(screen.getByRole('group', { name: 'Recovery phrase' })).toBeInTheDocument();
    const first = screen.getByLabelText('Word 1') as HTMLInputElement;
    expect(first.type).toBe('password');
    expect(screen.getByLabelText('Word 24')).toBeInTheDocument();
  });

  it('Show words reveals the boxes', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('checkbox', { name: /show words/i }));
    expect((screen.getByLabelText('Word 1') as HTMLInputElement).type).toBe('text');
  });

  it('pasting the whole phrase into any box distributes it from that box', () => {
    render(<Harness />);
    fireEvent.paste(screen.getByLabelText('Word 1'), { clipboardData: { getData: () => WORDS.join(' ') } });
    expect(screen.getByLabelText('Word 1')).toHaveValue('w1');
    expect(screen.getByLabelText('Word 24')).toHaveValue('w24');
  });

  it('a space moves to the next box and never renders any validation message', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByLabelText('Word 1'));
    await userEvent.keyboard('zzzz ');
    expect(screen.getByLabelText('Word 1')).toHaveValue('zzzz');
    expect(screen.getByLabelText('Word 2')).toHaveFocus();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('pasting three words into box 1 focuses box 4, the next empty box', () => {
    render(<Harness />);
    fireEvent.paste(screen.getByLabelText('Word 1'), { clipboardData: { getData: () => 'w1 w2 w3' } });
    expect(screen.getByLabelText('Word 4')).toHaveFocus();
  });

  it('pasting 2 words into box 2 when boxes 1-4 are already filled focuses box 5, the first empty one, not box 4', () => {
    render(<Harness />);
    ['w0', 'w1', 'w2', 'w3'].forEach((w, i) => {
      fireEvent.change(screen.getByLabelText(`Word ${i + 1}`), { target: { value: w } });
    });
    fireEvent.paste(screen.getByLabelText('Word 2'), { clipboardData: { getData: () => 'x1 x2' } });
    expect(screen.getByLabelText('Word 5')).toHaveFocus();
  });

  it('pasting all 24 words focuses box 24, the last box', () => {
    render(<Harness />);
    fireEvent.paste(screen.getByLabelText('Word 1'), { clipboardData: { getData: () => WORDS.join(' ') } });
    expect(screen.getByLabelText('Word 24')).toHaveFocus();
  });
});
