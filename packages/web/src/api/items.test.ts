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
  InitiateItemUploadCommand: class {
    constructor(public input: unknown) { commands.push(['InitiateItemUpload', input]); }
  },
  CompleteItemUploadCommand: class {
    constructor(public input: unknown) { commands.push(['CompleteItemUpload', input]); }
  },
  ListItemsCommand: class {
    constructor(public input: unknown) { commands.push(['ListItems', input]); }
  },
  GetItemDownloadUrlCommand: class {
    constructor(public input: unknown) { commands.push(['GetItemDownloadUrl', input]); }
  },
  DeleteItemCommand: class {
    constructor(public input: unknown) { commands.push(['DeleteItem', input]); }
  },
}));
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(async () => ({ tokens: { idToken: { toString: () => 'JWT' } } })),
}));
vi.mock('../config', () => ({ getConfig: () => ({ apiBaseUrl: 'https://api' }) }));

import { initiateUpload, putToS3, completeUpload, listItems, getDownloadUrl, deleteItem } from './items';

beforeEach(() => {
  sendMock.mockReset();
  commands.length = 0;
  vi.unstubAllGlobals();
});

describe('items api', () => {
  it('initiateUpload sends the command and returns itemId+uploadUrl', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', uploadUrl: 'https://s3/put', expiresAt: new Date(0) });
    const meta = new Uint8Array([1, 2, 3]);
    const out = await initiateUpload({ vaultId: 'v1', encryptedMetadata: meta, sizeBytes: 200 });
    expect(out).toEqual({ itemId: 'i1', uploadUrl: 'https://s3/put' });
    expect(commands).toContainEqual(['InitiateItemUpload', { vaultId: 'v1', encryptedMetadata: meta, sizeBytes: 200 }]);
  });

  it('putToS3 PUTs raw bytes with NO Authorization header', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const blob = new Uint8Array([1, 2, 3]);
    await putToS3('https://s3/put', blob);
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

  it('completeUpload sends the command with the itemId', async () => {
    sendMock.mockResolvedValueOnce({ itemId: 'i1', completedAt: new Date(0) });
    await completeUpload('i1');
    expect(commands).toContainEqual(['CompleteItemUpload', { itemId: 'i1' }]);
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

  it('getDownloadUrl returns the url', async () => {
    sendMock.mockResolvedValueOnce({ downloadUrl: 'https://s3/get', expiresAt: new Date(0) });
    expect(await getDownloadUrl('i1')).toBe('https://s3/get');
    expect(commands).toContainEqual(['GetItemDownloadUrl', { itemId: 'i1' }]);
  });

  it('deleteItem sends the command with the itemId', async () => {
    sendMock.mockResolvedValueOnce({ message: 'ok', deletedAt: new Date(0) });
    await deleteItem('i1');
    expect(commands).toContainEqual(['DeleteItem', { itemId: 'i1' }]);
  });
});
