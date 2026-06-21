import { retrieveKeys } from '@cortex/encryption';

const VAULT_ID_KEY = 'cortex_vault_id';

export async function getVaultKeys(): Promise<{
  vaultId: string;
  kek: Uint8Array;
  metadataKey: Uint8Array;
}> {
  const vaultId = localStorage.getItem(VAULT_ID_KEY);
  if (!vaultId) throw new Error('Vault is locked — unlock it again');
  const keys = await retrieveKeys(vaultId);
  if (!keys) throw new Error('Vault is locked — unlock it again');
  return { vaultId, kek: keys.keyEncryptionKey, metadataKey: keys.metadataEncryptionKey };
}
