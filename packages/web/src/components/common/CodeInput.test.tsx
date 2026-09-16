import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import CodeInput from './CodeInput';

function Harness({ onComplete }: { onComplete?: (c: string) => void }) {
  const [v, setV] = useState('');
  return (
    <>
      <CodeInput value={v} onChange={setV} onComplete={onComplete} />
      <button onClick={() => setV('')}>Reset</button>
      <button onClick={() => setV('481920')}>Prefill</button>
    </>
  );
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

  it('typing into box 3 while box 2 is empty does not collapse the digit into box 2, and onComplete waits for all six', async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    await userEvent.click(screen.getByLabelText('Digit 1'));
    await userEvent.keyboard('4');
    await userEvent.click(screen.getByLabelText('Digit 3'));
    await userEvent.keyboard('7');
    expect(screen.getByLabelText('Digit 2')).toHaveValue('');
    expect(screen.getByLabelText('Digit 3')).toHaveValue('7');
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('a browser autofill that writes a whole code into box 1 distributes it across the boxes', () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);
    fireEvent.change(screen.getByLabelText('Digit 1'), { target: { value: '481920' } });
    '481920'.split('').forEach((d, i) => expect(screen.getByLabelText(`Digit ${i + 1}`)).toHaveValue(d));
    expect(onComplete).toHaveBeenCalledWith('481920');
  });

  it('a code the parent sets after mount shows in every box', async () => {
    render(<Harness />);
    await userEvent.type(screen.getByLabelText('Digit 1'), '7');
    await userEvent.click(screen.getByRole('button', { name: 'Prefill' }));
    '481920'.split('').forEach((d, i) => expect(screen.getByLabelText(`Digit ${i + 1}`)).toHaveValue(d));
  });

  it('a parent reset to empty string clears every box', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByLabelText('Digit 1'));
    await userEvent.keyboard('123456');
    expect(screen.getByLabelText('Digit 6')).toHaveValue('6');
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }));
    for (let i = 1; i <= 6; i++) expect(screen.getByLabelText(`Digit ${i}`)).toHaveValue('');
  });
});
