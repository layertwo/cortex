import { describe, it, expect, vi, beforeEach } from 'vitest';

// The generated SDK owns HTTP + auth + serde; our client.ts only constructs the
// client (endpoint + Cognito bearer token) and maps command I/O. So we mock the
// SDK and assert that wiring rather than re-testing smithy's transport.
const { sendMock, configs, commands } = vi.hoisted(() => ({
  sendMock: vi.fn(),
  configs: [] as Array<{ endpoint: string; token: () => Promise<{ token: string }> }>,
  commands: [] as Array<[string, unknown]>,
}));

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
      constructor(config: { endpoint: string; token: () => Promise<{ token: string }> }) {
        configs.push(config);
      }
    },
    CreateVaultCommand: cmd('CreateVault'),
    GetVaultSaltCommand: cmd('GetVaultSalt'),
    GetVaultCommand: cmd('GetVault'),
    UpdateVaultPasswordCommand: cmd('UpdateVaultPassword'),
    UpdateVaultRotationCommand: cmd('UpdateVaultRotation'),
    ListVaultsCommand: cmd('ListVaults'),
    UpdateVaultCommand: cmd('UpdateVault'),
    DeleteVaultCommand: cmd('DeleteVault'),
  };
});
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

import {
  createVault,
  getVaultSalt,
  getVault,
  updateVaultPassword,
  updateVaultRotation,
  listVaults,
  listAllVaults,
  updateVault,
  deleteVault,
} from './client';

const SALT = new Uint8Array(16).fill(1);
const summary = (vaultId: string) => ({
  vaultId,
  vaultSalt: SALT,
  createdAt: new Date(0),
  updatedAt: new Date(0),
  currentVmkVersion: 1,
  rotationState: 'IDLE' as const,
});

