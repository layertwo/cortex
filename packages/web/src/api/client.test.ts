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
  kekVersion: 1,
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
  it('maps the name, verifier and staged pair, defaulting absent fields to null', async () => {
    sendMock.mockResolvedValueOnce({ vaultId: 'v1', vaultSalt: SALT, createdAt: new Date(0), updatedAt: new Date(0) });

    expect(await getVault('v1')).toEqual({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
      encryptedName: null,
      verifier: null,
      pendingVaultSalt: null,
      pendingVerifier: null,
    });
    expect(commands).toContainEqual(['GetVault', { vaultId: 'v1' }]);

    const name = new Uint8Array([1]);
    const verifier = new Uint8Array([2]);
    const pendingSalt = new Uint8Array(16).fill(4);
    const pendingVerifier = new Uint8Array([5]);
    sendMock.mockResolvedValueOnce({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 3,
      rotationState: 'PAUSED',
      rotationLockedAt: 1700000000,
      encryptedName: name,
      verifier,
      pendingVaultSalt: pendingSalt,
      pendingVerifier,
    });

    expect(await getVault('v1')).toEqual({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 3,
      rotationState: 'PAUSED',
      rotationLockedAt: 1700000000,
      encryptedName: name,
      verifier,
      pendingVaultSalt: pendingSalt,
      pendingVerifier,
    });
  });
});

describe('updateVaultRotation', () => {
  it('passes the staged pair and name through and maps the pending fields', async () => {
    const newSalt = new Uint8Array(16).fill(8);
    const newVerifier = new Uint8Array([9]);
    sendMock.mockResolvedValueOnce({
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
      pendingVaultSalt: newSalt,
      pendingVerifier: newVerifier,
    });

    const acquired = await updateVaultRotation({
      vaultId: 'v1',
      action: 'ACQUIRE',
      expectedState: 'IDLE',
      newVaultSalt: newSalt,
      newVerifier,
    });

    expect(acquired).toEqual({
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
      pendingVaultSalt: newSalt,
      pendingVerifier: newVerifier,
    });
    expect(commands).toContainEqual([
      'UpdateVaultRotation',
      { vaultId: 'v1', action: 'ACQUIRE', expectedState: 'IDLE', newVaultSalt: newSalt, newVerifier },
    ]);

    const newName = new Uint8Array([3]);
    sendMock.mockResolvedValueOnce({ rotationState: 'IDLE' });

    const released = await updateVaultRotation({
      vaultId: 'v1',
      action: 'RELEASE',
      expectedState: 'IN_PROGRESS',
      kekVersion: 2,
      newEncryptedName: newName,
    });

    expect(released).toEqual({ rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null });
    expect(commands).toContainEqual([
      'UpdateVaultRotation',
      { vaultId: 'v1', action: 'RELEASE', expectedState: 'IN_PROGRESS', kekVersion: 2, newEncryptedName: newName },
    ]);
  });

  it('sends PAUSE and ABANDON with their expected states', async () => {
    sendMock.mockResolvedValueOnce({ rotationState: 'PAUSED', rotationLockedAt: 1 });
    sendMock.mockResolvedValueOnce({ rotationState: 'IDLE' });

    await updateVaultRotation({ vaultId: 'v1', action: 'PAUSE', expectedState: 'IN_PROGRESS' });
    const abandoned = await updateVaultRotation({ vaultId: 'v1', action: 'ABANDON', expectedState: 'PAUSED' });

    expect(commands).toContainEqual(['UpdateVaultRotation', { vaultId: 'v1', action: 'PAUSE', expectedState: 'IN_PROGRESS' }]);
    expect(commands).toContainEqual(['UpdateVaultRotation', { vaultId: 'v1', action: 'ABANDON', expectedState: 'PAUSED' }]);
    expect(abandoned.rotationState).toBe('IDLE');
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
  it('sends the encrypted name and/or verifier', async () => {
    sendMock.mockResolvedValue({ vaultId: 'v1', updatedAt: new Date(0) });
    const encryptedName = new Uint8Array([1]);
    const verifier = new Uint8Array([2]);

    await updateVault('v1', { encryptedName, verifier });
    await updateVault('v1', { verifier });

    expect(commands).toContainEqual(['UpdateVault', { vaultId: 'v1', encryptedName, verifier }]);
    expect(commands).toContainEqual(['UpdateVault', { vaultId: 'v1', encryptedName: undefined, verifier }]);
  });

  it('rejects without sending when both fields are absent', async () => {
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
