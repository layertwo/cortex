import { encrypt, decrypt, bytesToBase64, base64ToBytes } from '@cortex/encryption';

const PREFIX = 'cortex_rotation_bridge_';

function key(vaultId: string): string {
  return PREFIX + vaultId;
}

function concat(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

// Encrypt oldKek ‖ oldMetadataKey (64 bytes) with newKek; store as base64 in localStorage.
export async function saveBridge(
  vaultId: string,
  oldKek: Uint8Array,
  oldMetadataKey: Uint8Array,
  newKek: Uint8Array,
): Promise<void> {
  const plain = concat(oldKek, oldMetadataKey);
  const ct = await encrypt(plain, newKek);
  localStorage.setItem(key(vaultId), bytesToBase64(ct));
}

// Decrypt and return oldKek + oldMetadataKey. Returns null if absent or decryption fails.
export function loadBridge(
  vaultId: string,
  newKek: Uint8Array,
): { oldKek: Uint8Array; oldMetadataKey: Uint8Array } | null {
  const stored = localStorage.getItem(key(vaultId));
  if (!stored) return null;
  try {
    const plain = decrypt(base64ToBytes(stored), newKek);
    return { oldKek: plain.slice(0, 32), oldMetadataKey: plain.slice(32, 64) };
  } catch {
    return null;
  }
}

export function clearBridge(vaultId: string): void {
  localStorage.removeItem(key(vaultId));
}

export function hasBridge(vaultId: string): boolean {
  return localStorage.getItem(key(vaultId)) !== null;
}
