// Per-account cache of the vaults this browser knows about, seeded and merged from
// ListVaults on every sign-in (syncFromServer). Keys are namespaced by the Cognito
// subject resolved in auth/account.ts: `cortex_vaults:<sub>` holds the list and
// `cortex_vault_id:<sub>` is the active-vault pointer read by keyAccess.ts.
// `vaultSalt` and the decrypted `name` are session-only: save() strips both.
// Salt with a wrapped envelope is an offline password-guessing oracle, and a
// plaintext name on disk would outlive the vault password. SessionContext keeps
// the merged list (including both) in React state for the session.
import type { RotationState, VaultSummary } from '@cortex/client';
import { bytesToBase64 } from '@cortex/encryption';
import { getAccountId } from '../auth/account';

export type VaultEntry = {
  vaultId: string;
  name?: string; // decrypted display name; session-only until the vault is unlocked
  lastOpened?: number;
  encryptedName?: string; // bytesToBase64(summary.encryptedName)
  currentVmkVersion?: number;
  rotationState?: RotationState;
  vaultSalt?: Uint8Array; // memory only; stripped by save()
};

// upsertVault accepts a partial patch keyed by vaultId; a full VaultEntry is also a VaultPatch.
export type VaultPatch = Pick<VaultEntry, 'vaultId'> & Partial<VaultEntry>;

export const DEFAULT_VAULT_NAME = 'Personal';
export const LOCKED_VAULT_NAME = 'Locked vault';

/** Display label for a vault whose name has not been decrypted this session. */
export function vaultLabel(entry: Pick<VaultEntry, 'name'>): string {
  return entry.name ?? LOCKED_VAULT_NAME;
}

const LEGACY_REGISTRY_KEY = 'cortex_vaults';
const LEGACY_ACTIVE_KEY = 'cortex_vault_id';

function registryKey(account: string): string {
  return `cortex_vaults:${account}`;
}

function activeKey(account: string): string {
  return `cortex_vault_id:${account}`;
}

function requireAccount(): string {
  const account = getAccountId();
  if (!account) throw new Error('No account resolved');
  return account;
}

function parse(raw: string | null): VaultEntry[] {
  try {
    const list = JSON.parse(raw ?? '[]') as unknown;
    if (!Array.isArray(list)) return [];
    // Older builds persisted plaintext names; drop them on read so they are neither
    // displayed nor written back.
    return list.map((entry) => {
      const { name: _name, ...rest } = entry as VaultEntry;
      return rest;
    });
  } catch {
    return [];
  }
}

function persistable(entry: VaultEntry): VaultEntry {
  const copy = { ...entry };
  delete copy.vaultSalt;
  delete copy.name;
  return copy;
}

function save(list: VaultEntry[]): void {
  localStorage.setItem(registryKey(requireAccount()), JSON.stringify(list.map(persistable)));
}

export function listVaults(): VaultEntry[] {
  const account = getAccountId();
  if (!account) return [];
  return parse(localStorage.getItem(registryKey(account)));
}

export function activeVaultId(): string | null {
  const account = getAccountId();
  if (!account) return null;
  return localStorage.getItem(activeKey(account));
}

export function setActiveVault(vaultId: string): void {
  localStorage.setItem(activeKey(requireAccount()), vaultId);
}

export function upsertVault(entry: VaultPatch): void {
  const list = listVaults();
  const i = list.findIndex((v) => v.vaultId === entry.vaultId);
  if (i === -1) list.push({ ...entry });
  else list[i] = { ...list[i], ...entry };
  save(list);
}

export function removeVault(vaultId: string): void {
  const account = requireAccount();
  save(listVaults().filter((v) => v.vaultId !== vaultId));
  if (localStorage.getItem(activeKey(account)) === vaultId) {
    localStorage.removeItem(activeKey(account));
  }
}

// A device set up before the account gate has un-namespaced `cortex_vaults` /
// `cortex_vault_id` (or only the pointer, from before the registry existed). On the first
// gate they move under the current account when its registry is still empty; the legacy
// keys are deleted either way. The ListVaults merge then confirms or drops the entries.
export function migrateLegacyRegistry(): void {
  const account = requireAccount();
  const legacyActive = localStorage.getItem(LEGACY_ACTIVE_KEY);
  if (listVaults().length === 0) {
    let list = parse(localStorage.getItem(LEGACY_REGISTRY_KEY));
    if (list.length === 0 && legacyActive) list = [{ vaultId: legacyActive }];
    if (list.length > 0) save(list);
    if (legacyActive && list.some((v) => v.vaultId === legacyActive)) {
      localStorage.setItem(activeKey(account), legacyActive);
    }
  }
  localStorage.removeItem(LEGACY_REGISTRY_KEY);
  localStorage.removeItem(LEGACY_ACTIVE_KEY);
}

// Server fields win (encryptedName, currentVmkVersion, rotationState persisted; vaultSalt
// and name in memory only); `memory` carries this session's names/salts so a sign-in
// refresh does not hide them; entries the server no longer lists are dropped and the
// active pointer is cleared if it pointed at one.
export function syncFromServer(vaults: VaultSummary[], memory: VaultEntry[] = []): VaultEntry[] {
  const account = requireAccount();
  const merged: VaultEntry[] = [];
  for (const summary of vaults) {
    if (!summary.vaultId || !summary.vaultSalt) continue;
    const prev = memory.find((v) => v.vaultId === summary.vaultId);
    const entry: VaultEntry = {
      ...prev,
      vaultId: summary.vaultId,
      encryptedName: summary.encryptedName ? bytesToBase64(summary.encryptedName) : undefined,
      currentVmkVersion: summary.currentVmkVersion ?? 0,
      rotationState: summary.rotationState ?? 'IDLE',
      vaultSalt: summary.vaultSalt,
    };
    merged.push(entry);
  }
  save(merged);
  const active = localStorage.getItem(activeKey(account));
  if (active && !merged.some((v) => v.vaultId === active)) localStorage.removeItem(activeKey(account));
  return merged;
}
