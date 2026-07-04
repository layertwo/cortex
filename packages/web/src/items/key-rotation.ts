import {
  wrapDek,
  unwrapDek,
  encryptTagForSearch,
} from '@cortex/encryption';
import type { ItemData } from '@cortex/client';
import type { CollectionData } from '@cortex/client';
import { decryptMetadata, encryptMetadata } from './metadata';
import { decryptCollectionName, encryptCollectionName } from './collectionMetadata';
import { updateItemRotation } from '../api/items';
import { updateCollection } from '../api/collections';

const ITEM_RETRIES = 3;

export async function reWrapDek(
  wrappedDek: Uint8Array,
  oldKek: Uint8Array,
  newKek: Uint8Array,
  contentId: string,
): Promise<Uint8Array> {
  const dek = unwrapDek(wrappedDek, oldKek, contentId);
  return wrapDek(dek, newKek, contentId);
}

export interface RotateItemsArgs {
  vaultId: string;
  items: ItemData[];
  targetDekVersion: number;
  oldKek: Uint8Array;
  newKek: Uint8Array;
  oldMetadataKey: Uint8Array;
  newMetadataKey: Uint8Array;
  onProgress?: (done: number, total: number) => void;
}

// Sweep: for each item at dekVersion < targetDekVersion, re-wrap DEK and
// re-encrypt metadata + tags under the new keys. Retries each item ITEM_RETRIES times.
export async function rotateItems({
  vaultId,
  items,
  targetDekVersion,
  oldKek,
  newKek,
  oldMetadataKey,
  newMetadataKey,
  onProgress,
}: RotateItemsArgs): Promise<void> {
  let done = 0;
  const pending = items.filter(
    (it) => it.itemType === 'MEDIA' && (it.dekVersion ?? 0) < targetDekVersion,
  );

  for (const item of pending) {
    if (!item.wrappedDek || !item.encryptedMetadata) {
      done++;
      onProgress?.(done, pending.length);
      continue;
    }

    const meta = decryptMetadata(item.encryptedMetadata, oldMetadataKey);
    const contentId = meta.contentId;

    let lastErr: unknown;
    for (let attempt = 0; attempt <= ITEM_RETRIES; attempt++) {
      try {
        const newWrappedDek = await reWrapDek(item.wrappedDek, oldKek, newKek, contentId);
        const newEncryptedMetadata = await encryptMetadata(meta, newMetadataKey);
        const tags = meta.tags ?? [];
        const newEncryptedTags = tags.map((t) => encryptTagForSearch(t, newMetadataKey, vaultId));

        await updateItemRotation(
          item.itemId!,
          newWrappedDek,
          targetDekVersion,
          newEncryptedMetadata,
          newEncryptedTags,
          item.version!,
        );
        lastErr = undefined;
        break;
      } catch (err) {
        lastErr = err;
        if (attempt < ITEM_RETRIES) {
          await new Promise((r) => setTimeout(r, 200 * 2 ** attempt));
        }
      }
    }
    // All retries exhausted — rethrow so the caller can set rotationState=PAUSED.
    // The item's dekVersion is unchanged, so resume will retry it.
    if (lastErr) throw lastErr;

    done++;
    onProgress?.(done, pending.length);
  }
}

// Re-encrypt all collection names (metadata) under the new metadataKey.
export async function rotateCollections(
  collections: CollectionData[],
  oldMetadataKey: Uint8Array,
  newMetadataKey: Uint8Array,
  vaultId: string,
): Promise<void> {
  for (const col of collections) {
    if (!col.encryptedMetadata) continue;
    const name = decryptCollectionName(col.encryptedMetadata, oldMetadataKey);
    const newMeta = await encryptCollectionName(name, newMetadataKey);
    await updateCollection(col.collectionId!, vaultId, newMeta);
  }
}
