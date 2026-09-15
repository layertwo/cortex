import { describe, it, expect, beforeEach } from 'vitest';
import type { VaultSummary } from '@cortex/client';
import {
  listVaults,
  upsertVault,
  activeVaultId,
  setActiveVault,
  renameInRegistry,
  removeVault,
  migrateLegacyRegistry,
  syncFromServer,
} from './registry';

const utf8 = (s: string) => new TextEncoder().encode(s);
const b64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes));

function summary(vaultId: string, extra: Partial<VaultSummary> = {}): VaultSummary {
  return {
    vaultId,
    vaultSalt: new Uint8Array(16).fill(7),
    createdAt: new Date(0),
    updatedAt: new Date(0),
    kekVersion: 1,
    rotationState: 'IDLE',
    ...extra,
  };
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('cortex_account', 'u1');
});

describe('vault registry', () => {
  it('starts empty', () => {
    expect(listVaults()).toEqual([]);
    expect(activeVaultId()).toBeNull();
  });

  it('upserts by vaultId and keeps insertion order under the namespaced key', () => {
    upsertVault({ vaultId: 'a', name: 'Personal' });
    upsertVault({ vaultId: 'b', name: 'Family' });
    upsertVault({ vaultId: 'a', name: 'Personal', lastOpened: 5 });
    expect(listVaults()).toEqual([
      { vaultId: 'a', name: 'Personal', lastOpened: 5 },
      { vaultId: 'b', name: 'Family' },
    ]);
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!)).toHaveLength(2);
    expect(localStorage.getItem('cortex_vaults')).toBeNull();
  });

  it('tracks the active vault through the namespaced pointer', () => {
    upsertVault({ vaultId: 'a', name: 'Personal' });
    setActiveVault('a');
    expect(activeVaultId()).toBe('a');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('a');
    expect(localStorage.getItem('cortex_vault_id')).toBeNull();
  });

  it('renameInRegistry changes only the name', () => {
    upsertVault({ vaultId: 'a', name: 'Personal', lastOpened: 3, kekVersion: 2 });
    renameInRegistry('a', 'Me');
    expect(listVaults()).toEqual([{ vaultId: 'a', name: 'Me', lastOpened: 3, kekVersion: 2 }]);
  });

  it('never persists vaultSalt or verifier', () => {
    upsertVault({ vaultId: 'a', name: 'Personal', vaultSalt: new Uint8Array(16), verifier: 'blob' });
    const raw = localStorage.getItem('cortex_vaults:u1')!;
    expect(raw).not.toContain('vaultSalt');
    expect(raw).not.toContain('verifier');
    expect(listVaults()).toEqual([{ vaultId: 'a', name: 'Personal' }]);
  });

  it('survives a corrupt registry value', () => {
    localStorage.setItem('cortex_vaults:u1', '{not json');
    expect(listVaults()).toEqual([]);
  });

  it('isolates accounts', () => {
    upsertVault({ vaultId: 'a', name: 'Personal' });
    setActiveVault('a');
    localStorage.setItem('cortex_account', 'u2');
    expect(listVaults()).toEqual([]);
    expect(activeVaultId()).toBeNull();
  });

  it('removeVault drops the entry and clears a matching active pointer', () => {
    upsertVault({ vaultId: 'a', name: 'Personal' });
    upsertVault({ vaultId: 'b', name: 'Work' });
    setActiveVault('a');
    removeVault('a');
    expect(listVaults()).toEqual([{ vaultId: 'b', name: 'Work' }]);
    expect(activeVaultId()).toBeNull();
    setActiveVault('b');
    removeVault('zzz');
    expect(activeVaultId()).toBe('b');
  });
});

describe('without a resolved account', () => {
  beforeEach(() => localStorage.removeItem('cortex_account'));

  it('readers return empty', () => {
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'old', name: 'Personal' }]));
    localStorage.setItem('cortex_vault_id', 'old');
    expect(listVaults()).toEqual([]);
    expect(activeVaultId()).toBeNull();
  });

  it('writers throw', () => {
    expect(() => upsertVault({ vaultId: 'a', name: 'Personal' })).toThrow('No account resolved');
    expect(() => setActiveVault('a')).toThrow('No account resolved');
    expect(() => renameInRegistry('a', 'x')).toThrow('No account resolved');
    expect(() => removeVault('a')).toThrow('No account resolved');
    expect(() => migrateLegacyRegistry()).toThrow('No account resolved');
    expect(() => syncFromServer([])).toThrow('No account resolved');
  });
});

