import { describe, it, expect, vi, beforeEach } from 'vitest';

// Same convention as client.test.ts: the generated SDK owns HTTP/auth/serde, so we
// mock @cortex/client and assert which command was sent with which input. Only
// putToS3 hits the network directly (presigned URL is not a Smithy op).
const { sendMock, commands } = vi.hoisted(() => ({
  sendMock: vi.fn(),
  commands: [] as Array<[string, unknown]>,
}));

vi.mock('@cortex/client', () => ({
  CortexClient: class {
    send = sendMock;
    constructor(public config: unknown) {}
  },
  CreateItemUploadCommand: class {
    constructor(public input: unknown) { commands.push(['CreateItemUpload', input]); }
  },
  FinalizeItemUploadCommand: class {
    constructor(public input: unknown) { commands.push(['FinalizeItemUpload', input]); }
  },
  ListItemsCommand: class {
    constructor(public input: unknown) { commands.push(['ListItems', input]); }
  },
  GetItemContentUrlCommand: class {
    constructor(public input: unknown) { commands.push(['GetItemContentUrl', input]); }
  },
  DeleteItemCommand: class {
    constructor(public input: unknown) { commands.push(['DeleteItem', input]); }
  },
  CreateUploadPartUrlsCommand: class {
    constructor(public input: unknown) { commands.push(['CreateUploadPartUrls', input]); }
  },
  DeleteItemUploadCommand: class {
    constructor(public input: unknown) { commands.push(['DeleteItemUpload', input]); }
  },
  SearchByTagCommand: class {
    constructor(public input: unknown) { commands.push(['SearchByTag', input]); }
  },
  UpdateItemCommand: class {
    constructor(public input: unknown) { commands.push(['UpdateItem', input]); }
  },
}));
vi.mock('../config', () => ({ getConfig: () => ({ apiBaseUrl: 'https://api' }) }));

import {
  createItemUpload,
  putToS3,
  finalizeUpload,
  createUploadPartUrls,
  deleteUpload,
  searchByTag,
  listItems,
  getContentUrl,
  deleteItem,
  updateItemTags,
} from './items';

beforeEach(() => {
  commands.length = 0;
});

