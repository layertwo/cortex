import { describe, it, expect, vi, beforeEach } from 'vitest';

const { retrieveKeys } = vi.hoisted(() => ({ retrieveKeys: vi.fn() }));
vi.mock('@cortex/encryption', () => ({ retrieveKeys }));

import { getVaultKeys } from './keyAccess';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('getVaultKeys', () => {
  it('returns vaultId + kek + metadataKey from key-storage', async () => {
    localStorage.setItem('cortex_vault_id', 'v1');
    retrieveKeys.mockResolvedValue({
      keyEncryptionKey: new Uint8Array(32).fill(1),
      metadataEncryptionKey: new Uint8Array(32).fill(2),
    });
    const out = await getVaultKeys();
    expect(out.vaultId).toBe('v1');
    expect(out.kek).toEqual(new Uint8Array(32).fill(1));
    expect(out.metadataKey).toEqual(new Uint8Array(32).fill(2));
    expect(retrieveKeys).toHaveBeenCalledWith('v1');
  });

  it('throws when there is no vault id', async () => {
    await expect(getVaultKeys()).rejects.toThrow('locked');
  });

  it('throws when keys are absent/expired', async () => {
    localStorage.setItem('cortex_vault_id', 'v1');
    retrieveKeys.mockResolvedValue(null);
    await expect(getVaultKeys()).rejects.toThrow('locked');
  });
});
