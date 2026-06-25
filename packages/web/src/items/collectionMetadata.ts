import { encrypt, decrypt, stringToBytes, bytesToString } from '@cortex/encryption';

// A collection's only metadata today is its name. Encrypted with the vault's
// metadataKey (reversible) so the sidebar can display it. Server stores opaque bytes.
export async function encryptCollectionName(name: string, metadataKey: Uint8Array): Promise<Uint8Array> {
  return encrypt(stringToBytes(JSON.stringify({ name })), metadataKey);
}

export function decryptCollectionName(blob: Uint8Array, metadataKey: Uint8Array): string {
  return (JSON.parse(bytesToString(decrypt(blob, metadataKey))) as { name: string }).name;
}
