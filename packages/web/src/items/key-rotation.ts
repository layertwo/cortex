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
import { updateCollection, listAllCollections } from '../api/collections';

const ITEM_RETRIES = 3;

// Exact server text of the collection 409 (global constraints §10): a concurrent write (e.g. a
// rename on another device) moved the row out from under the version this sweep last saw.
const COLLECTION_CONFLICT_MESSAGE = 'Collection was modified on another device; reload and retry';

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

// Re-encrypt every collection name still under the old metadata key. `metadataVersion` is the
// KEK version whose key encrypts the row (absent means 1); rows already at `targetVersion` were
// re-keyed by an earlier attempt and are skipped, so the sweep resumes where it stopped. Each
// update is retried like items (a 409 from a concurrent rename included), then rethrown so the
// caller can pause the rotation.
export async function rotateCollections(
  collections: CollectionData[],
  oldMetadataKey: Uint8Array,
  newMetadataKey: Uint8Array,
  vaultId: string,
  targetVersion: number,
): Promise<void> {
  for (const col of collections) {
    let current = col.metadataVersion ?? 1;
    let encryptedMetadata = col.encryptedMetadata;
    if (!encryptedMetadata || current >= targetVersion) continue;

    let lastErr: unknown;
    for (let attempt = 0; attempt <= ITEM_RETRIES; attempt++) {
      try {
        const name = decryptCollectionName(encryptedMetadata, oldMetadataKey);
        const newMeta = await encryptCollectionName(name, newMetadataKey);
        await updateCollection(col.collectionId!, vaultId, newMeta, targetVersion, current);
        lastErr = undefined;
        break;
      } catch (err) {
        lastErr = err;
        if (err instanceof Error && err.message === COLLECTION_CONFLICT_MESSAGE) {
          // The expected version we sent is now stale (e.g. a concurrent rename bumped it) and
          // would 409 forever if resent as-is: re-read the row and retry with what it holds now.
          const fresh = (await listAllCollections(vaultId)).find((c) => c.collectionId === col.collectionId);
          if (!fresh || !fresh.encryptedMetadata || (fresh.metadataVersion ?? 1) >= targetVersion) {
            lastErr = undefined;
            break;
          }
          current = fresh.metadataVersion ?? 1;
          encryptedMetadata = fresh.encryptedMetadata;
        }
        if (attempt < ITEM_RETRIES) {
          await new Promise((r) => setTimeout(r, 200 * 2 ** attempt));
        }
      }
    }
    if (lastErr) throw lastErr;
  }
}
