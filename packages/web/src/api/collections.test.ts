import { describe, it, expect, vi, beforeEach } from 'vitest';

const { sendMock, commands } = vi.hoisted(() => ({ sendMock: vi.fn(), commands: [] as Array<[string, unknown]> }));

vi.mock('@cortex/client', () => {
  const cmd = (name: string) =>
    class {
      constructor(public input: unknown) {
        commands.push([name, input]);
      }
    };
  return {
    CortexClient: class {
      send = sendMock;
      constructor(public config: unknown) {}
    },
    CreateCollectionCommand: cmd('CreateCollection'),
    ListCollectionsCommand: cmd('ListCollections'),
    GetCollectionCommand: cmd('GetCollection'),
    UpdateCollectionCommand: cmd('UpdateCollection'),
    DeleteCollectionCommand: cmd('DeleteCollection'),
    AddItemToCollectionCommand: cmd('AddItemToCollection'),
    RemoveItemFromCollectionCommand: cmd('RemoveItemFromCollection'),
  };
});
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(async () => ({ tokens: { idToken: { toString: () => 'JWT' } } })),
}));
vi.mock('../config', () => ({ getConfig: () => ({ apiBaseUrl: 'https://api' }) }));

import {
  createCollection,
  listCollections,
  getCollection,
  updateCollection,
  deleteCollection,
  addItemToCollection,
  removeItemFromCollection,
} from './collections';

beforeEach(() => {
  sendMock.mockReset();
  commands.length = 0;
});

describe('collections api', () => {
  it('createCollection returns the new id', async () => {
    sendMock.mockResolvedValueOnce({ collectionId: 'c1', createdAt: new Date(0) });
    const meta = new Uint8Array([1, 2]);
    expect(await createCollection('v1', meta)).toBe('c1');
    expect(commands).toContainEqual(['CreateCollection', { vaultId: 'v1', encryptedMetadata: meta }]);
  });

  it('listCollections returns the array (or [])', async () => {
    const cols = [
      { collectionId: 'c1', vaultId: 'v1', encryptedMetadata: new Uint8Array([9]), itemCount: 2, createdAt: new Date(0), updatedAt: new Date(0) },
    ];
    sendMock.mockResolvedValueOnce({ collections: cols });
    expect(await listCollections('v1')).toBe(cols);
    sendMock.mockResolvedValueOnce({});
    expect(await listCollections('v1')).toEqual([]);
  });

  it('getCollection returns its items (or [])', async () => {
    const items = [{ itemId: 'i1', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), createdAt: new Date(0) }];
    sendMock.mockResolvedValueOnce({ collectionId: 'c1', items });
    expect(await getCollection('c1', 'v1')).toBe(items);
    expect(commands).toContainEqual(['GetCollection', { collectionId: 'c1', vaultId: 'v1' }]);
  });

  it('add/remove/update/delete send the right inputs', async () => {
    sendMock.mockResolvedValue({});
    await addItemToCollection('c1', 'v1', 'i1');
    await removeItemFromCollection('c1', 'v1', 'i1');
    await updateCollection('c1', 'v1', new Uint8Array([7]));
    await deleteCollection('c1', 'v1');
    expect(commands).toContainEqual(['AddItemToCollection', { collectionId: 'c1', vaultId: 'v1', itemId: 'i1' }]);
    expect(commands).toContainEqual(['RemoveItemFromCollection', { collectionId: 'c1', vaultId: 'v1', itemId: 'i1' }]);
    expect(commands).toContainEqual(['UpdateCollection', { collectionId: 'c1', vaultId: 'v1', encryptedMetadata: new Uint8Array([7]) }]);
    expect(commands).toContainEqual(['DeleteCollection', { collectionId: 'c1', vaultId: 'v1' }]);
  });
});
