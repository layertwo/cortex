import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RecoveryPhrase, { phraseRows } from './RecoveryPhrase';

const PHRASE =
  'word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15 word16 word17 word18 word19 word20 word21 word22 word23 word24';

describe('RecoveryPhrase', () => {
  it('phraseRows groups three words per line', () => {
    expect(phraseRows('a b c d e f g')).toBe('a b c\nd e f\ng');
  });

  it('renders each three-word row as its own line with a copy button', () => {
    render(<RecoveryPhrase phrase={PHRASE} />);
    expect(screen.getByText('word1 word2 word3')).toBeInTheDocument();
    expect(screen.getByText(/word22 word23 word24/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
  });

  it('copies the original single-line phrase to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    render(<RecoveryPhrase phrase={PHRASE} />);
    await userEvent.click(screen.getByRole('button', { name: /copy/i }));
    expect(writeText).toHaveBeenCalledWith(PHRASE);
  });
});
