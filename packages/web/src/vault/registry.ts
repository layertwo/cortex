// Device-local list of vaults this browser knows about. The backend has no ListVaults yet
// (design follow-up 1), so this is the only source of "which vaults exist" on a device.
// `cortex_vault_id` keeps its historical role as the active-vault pointer; keyAccess.ts
// and the encryption key store read it.
export type VaultEntry = { vaultId: string; name: string; lastOpened?: number };

export const DEFAULT_VAULT_NAME = 'Personal';

const REGISTRY_KEY = 'cortex_vaults';
const ACTIVE_KEY = 'cortex_vault_id';

function save(list: VaultEntry[]): void {
  localStorage.setItem(REGISTRY_KEY, JSON.stringify(list));
}

export function listVaults(): VaultEntry[] {
  let list: VaultEntry[] = [];
  try {
    list = JSON.parse(localStorage.getItem(REGISTRY_KEY) ?? '[]') as VaultEntry[];
    if (!Array.isArray(list)) list = [];
  } catch {
    list = [];
  }
  if (list.length === 0) {
    // Migration: a device set up before the registry existed has only the pointer.
    const legacy = localStorage.getItem(ACTIVE_KEY);
    if (legacy) {
      list = [{ vaultId: legacy, name: DEFAULT_VAULT_NAME }];
      save(list);
    }
  }
  return list;
}

export function upsertVault(entry: VaultEntry): void {
  const list = listVaults();
  const i = list.findIndex((v) => v.vaultId === entry.vaultId);
  if (i === -1) list.push(entry);
  else list[i] = { ...list[i], ...entry };
  save(list);
}

export function activeVaultId(): string | null {
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveVault(vaultId: string): void {
  localStorage.setItem(ACTIVE_KEY, vaultId);
}
