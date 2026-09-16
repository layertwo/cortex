import { describe, it, expect, vi, beforeEach } from 'vitest';

const { retrieveKeys } = vi.hoisted(() => ({ retrieveKeys: vi.fn() }));
vi.mock('@cortex/encryption', () => ({ retrieveKeys }));

import { getVaultKeys } from './keyAccess';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem('cortex_account', 'u1');
});

describe('getVaultKeys', () => {
  it('returns vaultId + kek + metadataKey from key-storage and kekVersion from the registry', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal', kekVersion: 3 }]));
    retrieveKeys.mockResolvedValueOnce({
      keyEncryptionKey: new Uint8Array(32).fill(1),
      metadataEncryptionKey: new Uint8Array(32).fill(2),
    });
    const out = await getVaultKeys();
    expect(out.vaultId).toBe('v1');
    expect(out.kek).toEqual(new Uint8Array(32).fill(1));
    expect(out.metadataKey).toEqual(new Uint8Array(32).fill(2));
    expect(out.kekVersion).toBe(3);
    expect(retrieveKeys).toHaveBeenCalledWith('v1');
  });

  it('defaults kekVersion to 1 when the registry has no version for the vault', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    retrieveKeys.mockResolvedValueOnce({
      keyEncryptionKey: new Uint8Array(32).fill(1),
      metadataEncryptionKey: new Uint8Array(32).fill(2),
    });
    expect((await getVaultKeys()).kekVersion).toBe(1);
  });

  it('throws when there is no vault id', async () => {
    await expect(getVaultKeys()).rejects.toThrow('locked');
  });

  it('throws when there is no account, even if a legacy pointer exists', async () => {
    localStorage.removeItem('cortex_account');
    localStorage.setItem('cortex_vault_id', 'v1');
    await expect(getVaultKeys()).rejects.toThrow('locked');
    expect(retrieveKeys).not.toHaveBeenCalled();
  });

  it('throws when keys are absent/expired', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    retrieveKeys.mockResolvedValueOnce(null);
    await expect(getVaultKeys()).rejects.toThrow('locked');
  });
});
