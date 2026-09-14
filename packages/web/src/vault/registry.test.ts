import { describe, it, expect, beforeEach } from 'vitest';
import { listVaults, upsertVault, activeVaultId, setActiveVault } from './registry';

beforeEach(() => localStorage.clear());

describe('vault registry', () => {
  it('starts empty', () => {
    expect(listVaults()).toEqual([]);
    expect(activeVaultId()).toBeNull();
  });

  it('seeds a Personal entry from a legacy cortex_vault_id', () => {
    localStorage.setItem('cortex_vault_id', 'v-old');
    expect(listVaults()).toEqual([{ vaultId: 'v-old', name: 'Personal' }]);
    expect(activeVaultId()).toBe('v-old');
  });

  it('upserts by vaultId and keeps insertion order', () => {
    upsertVault({ vaultId: 'a', name: 'Personal' });
    upsertVault({ vaultId: 'b', name: 'Family' });
    upsertVault({ vaultId: 'a', name: 'Personal', lastOpened: 5 });
    expect(listVaults()).toEqual([
      { vaultId: 'a', name: 'Personal', lastOpened: 5 },
      { vaultId: 'b', name: 'Family' },
    ]);
  });

  it('renames and tracks the active vault through the legacy key', () => {
    upsertVault({ vaultId: 'a', name: 'Personal' });
    upsertVault({ vaultId: 'a', name: 'Me' });
    setActiveVault('a');
    expect(listVaults()[0].name).toBe('Me');
    expect(activeVaultId()).toBe('a');
    expect(localStorage.getItem('cortex_vault_id')).toBe('a');
  });

  it('survives a corrupt registry value', () => {
    localStorage.setItem('cortex_vaults', '{not json');
    expect(listVaults()).toEqual([]);
  });
});
