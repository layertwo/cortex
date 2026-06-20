import {
  encrypt,
  decrypt,
  stringToBytes,
  bytesToString,
  bytesToBase64,
  base64ToBytes,
} from '@cortex/encryption';

const VERIFIER_CONSTANT = 'cortex-vault-verifier-v1';
const STORAGE_PREFIX = 'cortex_vault_verifier_';

export async function createVerifier(metadataKey: Uint8Array): Promise<string> {
  const ct = await encrypt(stringToBytes(VERIFIER_CONSTANT), metadataKey);
  return bytesToBase64(ct);
}

export function checkVerifier(stored: string, metadataKey: Uint8Array): boolean {
  try {
    const pt = decrypt(base64ToBytes(stored), metadataKey);
    return bytesToString(pt) === VERIFIER_CONSTANT;
  } catch {
    return false;
  }
}

export function saveVerifier(vaultId: string, blob: string): void {
  localStorage.setItem(STORAGE_PREFIX + vaultId, blob);
}

export function loadVerifier(vaultId: string): string | null {
  return localStorage.getItem(STORAGE_PREFIX + vaultId);
}
