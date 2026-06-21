import { describe, it, expect, vi, beforeEach } from 'vitest';

// The generated SDK owns HTTP + auth + serde; our client.ts only constructs the
// client (endpoint + Cognito bearer token) and maps command I/O. So we mock the
// SDK and assert that wiring rather than re-testing smithy's transport.
const { sendMock, configs, commands } = vi.hoisted(() => ({
  sendMock: vi.fn(),
  configs: [] as Array<{ endpoint: string; token: () => Promise<{ token: string }> }>,
  commands: [] as Array<[string, unknown]>,
}));

vi.mock('@cortex/client', () => ({
  CortexClient: class {
    send = sendMock;
    constructor(config: { endpoint: string; token: () => Promise<{ token: string }> }) {
      configs.push(config);
    }
  },
  CreateVaultCommand: class {
    constructor(public input: unknown) {
      commands.push(['CreateVault', input]);
    }
  },
  GetVaultSaltCommand: class {
    constructor(public input: unknown) {
      commands.push(['GetVaultSalt', input]);
    }
  },
}));
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
  sendMock.mockReset();
  configs.length = 0;
  commands.length = 0;
});

describe('api client', () => {
  it('configures the client with the endpoint and a Cognito bearer token', async () => {
    sendMock.mockResolvedValueOnce({ vaultId: 'v1', vaultSalt: new Uint8Array(16) });

    await createVault();

    expect(configs[0].endpoint).toBe('https://api');
    expect(await configs[0].token()).toEqual({ token: 'JWT123' });
  });

  it('createVault returns vaultId and the raw (Uint8Array) salt', async () => {
    const salt = new Uint8Array(16).fill(7);
    sendMock.mockResolvedValueOnce({ vaultId: 'v1', vaultSalt: salt, createdAt: 1 });

    const result = await createVault();

    expect(result).toEqual({ vaultId: 'v1', vaultSalt: salt });
    expect(commands).toContainEqual(['CreateVault', {}]);
  });

  it('getVaultSalt passes the vaultId and returns the raw salt', async () => {
    const salt = new Uint8Array(16).fill(3);
    sendMock.mockResolvedValueOnce({ vaultSalt: salt });

    const result = await getVaultSalt('v9');

    expect(result).toEqual(salt);
    expect(commands).toContainEqual(['GetVaultSalt', { vaultId: 'v9' }]);
  });

  it('throws when the response is missing the salt', async () => {
    sendMock.mockResolvedValueOnce({});
    await expect(getVaultSalt('v9')).rejects.toThrow('missing salt');
  });
});
