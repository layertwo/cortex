import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ShareAccess } from './ShareAccess';

describe('ShareAccess', () => {
  it('shows an error banner when the URL fragment is missing', () => {
    window.history.pushState({}, '', '/s/abc');
    render(<ShareAccess apiBaseUrl="https://api" />);
    expect(screen.getByRole('alert')).toHaveTextContent(/missing key material/i);
    expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument();
  });

  it('asks for the share password when the URL is complete', async () => {
    window.history.pushState({}, '', '/s/abc#blob');
    render(<ShareAccess apiBaseUrl="https://api" />);
    expect(await screen.findByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /decrypt/i })).toBeDisabled();
  });
});
