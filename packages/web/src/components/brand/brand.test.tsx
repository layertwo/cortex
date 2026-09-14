import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Mark from './Mark';
import Wordmark from './Wordmark';

describe('brand', () => {
  it('Mark is a decorative SVG sized by the size prop', () => {
    const { container } = render(<Mark size={32} />);
    const svg = container.querySelector('svg')!;
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg).toHaveAttribute('width', '32');
    expect(svg).toHaveAttribute('height', '32');
  });

  it('Wordmark shows the mark and the name', () => {
    render(<Wordmark />);
    const w = screen.getByTestId('wordmark');
    expect(w).toHaveTextContent('Cortex');
    expect(w.querySelector('svg')).not.toBeNull();
  });
});
