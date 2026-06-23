import { encrypt, decrypt, stringToBytes, bytesToString } from '@cortex/encryption';

export interface FileMetadata {
  name: string;
  contentType: string;
  size: number;
  contentId: string;
  // Set to STREAM_VERSION for chunked-stream uploads (2.5c). Absent ⇒ legacy
  // Slice 2 whole-buffer object; the download path dispatches on this.
  streamVersion?: number;
}

// Adapted for #208: the Smithy `encryptedMetadata` field is a Blob (Uint8Array)
// that the generated SDK base64-encodes on the wire. So this codec produces and
// consumes raw ciphertext bytes — no manual base64 (that would double-encode).
export async function encryptMetadata(meta: FileMetadata, metadataKey: Uint8Array): Promise<Uint8Array> {
  return encrypt(stringToBytes(JSON.stringify(meta)), metadataKey);
}

export function decryptMetadata(ciphertext: Uint8Array, metadataKey: Uint8Array): FileMetadata {
  const json = bytesToString(decrypt(ciphertext, metadataKey));
  return JSON.parse(json) as FileMetadata;
}
