import { decryptFileWithDek } from '@cortex/encryption';
import { decodeItemBlob } from './itemBlob';
import { type FileMetadata } from './metadata';

// Legacy (Slice 2) whole-buffer download path. New uploads use the chunked
// streaming format (see streamingUpload.ts); the download path selects this only
// when metadata has no streamVersion. Kept for objects uploaded before 2.5c.
export function decryptDownloadedBlob(
  blob: Uint8Array,
  metadata: FileMetadata,
  kek: Uint8Array,
): Uint8Array {
  const { wrappedDek, ciphertext } = decodeItemBlob(blob);
  return decryptFileWithDek(ciphertext, wrappedDek, kek, metadata.contentId);
}
