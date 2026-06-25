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

export async function createCollection(vaultId: string, encryptedMetadata: Uint8Array): Promise<string> {
  const out = await makeClient().send(new CreateCollectionCommand({ vaultId, encryptedMetadata }));
  if (!out.collectionId) throw new Error('createCollection: incomplete response');
  return out.collectionId;
}

export async function listCollections(vaultId: string): Promise<CollectionData[]> {
  const out = await makeClient().send(new ListCollectionsCommand({ vaultId }));
  return out.collections ?? [];
}

export async function getCollection(collectionId: string): Promise<ItemData[]> {
  const out = await makeClient().send(new GetCollectionCommand({ collectionId }));
  return out.items ?? [];
}

export async function updateCollection(
  collectionId: string,
  vaultId: string,
  encryptedMetadata: Uint8Array,
): Promise<void> {
  await makeClient().send(new UpdateCollectionCommand({ collectionId, vaultId, encryptedMetadata }));
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
