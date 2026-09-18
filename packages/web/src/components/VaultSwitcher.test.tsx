import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const { session } = vi.hoisted(() => ({
  session: {
    vaults: [
      { vaultId: 'v1', name: 'Personal' },
      { vaultId: 'v2', name: 'Family archive' },
    ],
    activeVault: { vaultId: 'v1', name: 'Personal' },
    switchVault: vi.fn(async (): Promise<'unlocked' | 'locked'> => 'locked'),
  },
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => session }));

import VaultSwitcher from './VaultSwitcher';

describe('VaultSwitcher', () => {
  it('names the current vault on the trigger and lists every vault plus the two actions', async () => {
    render(<VaultSwitcher onLocked={vi.fn()} onNew={vi.fn()} onManage={vi.fn()} />);
    const trigger = screen.getByRole('button', { name: /switch vault, current: personal/i });
    expect(trigger).toHaveTextContent('Personal');
    await userEvent.click(trigger);
    expect(screen.getByRole('menuitem', { name: /family archive/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /new vault/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /manage vaults/i })).toBeInTheDocument();
  });

  it('asks the parent to unlock when the chosen vault has no keys here', async () => {
    const onLocked = vi.fn();
    render(<VaultSwitcher onLocked={onLocked} onNew={vi.fn()} onManage={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /switch vault/i }));
    await userEvent.click(screen.getByRole('menuitem', { name: /family archive/i }));
    await waitFor(() => expect(session.switchVault).toHaveBeenCalledWith('v2'));
    expect(onLocked).toHaveBeenCalledWith({ vaultId: 'v2', name: 'Family archive' });
  });

  it('routes New vault and Manage vaults to the parent', async () => {
    const onNew = vi.fn();
    const onManage = vi.fn();
    render(<VaultSwitcher onLocked={vi.fn()} onNew={onNew} onManage={onManage} />);
    await userEvent.click(screen.getByRole('button', { name: /switch vault/i }));
    await userEvent.click(screen.getByRole('menuitem', { name: /new vault/i }));
    expect(onNew).toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: /switch vault/i }));
    await userEvent.click(screen.getByRole('menuitem', { name: /manage vaults/i }));
    expect(onManage).toHaveBeenCalled();
  });
});
