import { describe, it, expect, vi, beforeEach } from 'vitest';
import { wrapDek, unwrapDek, generateDek, encryptTagForSearch } from '@cortex/encryption';
import type { ItemData, CollectionData } from '@cortex/client';
import { encryptMetadata, decryptMetadata, type FileMetadata } from './metadata';
import { encryptCollectionName, decryptCollectionName } from './collectionMetadata';

// key-rotation.ts calls the real network-facing API functions, so they must be
// mocked here (same convention as streamingUpload.test.ts): everything else
// (crypto, metadata codecs) runs for real so the tests exercise the actual
// re-wrap/re-encrypt logic end-to-end.
const itemsApi = vi.hoisted(() => ({ updateItemRotation: vi.fn() }));
vi.mock('../api/items', () => itemsApi);

const collectionsApi = vi.hoisted(() => ({ updateCollection: vi.fn() }));
vi.mock('../api/collections', () => collectionsApi);

import { reWrapDek, rotateItems, rotateCollections } from './key-rotation';

const oldKek = new Uint8Array(32).fill(0xaa);
const newKek = new Uint8Array(32).fill(0xbb);
const oldMetadataKey = new Uint8Array(32).fill(0x11);
const newMetadataKey = new Uint8Array(32).fill(0x22);
const vaultId = 'v1';

describe('reWrapDek', () => {
  it('re-wraps so the new KEK unwraps to the same DEK', async () => {
    const dek = await generateDek();
    const contentId = crypto.randomUUID();
    const oldWrapped = await wrapDek(dek, oldKek, contentId);

    const newWrapped = await reWrapDek(oldWrapped, oldKek, newKek, contentId);

    const recovered = unwrapDek(newWrapped, newKek, contentId);
    expect(Array.from(recovered)).toEqual(Array.from(dek));
  });

  it('throws when the old KEK is wrong (HMAC binding check)', async () => {
    const contentId = crypto.randomUUID();
    const dek = await generateDek();
    const wrapped = await wrapDek(dek, oldKek, contentId);
    const wrongKek = new Uint8Array(32).fill(0x99);
    await expect(reWrapDek(wrapped, wrongKek, newKek, contentId)).rejects.toThrow();
  });
});

describe('reWrapDek property: any 32-byte keys + random contentId', () => {
  it('re-wrap is always reversible', async () => {
    for (let i = 0; i < 20; i++) {
      const k1 = crypto.getRandomValues(new Uint8Array(32));
      const k2 = crypto.getRandomValues(new Uint8Array(32));
      const id = crypto.randomUUID();
      const dek = await generateDek();
      const wrapped = await wrapDek(dek, k1, id);
      const rewrapped = await reWrapDek(wrapped, k1, k2, id);
      const recovered = unwrapDek(rewrapped, k2, id);
      expect(Array.from(recovered)).toEqual(Array.from(dek));
    }
  });
});

