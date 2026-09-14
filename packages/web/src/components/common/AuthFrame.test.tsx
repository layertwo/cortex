import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AuthFrame from './AuthFrame';

describe('AuthFrame', () => {
  it('renders the wordmark, title, description, footer line and children', () => {
    render(
      <AuthFrame title="Welcome back" description="Log in to open your vault.">
        <button>child</button>
      </AuthFrame>,
    );
    expect(screen.getByTestId('wordmark')).toHaveTextContent('Cortex');
    expect(screen.getByRole('heading', { level: 1, name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.getByText('Log in to open your vault.')).toBeInTheDocument();
    expect(screen.getByText(/never sees your files or your keys/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'child' })).toBeInTheDocument();
  });

  it('renders the rail with the active step marked current', () => {
    render(
      <AuthFrame title="T" rail={{ steps: ['Account', 'Verify', 'Vault', 'Recovery'], active: 2 }}>
        x
      </AuthFrame>,
    );
    const list = screen.getByRole('list', { name: 'Setup progress' });
    const items = screen.getAllByRole('listitem');
    expect(list).toBeInTheDocument();
    expect(items).toHaveLength(4);
    expect(items[2]).toHaveAttribute('aria-current', 'step');
    expect(items[2]).toHaveTextContent('Vault');
  });

  it('adds the enter animation class only when asked', () => {
    const { container, rerender } = render(<AuthFrame title="T">x</AuthFrame>);
    expect(container.querySelector('.auth-enter')).toBeNull();
    rerender(<AuthFrame title="T" enter>x</AuthFrame>);
    expect(container.querySelector('.auth-enter')).not.toBeNull();
  });

  it('renders an aside next to the card when provided', () => {
    render(<AuthFrame title="T" aside={<div>proof</div>}>x</AuthFrame>);
    expect(screen.getByText('proof')).toBeInTheDocument();
  });
});
