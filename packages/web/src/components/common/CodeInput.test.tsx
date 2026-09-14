import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import CodeInput from './CodeInput';

function Harness({ onComplete }: { onComplete?: (c: string) => void }) {
  const [v, setV] = useState('');
  return <CodeInput value={v} onChange={setV} onComplete={onComplete} />;
}

describe('CodeInput', () => {
  it('renders six labelled boxes in a named group', () => {
    render(<Harness />);
    expect(screen.getByRole('group', { name: 'Verification code' })).toBeInTheDocument();
    for (let i = 1; i <= 6; i++) expect(screen.getByLabelText(`Digit ${i}`)).toBeInTheDocument();
  });

  it('typing a digit fills the box and moves focus to the next one', async () => {
    render(<Harness />);
    const first = screen.getByLabelText('Digit 1');
    await userEvent.click(first);
    await userEvent.keyboard('4');
    expect(first).toHaveValue('4');
    expect(screen.getByLabelText('Digit 2')).toHaveFocus();
  });

  it('pasting a whole code fills every box and calls onComplete', () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    fireEvent.paste(screen.getByLabelText('Digit 1'), {
      clipboardData: { getData: () => '481920' },
    });
    expect(screen.getByLabelText('Digit 6')).toHaveValue('0');
    expect(onComplete).toHaveBeenCalledWith('481920');
  });

  it('ignores non-digits', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByLabelText('Digit 1'));
    await userEvent.keyboard('x');
    expect(screen.getByLabelText('Digit 1')).toHaveValue('');
  });

  it('pasting a partial code focuses the next empty box and does not complete', () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    fireEvent.paste(screen.getByLabelText('Digit 1'), {
      clipboardData: { getData: () => '481' },
    });
    expect(screen.getByLabelText('Digit 3')).toHaveValue('1');
    expect(screen.getByLabelText('Digit 4')).toHaveFocus();
    expect(onComplete).not.toHaveBeenCalled();
  });
});