beforeEach(() => {
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

describe('getVault', () => {
  it('defaults absent fields and maps the VMK envelopes', async () => {
    sendMock.mockResolvedValueOnce({ vaultId: 'v1', vaultSalt: SALT, createdAt: new Date(0), updatedAt: new Date(0) });

    expect(await getVault('v1')).toEqual({
      vaultId: 'v1',
      vaultSalt: SALT,
      encryptedName: null,
      currentVmkVersion: 0,
      envelopeVersion: 0,
      vmkEnvelopes: [],
      rotationState: 'IDLE',
      rotationLockedAt: null,
    });
    expect(commands).toContainEqual(['GetVault', { vaultId: 'v1' }]);
  });

  it('maps the name, current version and envelopes', async () => {
    const name = new Uint8Array([1]);
    const wrappedVmk = new Uint8Array([2]);
    sendMock.mockResolvedValueOnce({
      vaultId: 'v1',
      vaultSalt: SALT,
      createdAt: new Date(0),
      updatedAt: new Date(0),
      encryptedName: name,
      currentVmkVersion: 2,
      envelopeVersion: 5,
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
      vmkEnvelopes: [{ vmkVersion: 2, wrappedVmk, createdAt: new Date(1000) }],
    });

    expect(await getVault('v1')).toEqual({
      vaultId: 'v1',
      vaultSalt: SALT,
      encryptedName: name,
      currentVmkVersion: 2,
      envelopeVersion: 5,
      vmkEnvelopes: [{ vmkVersion: 2, wrappedVmk, createdAt: new Date(1000) }],
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
    });
  });
});

describe('updateVaultPassword', () => {
  it('sends the expected version and envelopes and returns the new envelope version', async () => {
    const wrappedVmk = new Uint8Array([9]);
    const createdAt = new Date(1000);
    sendMock.mockResolvedValueOnce({ envelopeVersion: 3 });

    const out = await updateVaultPassword('v1', 2, [{ vmkVersion: 1, wrappedVmk, createdAt }]);

    expect(out).toEqual({ envelopeVersion: 3 });
    expect(commands).toContainEqual([
      'UpdateVaultPassword',
      { vaultId: 'v1', expectedEnvelopeVersion: 2, vmkEnvelopes: [{ vmkVersion: 1, wrappedVmk, createdAt }] },
    ]);
  });

  it('throws when the response omits envelopeVersion', async () => {
    sendMock.mockResolvedValueOnce({});
    await expect(updateVaultPassword('v1', 0, [])).rejects.toThrow('updateVaultPassword: incomplete response');
  });
});

describe('updateVaultRotation', () => {
  it('passes ACQUIRE inputs and maps the version fields', async () => {
    const wrappedNewVmk = new Uint8Array([8]);
    sendMock.mockResolvedValueOnce({ rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, currentVmkVersion: 2, envelopeVersion: 6 });

    const acquired = await updateVaultRotation({
      vaultId: 'v1',
      action: 'ACQUIRE',
      expectedState: 'IDLE',
      expectedEnvelopeVersion: 5,
      newVmkVersion: 2,
      wrappedNewVmk,
    });

    expect(acquired).toEqual({ rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, currentVmkVersion: 2, envelopeVersion: 6 });
    expect(commands).toContainEqual([
      'UpdateVaultRotation',
      { vaultId: 'v1', action: 'ACQUIRE', expectedState: 'IDLE', expectedEnvelopeVersion: 5, newVmkVersion: 2, wrappedNewVmk },
    ]);
  });

  it('passes RELEASE with the re-encrypted name', async () => {
    const newName = new Uint8Array([3]);
    sendMock.mockResolvedValueOnce({ rotationState: 'IDLE', currentVmkVersion: 2, envelopeVersion: 6 });

    const released = await updateVaultRotation({ vaultId: 'v1', action: 'RELEASE', expectedState: 'IN_PROGRESS', newEncryptedName: newName });

    expect(released).toEqual({ rotationState: 'IDLE', rotationLockedAt: null, currentVmkVersion: 2, envelopeVersion: 6 });
    expect(commands).toContainEqual([
      'UpdateVaultRotation',
      { vaultId: 'v1', action: 'RELEASE', expectedState: 'IN_PROGRESS', newEncryptedName: newName },
    ]);
  });
});

describe('listVaults', () => {
  it('sends the page size (default 50) and token and returns the page', async () => {
    const vaults = [summary('v1')];
    sendMock.mockResolvedValueOnce({ vaults, nextToken: 'T2' });

    expect(await listVaults()).toEqual({ vaults, nextToken: 'T2' });
    expect(commands).toContainEqual(['ListVaults', { pageSize: 50, nextToken: undefined }]);

    sendMock.mockResolvedValueOnce({});
    expect(await listVaults(10, 'T2')).toEqual({ vaults: [], nextToken: undefined });
    expect(commands).toContainEqual(['ListVaults', { pageSize: 10, nextToken: 'T2' }]);
  });

  it('listAllVaults pages until nextToken is absent, including an empty page with a token', async () => {
    sendMock.mockResolvedValueOnce({ vaults: [summary('v1')], nextToken: 'T2' });
    sendMock.mockResolvedValueOnce({ vaults: [], nextToken: 'T3' });
    sendMock.mockResolvedValueOnce({ vaults: [summary('v2'), summary('v3')] });

    const all = await listAllVaults();

    expect(all.map((v) => v.vaultId)).toEqual(['v1', 'v2', 'v3']);
    expect(commands.filter(([name]) => name === 'ListVaults').map(([, input]) => input)).toEqual([
      { pageSize: 50, nextToken: undefined },
      { pageSize: 50, nextToken: 'T2' },
      { pageSize: 50, nextToken: 'T3' },
    ]);
  });
});

describe('updateVault', () => {
  it('sends the encrypted name', async () => {
    sendMock.mockResolvedValue({ vaultId: 'v1', updatedAt: new Date(0) });
    const encryptedName = new Uint8Array([1]);

    await updateVault('v1', { encryptedName });

    expect(commands).toContainEqual(['UpdateVault', { vaultId: 'v1', encryptedName }]);
  });

  it('rejects without sending when the name is absent', async () => {
    await expect(updateVault('v1', {})).rejects.toThrow('updateVault: nothing to update');
    expect(sendMock).not.toHaveBeenCalled();
  });
});

describe('deleteVault', () => {
  it('sends the vaultId and returns the progress report', async () => {
    sendMock.mockResolvedValueOnce({ deletionState: 'DELETING', deletedItems: 25, deletedCollections: 0, deletedShares: 0 });

    expect(await deleteVault('v1')).toEqual({
      deletionState: 'DELETING',
      deletedItems: 25,
      deletedCollections: 0,
      deletedShares: 0,
    });
    expect(commands).toContainEqual(['DeleteVault', { vaultId: 'v1' }]);
  });

  it('defaults the counters to 0 and throws when deletionState is missing', async () => {
    sendMock.mockResolvedValueOnce({ deletionState: 'DELETED' });
    expect(await deleteVault('v1')).toEqual({ deletionState: 'DELETED', deletedItems: 0, deletedCollections: 0, deletedShares: 0 });

    sendMock.mockResolvedValueOnce({});
    await expect(deleteVault('v1')).rejects.toThrow('deleteVault: incomplete response');
  });
});