describe('items api', () => {
  it('createItemUpload sends the command and returns itemId+uploadUrl', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', uploadUrl: 'https://s3/put', expiresAt: new Date(0) });
    const meta = new Uint8Array([1, 2, 3]);
    const wrappedDek = new Uint8Array(97);
    const out = await createItemUpload({ vaultId: 'v1', encryptedMetadata: meta, sizeBytes: 200, wrappedDek, dekVersion: 1 });
    expect(out).toEqual({ itemId: 'i1', uploadUrl: 'https://s3/put' });
    expect(commands).toContainEqual(['CreateItemUpload', { vaultId: 'v1', encryptedMetadata: meta, sizeBytes: 200, wrappedDek, dekVersion: 1 }]);
  });

  it('putToS3 PUTs raw bytes with NO Authorization header and returns the ETag', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 200, headers: { ETag: '"abc"' } }));
    vi.stubGlobal('fetch', fetchMock);
    const blob = new Uint8Array([1, 2, 3]);
    const eTag = await putToS3('https://s3/put', blob);
    expect(eTag).toBe('"abc"');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://s3/put');
    expect(init.method).toBe('PUT');
    expect(init.body).toBe(blob);
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('putToS3 throws on a non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 403 })));
    await expect(putToS3('https://s3/put', new Uint8Array([1]))).rejects.toThrow('403');
  });

  it('putToS3 throws when the ETag header is missing (CORS not exposing it)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 200 })));
    await expect(putToS3('https://s3/put', new Uint8Array([1]))).rejects.toThrow(/ETag/);
  });

  it('createItemUpload surfaces uploadId when the server sends one (multipart)', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', uploadUrl: 'https://s3/put', uploadId: 'mp1' });
    const out = await createItemUpload({ vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), sizeBytes: 999, wrappedDek: new Uint8Array(97), dekVersion: 1 });
    expect(out).toEqual({ itemId: 'i1', uploadUrl: 'https://s3/put', uploadId: 'mp1' });
  });

  it('createUploadPartUrls maps the response to {partNumber, url}', async () => {
    sendMock.mockResolvedValueOnce({
      urls: [
        { partNumber: 1, url: 'https://s3/p1', expiresAt: new Date(0) },
        { partNumber: 2, url: 'https://s3/p2', expiresAt: new Date(0) },
      ],
    });
    const urls = await createUploadPartUrls('i1', 'mp1', [1, 2]);
    expect(urls).toEqual([{ partNumber: 1, url: 'https://s3/p1' }, { partNumber: 2, url: 'https://s3/p2' }]);
    expect(commands).toContainEqual(['CreateUploadPartUrls', { itemId: 'i1', uploadId: 'mp1', partNumbers: [1, 2] }]);
  });

  it('finalizeUpload sends only the itemId for single-PUT', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', completedAt: new Date(0) });
    await finalizeUpload('i1');
    expect(commands).toContainEqual(['FinalizeItemUpload', { itemId: 'i1' }]);
  });

  it('finalizeUpload passes uploadId + parts for multipart', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', completedAt: new Date(0) });
    await finalizeUpload('i1', { uploadId: 'mp1', parts: [{ partNumber: 1, eTag: '"e1"' }] });
    expect(commands).toContainEqual([
      'FinalizeItemUpload',
      { itemId: 'i1', uploadId: 'mp1', parts: [{ partNumber: 1, eTag: '"e1"' }] },
    ]);
  });

  it('deleteUpload sends only the itemId', async () => {
    sendMock.mockResolvedValueOnce({ message: 'Upload deleted' });
    await deleteUpload('i1');
    expect(commands).toContainEqual(['DeleteItemUpload', { itemId: 'i1' }]);
  });

  it('listItems sends vaultId and returns items', async () => {
    const items = [{ itemId: 'i1', encryptedMetadata: new Uint8Array([9]), createdAt: new Date(0) }];
    sendMock.mockResolvedValueOnce({ items, totalCount: 1 });
    const out = await listItems('v1');
    expect(out).toBe(items);
    expect(commands).toContainEqual(['ListItems', { vaultId: 'v1' }]);
  });

  it('listItems returns [] when items is absent', async () => {
    sendMock.mockResolvedValueOnce({ totalCount: 0 });
    expect(await listItems('v1')).toEqual([]);
  });

  it('getContentUrl returns the url', async () => {
    sendMock.mockResolvedValueOnce({ contentUrl: 'https://s3/get', expiresAt: new Date(0) });
    expect(await getContentUrl('i1')).toBe('https://s3/get');
    expect(commands).toContainEqual(['GetItemContentUrl', { itemId: 'i1' }]);
  });

  it('searchByTag returns items (or [])', async () => {
    const items = [{ itemId: 'i1', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), createdAt: new Date(0) }];
    sendMock.mockResolvedValueOnce({ items, totalCount: 1 });
    expect(await searchByTag('v1', 'YWJj')).toBe(items);
    expect(commands).toContainEqual(['SearchByTag', { vaultId: 'v1', encryptedTag: 'YWJj' }]);
  });

  it('deleteItem sends the command with the itemId', async () => {
    sendMock.mockResolvedValueOnce({ message: 'ok', deletedAt: new Date(0) });
    await deleteItem('i1');
    expect(commands).toContainEqual(['DeleteItem', { itemId: 'i1' }]);
  });

  it('updateItemTags sends UpdateItem with itemId, metadata and tags', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', updatedAt: new Date(0), version: 2 });
    const meta = new Uint8Array([1, 2]);
    const tags = [new Uint8Array([3]), new Uint8Array([4])];
    await updateItemTags('i1', meta, tags);
    expect(commands).toContainEqual([
      'UpdateItem',
      { itemId: 'i1', encryptedMetadata: meta, encryptedTags: tags },
    ]);
  });
});
