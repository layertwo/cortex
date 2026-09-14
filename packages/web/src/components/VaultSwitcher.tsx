import { DropdownMenu, type DropdownMenuOption } from '@astryxdesign/core/DropdownMenu';
import { useSession } from '../auth/SessionContext';
import type { VaultEntry } from '../vault/registry';

// Sidebar control for the active vault. Vaults already unlocked on this device switch
// instantly; locked ones hand off to the parent, which opens UnlockVaultDialog.
export default function VaultSwitcher({
  onLocked,
  onNew,
  onManage,
}: {
  onLocked: (vault: VaultEntry) => void;
  onNew: () => void;
  onManage: () => void;
}) {
  const { vaults, activeVault, switchVault } = useSession();
  const current = activeVault?.name ?? 'Vault';

  async function pick(v: VaultEntry) {
    if (v.vaultId === activeVault?.vaultId) return;
    if ((await switchVault(v.vaultId)) === 'locked') onLocked(v);
  }

  const items: DropdownMenuOption[] = [
    ...vaults.map<DropdownMenuOption>((v) => ({
      id: v.vaultId,
      label: v.name,
      description: v.vaultId === activeVault?.vaultId ? 'Open' : undefined,
      onClick: () => void pick(v),
    })),
    { type: 'divider' },
    { label: 'New vault', onClick: onNew },
    { label: 'Manage vaults', onClick: onManage },
  ];

  return (
    <DropdownMenu
      button={{ label: `Switch vault, current: ${current}`, children: current, variant: 'secondary', size: 'sm', width: '100%' }}
      items={items}
      menuWidth={240}
    />
  );
}
