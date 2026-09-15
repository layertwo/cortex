import {
  CreateCollectionCommand,
  ListCollectionsCommand,
  GetCollectionCommand,
  UpdateCollectionCommand,
  DeleteCollectionCommand,
  AddItemToCollectionCommand,
  RemoveItemFromCollectionCommand,
} from '@cortex/client';
import type { CollectionData, ItemData } from '@cortex/client';
import { makeClient } from './client';

export async function createCollection(
  vaultId: string,
  encryptedMetadata: Uint8Array,
  metadataVersion: number,
): Promise<string> {
  const out = await makeClient().send(new CreateCollectionCommand({ vaultId, encryptedMetadata, metadataVersion }));
  if (!out.collectionId) throw new Error('createCollection: incomplete response');
  return out.collectionId;
}

export async function listCollections(
  vaultId: string,
  pageSize?: number,
  nextToken?: string,
): Promise<{ collections: CollectionData[]; nextToken?: string }> {
  const out = await makeClient().send(new ListCollectionsCommand({ vaultId, pageSize, nextToken }));
  return { collections: out.collections ?? [], nextToken: out.nextToken };
}

export async function listAllCollections(vaultId: string): Promise<CollectionData[]> {
  const all: CollectionData[] = [];
  let nextToken: string | undefined;
  do {
    const page = await listCollections(vaultId, undefined, nextToken);
    all.push(...page.collections);
    nextToken = page.nextToken;
  } while (nextToken);
  return all;
}

export async function getCollection(collectionId: string, vaultId: string): Promise<ItemData[]> {
  const out = await makeClient().send(new GetCollectionCommand({ collectionId, vaultId }));
  return out.items ?? [];
}

// A 409 (another device re-keyed or renamed this collection first) surfaces as
// the server message: "Collection was modified on another device; reload and retry".
export async function updateCollection(
  collectionId: string,
  vaultId: string,
  encryptedMetadata: Uint8Array,
  metadataVersion: number,
  expectedMetadataVersion: number,
): Promise<void> {
  await makeClient().send(
    new UpdateCollectionCommand({ collectionId, vaultId, encryptedMetadata, metadataVersion, expectedMetadataVersion }),
  );
}

export async function deleteCollection(collectionId: string, vaultId: string): Promise<void> {
  await makeClient().send(new DeleteCollectionCommand({ collectionId, vaultId }));
}

export async function addItemToCollection(collectionId: string, vaultId: string, itemId: string): Promise<void> {
  await makeClient().send(new AddItemToCollectionCommand({ collectionId, vaultId, itemId }));
}

export async function removeItemFromCollection(
  collectionId: string,
  vaultId: string,
  itemId: string,
): Promise<void> {
  await makeClient().send(new RemoveItemFromCollectionCommand({ collectionId, vaultId, itemId }));
}
