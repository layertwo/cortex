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
  listAllCollections,
  getCollection,
  updateCollection,
  deleteCollection,
  addItemToCollection,
  removeItemFromCollection,
} from './collections';

const col = (collectionId: string) => ({
  collectionId,
  vaultId: 'v1',
  encryptedMetadata: new Uint8Array([9]),
  itemCount: 2,
  createdAt: new Date(0),
  updatedAt: new Date(0),
});

beforeEach(() => {
  commands.length = 0;
});

describe('collections api', () => {
  it('createCollection sends the metadata version and returns the new id', async () => {
    sendMock.mockResolvedValueOnce({ collectionId: 'c1', createdAt: new Date(0) });
    const meta = new Uint8Array([1, 2]);
    expect(await createCollection('v1', meta, 3)).toBe('c1');
    expect(commands).toContainEqual(['CreateCollection', { vaultId: 'v1', encryptedMetadata: meta, metadataVersion: 3 }]);
  });

  it('listCollections returns one page with its token (collections default to [])', async () => {
    const cols = [col('c1')];
    sendMock.mockResolvedValueOnce({ collections: cols, nextToken: 'T2' });
    expect(await listCollections('v1')).toEqual({ collections: cols, nextToken: 'T2' });
    expect(commands).toContainEqual(['ListCollections', { vaultId: 'v1', pageSize: undefined, nextToken: undefined }]);

    sendMock.mockResolvedValueOnce({});
    expect(await listCollections('v1', 20, 'T2')).toEqual({ collections: [], nextToken: undefined });
    expect(commands).toContainEqual(['ListCollections', { vaultId: 'v1', pageSize: 20, nextToken: 'T2' }]);
  });

  it('listAllCollections pages until nextToken is absent', async () => {
    sendMock.mockResolvedValueOnce({ collections: [col('c1')], nextToken: 'T2' });
    sendMock.mockResolvedValueOnce({ collections: [], nextToken: 'T3' });
    sendMock.mockResolvedValueOnce({ collections: [col('c2'), col('c3')] });

    const all = await listAllCollections('v1');

    expect(all.map((c) => c.collectionId)).toEqual(['c1', 'c2', 'c3']);
    expect(commands.filter(([name]) => name === 'ListCollections').map(([, input]) => input)).toEqual([
      { vaultId: 'v1', pageSize: undefined, nextToken: undefined },
      { vaultId: 'v1', pageSize: undefined, nextToken: 'T2' },
      { vaultId: 'v1', pageSize: undefined, nextToken: 'T3' },
    ]);
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
    await updateCollection('c1', 'v1', new Uint8Array([7]), 2, 1);
    await deleteCollection('c1', 'v1');
    expect(commands).toContainEqual(['AddItemToCollection', { collectionId: 'c1', vaultId: 'v1', itemId: 'i1' }]);
    expect(commands).toContainEqual(['RemoveItemFromCollection', { collectionId: 'c1', vaultId: 'v1', itemId: 'i1' }]);
    expect(commands).toContainEqual([
      'UpdateCollection',
      { collectionId: 'c1', vaultId: 'v1', encryptedMetadata: new Uint8Array([7]), metadataVersion: 2, expectedMetadataVersion: 1 },
    ]);
    expect(commands).toContainEqual(['DeleteCollection', { collectionId: 'c1', vaultId: 'v1' }]);
  });
});