// Builds a MEDIA ItemData whose wrappedDek/encryptedMetadata are real ciphertext
// (wrapped/encrypted under `kek`/`metadataKey`), so rotateItems' decrypt→re-wrap→
// re-encrypt pipeline runs against genuine data instead of stubs.
async function makeMediaItem(opts: {
  dekVersion: number;
  kek: Uint8Array;
  metadataKey: Uint8Array;
  itemId?: string;
  version?: number;
  tags?: string[];
}): Promise<{ item: ItemData; dek: Uint8Array; meta: FileMetadata }> {
  const contentId = crypto.randomUUID();
  const dek = await generateDek();
  const wrappedDek = await wrapDek(dek, opts.kek, contentId);
  const meta: FileMetadata = {
    name: 'photo.jpg',
    contentType: 'image/jpeg',
    size: 1234,
    contentId,
    tags: opts.tags ?? ['beach', 'sun'],
  };
  const encryptedMetadata = await encryptMetadata(meta, opts.metadataKey);
  const item: ItemData = {
    itemId: opts.itemId ?? crypto.randomUUID(),
    vaultId,
    itemType: 'MEDIA',
    encryptedMetadata,
    wrappedDek,
    dekVersion: opts.dekVersion,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    version: opts.version ?? 1,
  };
  return { item, dek, meta };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('rotateItems', () => {
  it('re-wraps the DEK and re-encrypts metadata + tags for a MEDIA item below targetDekVersion', async () => {
    const { item, dek, meta } = await makeMediaItem({ dekVersion: 1, kek: oldKek, metadataKey: oldMetadataKey });
    itemsApi.updateItemRotation.mockResolvedValue(undefined);

    await rotateItems({
      vaultId,
      items: [item],
      targetDekVersion: 2,
      oldKek,
      newKek,
      oldMetadataKey,
      newMetadataKey,
    });

    expect(itemsApi.updateItemRotation).toHaveBeenCalledTimes(1);
    const [itemId, newWrappedDek, dekVersion, newEncryptedMetadata, newEncryptedTags, expectedVersion] =
      itemsApi.updateItemRotation.mock.calls[0];

    expect(itemId).toBe(item.itemId);
    expect(dekVersion).toBe(2);
    expect(expectedVersion).toBe(item.version);

    // The re-wrapped DEK unwraps under the NEW kek to the same DEK bytes.
    const recoveredDek = unwrapDek(newWrappedDek, newKek, meta.contentId);
    expect(Array.from(recoveredDek)).toEqual(Array.from(dek));

    // The re-encrypted metadata decrypts under the NEW metadataKey to the same content.
    const recoveredMeta = decryptMetadata(newEncryptedMetadata, newMetadataKey);
    expect(recoveredMeta).toEqual(meta);

    // Tags are re-derived deterministically under the new metadataKey.
    const expectedTags = meta.tags!.map((t) => encryptTagForSearch(t, newMetadataKey, vaultId));
    expect((newEncryptedTags as Uint8Array[]).map((b) => Array.from(b))).toEqual(
      expectedTags.map((b) => Array.from(b)),
    );
  });

  it('skips non-MEDIA items even when present in the list', async () => {
    const noteItem: ItemData = {
      itemId: 'note-1',
      vaultId,
      itemType: 'NOTE',
      encryptedMetadata: new Uint8Array([1, 2, 3]),
      createdAt: new Date(0),
      updatedAt: new Date(0),
      version: 1,
    };
    const { item: mediaItem } = await makeMediaItem({ dekVersion: 1, kek: oldKek, metadataKey: oldMetadataKey });
    itemsApi.updateItemRotation.mockResolvedValue(undefined);

    await rotateItems({
      vaultId,
      items: [noteItem, mediaItem],
      targetDekVersion: 2,
      oldKek,
      newKek,
      oldMetadataKey,
      newMetadataKey,
    });

    expect(itemsApi.updateItemRotation).toHaveBeenCalledTimes(1);
    expect(itemsApi.updateItemRotation.mock.calls[0][0]).toBe(mediaItem.itemId);
  });

  // Required per plan self-review: rotateItems must be safe to re-run after a
  // partial failure/interruption, i.e. it must not re-process items already at
  // targetDekVersion.
  it('skips items already at targetDekVersion (resume after partial failure)', async () => {
    const target = 3;
    const alreadyRotated = (itemId: string): ItemData => ({
      itemId,
      vaultId,
      itemType: 'MEDIA',
      // Deliberately bogus ciphertext — must never be touched, since these items
      // are filtered out before any decrypt/re-wrap happens.
      encryptedMetadata: new Uint8Array([9, 9, 9]),
      wrappedDek: new Uint8Array(97),
      dekVersion: target,
      createdAt: new Date(0),
      updatedAt: new Date(0),
      version: 5,
    });
    const { item: pending } = await makeMediaItem({
      dekVersion: target - 1,
      kek: oldKek,
      metadataKey: oldMetadataKey,
      itemId: 'pending-1',
    });
    itemsApi.updateItemRotation.mockResolvedValue(undefined);

    await rotateItems({
      vaultId,
      items: [alreadyRotated('already-1'), alreadyRotated('already-2'), pending],
      targetDekVersion: target,
      oldKek,
      newKek,
      oldMetadataKey,
      newMetadataKey,
    });

    expect(itemsApi.updateItemRotation).toHaveBeenCalledTimes(1);
    expect(itemsApi.updateItemRotation.mock.calls[0][0]).toBe('pending-1');
  });

  it('calls onProgress once per pending item, in order, with the pending-item total', async () => {
    const { item: p1 } = await makeMediaItem({ dekVersion: 1, kek: oldKek, metadataKey: oldMetadataKey, itemId: 'p1' });
    const { item: p2 } = await makeMediaItem({ dekVersion: 1, kek: oldKek, metadataKey: oldMetadataKey, itemId: 'p2' });
    itemsApi.updateItemRotation.mockResolvedValue(undefined);
    const onProgress = vi.fn();

    await rotateItems({
      vaultId,
      items: [p1, p2],
      targetDekVersion: 2,
      oldKek,
      newKek,
      oldMetadataKey,
      newMetadataKey,
      onProgress,
    });

    expect(onProgress).toHaveBeenNthCalledWith(1, 1, 2);
    expect(onProgress).toHaveBeenNthCalledWith(2, 2, 2);
  });

  it('retries a transient failure and succeeds without throwing', async () => {
    const { item } = await makeMediaItem({ dekVersion: 1, kek: oldKek, metadataKey: oldMetadataKey, itemId: 'flaky-1' });
    itemsApi.updateItemRotation.mockRejectedValueOnce(new Error('transient')).mockResolvedValueOnce(undefined);

    await expect(
      rotateItems({
        vaultId,
        items: [item],
        targetDekVersion: 2,
        oldKek,
        newKek,
        oldMetadataKey,
        newMetadataKey,
      }),
    ).resolves.toBeUndefined();

    expect(itemsApi.updateItemRotation).toHaveBeenCalledTimes(2);
  });

  it('throws after exhausting all retries, so the caller can pause the sweep', async () => {
    const { item } = await makeMediaItem({ dekVersion: 1, kek: oldKek, metadataKey: oldMetadataKey, itemId: 'always-fails' });
    itemsApi.updateItemRotation.mockRejectedValue(new Error('network down'));

    await expect(
      rotateItems({
        vaultId,
        items: [item],
        targetDekVersion: 2,
        oldKek,
        newKek,
        oldMetadataKey,
        newMetadataKey,
      }),
    ).rejects.toThrow('network down');

    // ITEM_RETRIES = 3 → 4 total attempts (initial + 3 retries).
    expect(itemsApi.updateItemRotation).toHaveBeenCalledTimes(4);
  }, 10000);
});

describe('rotateCollections', () => {
  it('re-encrypts every collection name under the new metadataKey', async () => {
    const name1 = 'Vacation Photos';
    const name2 = 'Work Docs';
    const encMeta1 = await encryptCollectionName(name1, oldMetadataKey);
    const encMeta2 = await encryptCollectionName(name2, oldMetadataKey);
    const cols: CollectionData[] = [
      { collectionId: 'c1', vaultId, encryptedMetadata: encMeta1, itemCount: 3, createdAt: new Date(0), updatedAt: new Date(0) },
      { collectionId: 'c2', vaultId, encryptedMetadata: encMeta2, itemCount: 0, createdAt: new Date(0), updatedAt: new Date(0) },
    ];
    collectionsApi.updateCollection.mockResolvedValue(undefined);

    await rotateCollections(cols, oldMetadataKey, newMetadataKey, vaultId);

    expect(collectionsApi.updateCollection).toHaveBeenCalledTimes(2);

    const [id1, vault1, newMeta1] = collectionsApi.updateCollection.mock.calls[0];
    expect(id1).toBe('c1');
    expect(vault1).toBe(vaultId);
    expect(decryptCollectionName(newMeta1, newMetadataKey)).toBe(name1);

    const [id2, , newMeta2] = collectionsApi.updateCollection.mock.calls[1];
    expect(id2).toBe('c2');
    expect(decryptCollectionName(newMeta2, newMetadataKey)).toBe(name2);
  });

  it('skips collections without encryptedMetadata', async () => {
    const cols: CollectionData[] = [
      { collectionId: 'c1', vaultId, encryptedMetadata: undefined, itemCount: 0, createdAt: new Date(0), updatedAt: new Date(0) },
    ];

    await rotateCollections(cols, oldMetadataKey, newMetadataKey, vaultId);

    expect(collectionsApi.updateCollection).not.toHaveBeenCalled();
  });
});