describe('migrateLegacyRegistry', () => {
  it('moves the legacy list and pointer under the account and deletes the legacy keys', () => {
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Me' }, { vaultId: 'v2', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id', 'v2');
    migrateLegacyRegistry();
    expect(listVaults()).toEqual([{ vaultId: 'v1', name: 'Me' }, { vaultId: 'v2', name: 'Work' }]);
    expect(activeVaultId()).toBe('v2');
    expect(localStorage.getItem('cortex_vaults')).toBeNull();
    expect(localStorage.getItem('cortex_vault_id')).toBeNull();
  });

  it('seeds a Personal entry from a pointer-only legacy device', () => {
    localStorage.setItem('cortex_vault_id', 'v-old');
    migrateLegacyRegistry();
    expect(listVaults()).toEqual([{ vaultId: 'v-old', name: 'Personal' }]);
    expect(activeVaultId()).toBe('v-old');
    expect(localStorage.getItem('cortex_vault_id')).toBeNull();
  });

  it('leaves a populated namespaced registry alone but still deletes the legacy keys', () => {
    upsertVault({ vaultId: 'mine', name: 'Mine' });
    setActiveVault('mine');
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Me' }]));
    localStorage.setItem('cortex_vault_id', 'v1');
    migrateLegacyRegistry();
    expect(listVaults()).toEqual([{ vaultId: 'mine', name: 'Mine' }]);
    expect(activeVaultId()).toBe('mine');
    expect(localStorage.getItem('cortex_vaults')).toBeNull();
    expect(localStorage.getItem('cortex_vault_id')).toBeNull();
  });

  it('is a no-op with nothing to migrate', () => {
    migrateLegacyRegistry();
    expect(listVaults()).toEqual([]);
    expect(activeVaultId()).toBeNull();
  });
});

describe('syncFromServer', () => {
  it('server fields win, device keeps name and lastOpened, memory fields are returned but not persisted', () => {
    upsertVault({ vaultId: 'v1', name: 'Me', lastOpened: 42, kekVersion: 1, rotationState: 'IDLE' });
    const encryptedName = new Uint8Array([1, 2, 3]);
    const merged = syncFromServer([
      summary('v1', { encryptedName, verifier: utf8('VER1'), kekVersion: 3, rotationState: 'PAUSED' }),
    ]);
    expect(merged).toEqual([
      {
        vaultId: 'v1',
        name: 'Me',
        lastOpened: 42,
        encryptedName: b64(encryptedName),
        kekVersion: 3,
        rotationState: 'PAUSED',
        vaultSalt: new Uint8Array(16).fill(7),
        verifier: 'VER1',
      },
    ]);
    expect(listVaults()).toEqual([
      { vaultId: 'v1', name: 'Me', lastOpened: 42, encryptedName: b64(encryptedName), kekVersion: 3, rotationState: 'PAUSED' },
    ]);
    const raw = localStorage.getItem('cortex_vaults:u1')!;
    expect(raw).not.toContain('vaultSalt');
    expect(raw).not.toContain('verifier');
  });

  it('adds unknown vaults with the default name and no memory verifier when the server has none', () => {
    const merged = syncFromServer([summary('v2')]);
    expect(merged).toEqual([
      { vaultId: 'v2', name: 'Personal', kekVersion: 1, rotationState: 'IDLE', vaultSalt: new Uint8Array(16).fill(7) },
    ]);
    expect(merged[0].verifier).toBeUndefined();
    expect(listVaults()).toEqual([{ vaultId: 'v2', name: 'Personal', kekVersion: 1, rotationState: 'IDLE' }]);
  });

  it('drops entries the server no longer lists and clears the active pointer if it pointed at one', () => {
    upsertVault({ vaultId: 'gone', name: 'Old' });
    upsertVault({ vaultId: 'kept', name: 'Kept' });
    setActiveVault('gone');
    syncFromServer([summary('kept')]);
    expect(listVaults().map((v) => v.vaultId)).toEqual(['kept']);
    expect(activeVaultId()).toBeNull();
  });

  it('keeps the active pointer when its vault is still listed', () => {
    upsertVault({ vaultId: 'kept', name: 'Kept' });
    setActiveVault('kept');
    syncFromServer([summary('kept')]);
    expect(activeVaultId()).toBe('kept');
  });

  it('overwrites a stale local verifier blob and leaves a matching or absent one alone', () => {
    localStorage.setItem('cortex_vault_verifier_v1', 'OLD');
    localStorage.setItem('cortex_vault_verifier_v2', 'SAME');
    syncFromServer([
      summary('v1', { verifier: utf8('NEW') }),
      summary('v2', { verifier: utf8('SAME') }),
      summary('v3', { verifier: utf8('V3') }),
    ]);
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBe('NEW');
    expect(localStorage.getItem('cortex_vault_verifier_v2')).toBe('SAME');
    expect(localStorage.getItem('cortex_vault_verifier_v3')).toBeNull();
  });

  it('skips malformed summaries without an id or salt', () => {
    const merged = syncFromServer([{ ...summary('v1'), vaultSalt: undefined }, summary('v2')]);
    expect(merged.map((v) => v.vaultId)).toEqual(['v2']);
  });
});
