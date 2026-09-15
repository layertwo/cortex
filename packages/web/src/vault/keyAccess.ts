import { retrieveKeys } from '@cortex/encryption';
import { activeVaultId, listVaults } from './registry';

export async function getVaultKeys(): Promise<{
  vaultId: string;
  kek: Uint8Array;
  metadataKey: Uint8Array;
  kekVersion: number;
}> {
  const vaultId = activeVaultId();
  if (!vaultId) throw new Error('Vault is locked, unlock it again');
  const keys = await retrieveKeys(vaultId);
  if (!keys) throw new Error('Vault is locked, unlock it again');
  const kekVersion = listVaults().find((v) => v.vaultId === vaultId)?.kekVersion ?? 1;
  return { vaultId, kek: keys.keyEncryptionKey, metadataKey: keys.metadataEncryptionKey, kekVersion };
}
