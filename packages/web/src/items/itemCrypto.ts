import { encryptFileWithDek, decryptFileWithDek } from '@cortex/encryption';
import { encodeItemBlob, decodeItemBlob } from './itemBlob';
import { encryptMetadata, type FileMetadata } from './metadata';

export async function encryptFileForUpload(
  bytes: Uint8Array,
  name: string,
  contentType: string,
  keys: { kek: Uint8Array; metadataKey: Uint8Array },
): Promise<{ blob: Uint8Array; encryptedMetadata: Uint8Array; metadata: FileMetadata }> {
  const contentId = crypto.randomUUID();
  // fileId = contentId binds the DEK to this file (HMAC); wrappedDek is 97 bytes.
  const { encryptedContent, wrappedDek } = await encryptFileWithDek(bytes, keys.kek, contentId);
  const blob = encodeItemBlob(wrappedDek, encryptedContent);
  const metadata: FileMetadata = { name, contentType, size: bytes.length, contentId };
  const encryptedMetadata = await encryptMetadata(metadata, keys.metadataKey);
  return { blob, encryptedMetadata, metadata };
}

export function decryptDownloadedBlob(
  blob: Uint8Array,
  metadata: FileMetadata,
  kek: Uint8Array,
): Uint8Array {
  const { wrappedDek, ciphertext } = decodeItemBlob(blob);
  return decryptFileWithDek(ciphertext, wrappedDek, kek, metadata.contentId);
}
