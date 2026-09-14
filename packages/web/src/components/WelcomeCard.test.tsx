import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WelcomeCard from './WelcomeCard';

beforeEach(() => localStorage.clear());

describe('WelcomeCard', () => {
  it('lists the three steps with the phrase already done', () => {
    render(<WelcomeCard vaultId="v1" name="Personal" hasFiles={false} hasCollections={false} />);
    expect(screen.getByRole('heading', { name: /your vault is ready/i })).toBeInTheDocument();
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent(/recovery phrase saved/i);
    expect(items[0]).toHaveAttribute('data-done', 'true');
    expect(items[1]).toHaveAttribute('data-done', 'false');
  });

  it('disappears when everything is done', () => {
    const { container } = render(<WelcomeCard vaultId="v1" name="Personal" hasFiles hasCollections />);
    expect(container).toBeEmptyDOMElement();
  });

  it('can be dismissed and stays dismissed for that vault', async () => {
    // key={vaultId} mirrors the Dashboard call site: switching vaults remounts the card
    // instead of relying on an effect to resync dismissed state.
    const { rerender, container } = render(
      <WelcomeCard key="v1" vaultId="v1" name="Personal" hasFiles={false} hasCollections={false} />,
    );
    await userEvent.click(screen.getByRole('button', { name: /dismiss welcome/i }));
    expect(container).toBeEmptyDOMElement();
    rerender(<WelcomeCard key="v1" vaultId="v1" name="Personal" hasFiles={false} hasCollections={false} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<WelcomeCard key="v2" vaultId="v2" name="Work" hasFiles={false} hasCollections={false} />);
    expect(screen.getByRole('heading', { name: /your vault is ready/i })).toBeInTheDocument();
  });
});
