import { describe, it, expect, vi, beforeEach } from 'vitest';
import { bytesToBase64 } from '@cortex/encryption';

vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(async () => ({
    tokens: { idToken: { toString: () => 'JWT123' } },
  })),
}));
vi.mock('../config', () => ({
  getConfig: () => ({
    userPoolId: 'p',
    userPoolClientId: 'c',
    region: 'r',
    apiBaseUrl: 'https://api',
  }),
}));

import { createVault, getVaultSalt } from './client';

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('api client', () => {
  it('createVault POSTs with bearer token and decodes the salt', async () => {
    const salt = new Uint8Array(16).fill(7);
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ vaultId: 'v1', vaultSalt: bytesToBase64(salt), createdAt: 1 }),
          { status: 200 },
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await createVault();

    expect(result).toEqual({ vaultId: 'v1', vaultSalt: salt });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api/v1/vaults');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer JWT123');
  });

  it('getVaultSalt GETs and decodes the salt', async () => {
    const salt = new Uint8Array(16).fill(3);
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ vaultSalt: bytesToBase64(salt) }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await getVaultSalt('v9');

    expect(result).toEqual(salt);
    expect(fetchMock.mock.calls[0][0]).toBe('https://api/v1/vaults/v9/salt');
  });

  it('throws on non-2xx', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('nope', { status: 401 })));
    await expect(getVaultSalt('v9')).rejects.toThrow('401');
  });
});
