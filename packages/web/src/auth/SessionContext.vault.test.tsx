import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import { getCurrentUser } from 'aws-amplify/auth';
import {
  deriveKeys,
  generateVaultMasterKey,
  wrapVmk,
  unwrapVmk,
  wrapDek,
  storeKeys,
  retrieveKeys,
  bytesToBase64,
} from '@cortex/encryption';
import { ConflictError, type ItemData, type VaultSummary } from '@cortex/client';
import { encryptCollectionName, decryptCollectionName } from '../items/collectionMetadata';
import { encryptMetadata, type FileMetadata } from '../items/metadata';
import { listAllItems, listItems, updateItemRotation } from '../api/items';
import { listAllCollections } from '../api/collections';
import { getVaultKeys } from '../vault/keyAccess';

const SALT = new Uint8Array(16).fill(9);
const VMK = new Uint8Array(32).fill(7);
const VMK_NEW = new Uint8Array(32).fill(0x21);
// Password → wrapping key. A wrong password maps to a key no envelope was wrapped under.
const WRAP: Record<string, Uint8Array> = {
  vaultpw: new Uint8Array(32).fill(5),
  newvaultpw: new Uint8Array(32).fill(6),
  wrongpw: new Uint8Array(32).fill(0x99),
  recoverypw: new Uint8Array(32).fill(0x31),
  finalpw: new Uint8Array(32).fill(0x32),
};
const wrapKey = (pw: string) => (WRAP[pw] ?? new Uint8Array(32).fill(5)).slice();

// Hoisted so the vi.mock factories below can reference these without a TDZ error.
const { api } = vi.hoisted(() => ({
  api: {
    createVault: vi.fn(),
    getVault: vi.fn(),
    updateVaultPassword: vi.fn(),
    updateVaultRotation: vi.fn(),
    listAllVaults: vi.fn(async (): Promise<VaultSummary[]> => []),
    updateVault: vi.fn(),
    deleteVault: vi.fn(),
  },
}));

vi.mock('aws-amplify/auth', () => ({
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
  getCurrentUser: vi.fn(async () => ({ userId: 'u1' })), // already signed in
}));

vi.mock('../api/client', () => api);
vi.mock('../api/items', () => ({
  listAllItems: vi.fn(async () => []),
  listItems: vi.fn(async () => []),
  updateItemRotation: vi.fn(async () => {}),
}));
vi.mock('../api/collections', () => ({ listAllCollections: vi.fn(async () => []) }));

// Real crypto (wrapVmk/unwrapVmk/deriveKeys/encryption); mock only Argon2id (slow), the VMK
// generator (deterministic fixtures), recovery-phrase generation and key storage.
vi.mock('@cortex/encryption', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@cortex/encryption')>();
  return {
    ...actual,
    deriveWrappingKey: vi.fn(async (password: string) => wrapKey(password)),
    generateVaultMasterKey: vi.fn(async () => VMK.slice()),
    generateRecoveryKey: vi.fn(() => 'word '.repeat(24).trim()),
    storeKeys: vi.fn(async () => {}),
    clearKeys: vi.fn(async () => {}),
    retrieveKeys: vi.fn(async () => null),
  };
});

import {
  SessionProvider,
  useSession,
  WRONG_VAULT_PASSWORD,
  DELETE_REFUSED,
  VAULT_NEEDS_SETUP,
  ROTATION_INCOMPLETE,
  RECOVERY_BLOCKED_BY_ROTATION,
  type SessionValue,
} from './SessionContext';

const sessionRef: { current: SessionValue | null } = { current: null };

function Probe() {
  const s = useSession();
  sessionRef.current = s;
  return (
    <div>
      <span data-testid="status">{s.status}</span>
      <span data-testid="rotation-interrupted">{String(s.rotationInterrupted)}</span>
      <span data-testid="vaults">{s.vaults.map((v) => v.name).join(',')}</span>
      <span data-testid="active">{s.activeVault?.name ?? ''}</span>
      <span data-testid="version">{s.vaultVersion}</span>
      <button onClick={() => s.setupVault('vaultpw').then((r) => (document.title = r)).catch((e) => (document.title = e.message))}>
        setup
      </button>
      <button onClick={() => s.setupVault('vaultpw', 'Family').then((r) => (document.title = r)).catch((e) => (document.title = e.message))}>
        setup-family
      </button>
      <button onClick={() => s.unlockVault('vaultpw').catch((e) => (document.title = e.message))}>unlock</button>
      <button
        onClick={() =>
          s.changeVaultPassword('vaultpw', 'newvaultpw').then(() => (document.title = 'changed')).catch((e) => (document.title = e.message))
        }
      >
        change
      </button>
      <button
        onClick={() =>
          s.rotateEncryptionKeys('vaultpw').then((p) => (document.title = `rotated:${p.split(' ').length}`)).catch((e) => (document.title = e.message))
        }
      >
        rotate
      </button>
      <button onClick={() => s.switchVault('v9').then((r) => (document.title = r))}>switch-v9</button>
      <button onClick={() => s.renameVault('v1', 'Work').then(() => (document.title = 'renamed')).catch((e) => (document.title = e.message))}>
        rename-v1
      </button>
      <button onClick={() => s.logout()}>logout</button>
      <button onClick={() => s.signInAccount('a@b.com', 'pw')}>signin</button>
      <button
        onClick={() =>
          s.recoverVault(document.body.dataset.phrase ?? '', 'newpw')
            .then((r) => (document.title = `recovered:${r.vaultId}:${r.name}`))
            .catch((e) => (document.title = e.message))
        }
      >
        recover
      </button>
      <button
        onClick={() =>
          s.recoverVault(document.body.dataset.phrase ?? '', 'newpw', { vaultId: 'v1' })
            .then((r) => (document.title = `recovered:${r.vaultId}:${r.name}`))
            .catch((e) => (document.title = e.message))
        }
      >
        recover-kit
      </button>
      <button
        onClick={() =>
          s.deleteVault('v1', 'vaultpw', (n) => (document.body.dataset.deleted = String(n)))
            .then(() => (document.title = 'deleted'))
            .catch((e) => (document.title = e.message))
        }
      >
        delete-v1
      </button>
    </div>
  );
}

async function renderProbe() {
  render(
    <SessionProvider>
      <Probe />
    </SessionProvider>,
  );
  await waitFor(() => expect(screen.getByTestId('status')).not.toHaveTextContent('loading'));
}

function summary(over: Partial<VaultSummary> = {}): VaultSummary {
  return {
    vaultId: 'v1',
    vaultSalt: SALT,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    currentVmkVersion: 1,
    rotationState: 'IDLE',
    ...over,
  };
}

async function envelope(vmk: Uint8Array, password: string) {
  return wrapVmk(vmk, wrapKey(password));
}

// A vault record as GetVault returns it, with one envelope wrapping VMK under `vaultpw`.
async function serverVault(over: Record<string, unknown> = {}) {
  return {
    vaultId: 'v1',
    vaultSalt: SALT,
    encryptedName: null,
    currentVmkVersion: 1,
    envelopeVersion: 1,
    vmkEnvelopes: [{ vmkVersion: 1, wrappedVmk: await envelope(VMK, 'vaultpw'), createdAt: new Date(0) }],
    rotationState: 'IDLE' as const,
    rotationLockedAt: null,
    ...over,
  };
}

function storedRegistry(): Record<string, unknown>[] {
  return JSON.parse(localStorage.getItem('cortex_vaults:u1') ?? '[]') as Record<string, unknown>[];
}

async function mediaItem(dekVersion: number, keys: ReturnType<typeof deriveKeys>): Promise<ItemData> {
  const contentId = 'content-1';
  const wrappedDek = await wrapDek(new Uint8Array(32).fill(3), keys.keyEncryptionKey, contentId);
  const meta: FileMetadata = { name: 'a.jpg', contentType: 'image/jpeg', size: 1, contentId };
  return {
    itemId: 'm1',
    vaultId: 'v1',
    itemType: 'MEDIA',
    encryptedMetadata: await encryptMetadata(meta, keys.metadataEncryptionKey),
    wrappedDek,
    dekVersion,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    version: 1,
  };
}

beforeEach(() => {
  localStorage.clear();
  document.title = '';
  delete document.body.dataset.deleted;
  api.listAllVaults.mockRejectedValue(new Error('offline'));
  api.updateVault.mockResolvedValue(undefined);
  api.createVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT });
  api.updateVaultPassword.mockResolvedValue({ envelopeVersion: 1 });
  api.deleteVault.mockResolvedValue({ deletionState: 'DELETED', deletedItems: 0, deletedCollections: 0, deletedShares: 0 });
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

describe('account gate', () => {
  it('keeps the cached registry when ListVaults fails', async () => {
    localStorage.setItem(
      'cortex_vaults:u1',
      JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]),
    );
    await renderProbe();
    expect(localStorage.getItem('cortex_account')).toBe('u1');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal,Work');
  });

  it('adopts a pre-account registry, then merges the server list and drops vaults it no longer has', async () => {
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Photos' }, { vaultId: 'v2', name: 'Gone' }]));
    localStorage.setItem('cortex_vault_id', 'v2');
    api.listAllVaults.mockResolvedValue([summary()]);
    await renderProbe();
    expect(localStorage.getItem('cortex_vaults')).toBeNull();
    expect(localStorage.getItem('cortex_vault_id')).toBeNull();
    expect(screen.getByTestId('vaults')).toHaveTextContent('Photos');
    expect(storedRegistry()).toHaveLength(1);
    expect(storedRegistry()[0]).toMatchObject({ vaultId: 'v1', name: 'Photos', currentVmkVersion: 1, rotationState: 'IDLE' });
    expect(storedRegistry()[0]).not.toHaveProperty('vaultSalt');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBeNull(); // pointed at the dropped vault
  });

  it('logout clears the in-memory vaults but keeps the registry; another account signing in offline sees none of them', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal');
    await act(async () => {
      screen.getByText('logout').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('signedOut');
    expect(screen.getByTestId('vaults')).toHaveTextContent('');
    expect(localStorage.getItem('cortex_account')).toBeNull();
    expect(localStorage.getItem('cortex_vaults:u1')).not.toBeNull();

    vi.mocked(getCurrentUser).mockResolvedValueOnce({ userId: 'u2' } as never);
    await act(async () => {
      screen.getByText('signin').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    expect(localStorage.getItem('cortex_account')).toBe('u2');
    expect(screen.getByTestId('vaults')).toHaveTextContent('');
  });
});

describe('setupVault', () => {
  it('bootstraps envelopeVersion 0 with one VMK envelope, stores derived keys and unlocks', async () => {
    await renderProbe();
    await act(async () => {
      screen.getByText('setup').click();
    });
    expect(api.createVault).toHaveBeenCalled();
    expect(api.updateVaultPassword).toHaveBeenCalledTimes(1);
    const [vaultId, expectedEnvelopeVersion, envelopes] = api.updateVaultPassword.mock.calls[0] as [
      string,
      number,
      { vmkVersion: number; wrappedVmk: Uint8Array; createdAt: Date }[],
    ];
    expect(vaultId).toBe('v1');
    expect(expectedEnvelopeVersion).toBe(0);
    expect(envelopes).toHaveLength(1);
    expect(envelopes[0].vmkVersion).toBe(1);
    expect(unwrapVmk(envelopes[0].wrappedVmk, wrapKey('vaultpw'))).toEqual(VMK);
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', deriveKeys(VMK));
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(document.title.split(' ')).toHaveLength(24);
  });

  it('also stores the encrypted vault name and registers the vault locally', async () => {
    await renderProbe();
    await act(async () => {
      screen.getByText('setup-family').click();
    });
    const [, fields] = api.updateVault.mock.calls[0] as [string, { encryptedName: Uint8Array }];
    expect(decryptCollectionName(fields.encryptedName, deriveKeys(VMK).metadataEncryptionKey)).toBe('Family');
    expect(storedRegistry()[0]).toMatchObject({
      vaultId: 'v1',
      name: 'Family',
      encryptedName: bytesToBase64(fields.encryptedName),
      currentVmkVersion: 1,
      rotationState: 'IDLE',
    });
    expect(storedRegistry()[0]).not.toHaveProperty('vaultSalt');
  });

  it('leaves nothing local when the bootstrap write fails', async () => {
    api.updateVaultPassword.mockRejectedValueOnce(new Error('Network error'));
    await renderProbe();
    await act(async () => {
      screen.getByText('setup').click();
    });
    expect(document.title).toBe('Network error');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    expect(storedRegistry()).toEqual([]);
    expect(vi.mocked(storeKeys)).not.toHaveBeenCalled();
  });
});

describe('unlockVault', () => {
  it('unwraps the current envelope with the correct password and unlocks', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault());
    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', deriveKeys(VMK));
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('rejects a wrong password with WRONG_VAULT_PASSWORD and stays locked', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault());
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.unlockVault('wrongpw', 'v1')).rejects.toThrow(WRONG_VAULT_PASSWORD);
    });
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    expect(vi.mocked(storeKeys)).not.toHaveBeenCalled();
  });

  it('routes an unbootstrapped vault (no envelopes) to setup via VAULT_NEEDS_SETUP', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault({ vmkEnvelopes: [], currentVmkVersion: 0, envelopeVersion: 0 }));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.unlockVault('vaultpw', 'v1')).rejects.toThrow(VAULT_NEEDS_SETUP);
    });
    expect(vi.mocked(storeKeys)).not.toHaveBeenCalled();
  });

  it('sets rotationInterrupted when GetVault reports a non-IDLE rotation state', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault({ rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000 }));
    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
  });

  it('decrypts the server-side name into the registry', async () => {
    const encryptedName = await encryptCollectionName('Family', deriveKeys(VMK).metadataEncryptionKey);
    const vault = await serverVault({ encryptedName, vmkEnvelopes: [{ vmkVersion: 1, wrappedVmk: await envelope(VMK, 'vaultpw'), createdAt: new Date(0) }] });
    api.getVault.mockResolvedValue(vault);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal', encryptedName: bytesToBase64(encryptedName) }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('vaults')).toHaveTextContent('Family');
    expect(storedRegistry()[0]).toMatchObject({ name: 'Family', currentVmkVersion: 1, rotationState: 'IDLE' });
  });
});

describe('renameVault', () => {
  it('encrypts the name for the server, then updates the registry', async () => {
    const keys = deriveKeys(VMK);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    vi.mocked(retrieveKeys).mockResolvedValueOnce(keys as never);
    await renderProbe();
    await act(async () => {
      screen.getByText('rename-v1').click();
    });
    expect(document.title).toBe('renamed');
    const [vaultId, fields] = api.updateVault.mock.calls[0] as [string, { encryptedName: Uint8Array }];
    expect(vaultId).toBe('v1');
    expect(decryptCollectionName(fields.encryptedName, keys.metadataEncryptionKey)).toBe('Work');
    expect(storedRegistry()[0]).toMatchObject({ name: 'Work', encryptedName: bytesToBase64(fields.encryptedName) });
  });

  it('rejects a locked vault without calling the server', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    await act(async () => {
      screen.getByText('rename-v1').click();
    });
    expect(document.title).toBe('Unlock to rename');
    expect(api.updateVault).not.toHaveBeenCalled();
  });
});

describe('vault registry integration', () => {
  it('switchVault reports locked when that vault has no keys on this device', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    await renderProbe();
    await act(async () => {
      screen.getByText('switch-v9').click();
    });
    expect(document.title).toBe('locked');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
  });

  it('switchVault unlocks and activates when keys exist on this device', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    vi.mocked(retrieveKeys).mockResolvedValueOnce({
      keyEncryptionKey: new Uint8Array(32),
      metadataEncryptionKey: new Uint8Array(32),
    } as never);
    await renderProbe();
    const versionBefore = Number(screen.getByTestId('version').textContent);
    await act(async () => {
      screen.getByText('switch-v9').click();
    });
    expect(document.title).toBe('unlocked');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v9');
    expect(Number(screen.getByTestId('version').textContent)).toBe(versionBefore + 1);
  });
});

describe('changeVaultPassword', () => {
  it('re-wraps every envelope under the new password, preserving the version set', async () => {
    const env1 = await envelope(VMK, 'vaultpw');
    const env2 = await envelope(VMK_NEW, 'vaultpw');
    api.getVault.mockResolvedValue(
      await serverVault({
        currentVmkVersion: 2,
        envelopeVersion: 2,
        vmkEnvelopes: [
          { vmkVersion: 1, wrappedVmk: env1, createdAt: new Date(0) },
          { vmkVersion: 2, wrappedVmk: env2, createdAt: new Date(0) },
        ],
      }),
    );
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    await renderProbe();
    await act(async () => {
      screen.getByText('change').click();
    });
    expect(document.title).toBe('changed');
    expect(api.updateVaultPassword).toHaveBeenCalledTimes(1);
    const [vaultId, expectedEnvelopeVersion, envelopes] = api.updateVaultPassword.mock.calls[0] as [
      string,
      number,
      { vmkVersion: number; wrappedVmk: Uint8Array }[],
    ];
    expect(vaultId).toBe('v1');
    expect(expectedEnvelopeVersion).toBe(2);
    expect(envelopes.map((e) => e.vmkVersion)).toEqual([1, 2]);
    expect(unwrapVmk(envelopes[0].wrappedVmk, wrapKey('newvaultpw'))).toEqual(VMK);
    expect(unwrapVmk(envelopes[1].wrappedVmk, wrapKey('newvaultpw'))).toEqual(VMK_NEW);
  });

  it('rejects a wrong current password without writing', async () => {
    api.getVault.mockResolvedValue(await serverVault());
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.changeVaultPassword('wrongpw', 'newvaultpw')).rejects.toThrow(WRONG_VAULT_PASSWORD);
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
  });

  it('retries once on ConflictError against a fresh envelopeVersion', async () => {
    const first = await serverVault({ envelopeVersion: 1 });
    const fresh = await serverVault({
      envelopeVersion: 2,
      vmkEnvelopes: [{ vmkVersion: 1, wrappedVmk: await envelope(VMK, 'vaultpw'), createdAt: new Date(0) }],
    });
    api.getVault.mockResolvedValueOnce(first).mockResolvedValueOnce(fresh);
    api.updateVaultPassword
      .mockRejectedValueOnce(new ConflictError({ message: 'A vault password change cannot add or drop a VMK version', $metadata: {} }))
      .mockResolvedValueOnce({ envelopeVersion: 3 });
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    await renderProbe();
    await act(async () => {
      await sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw');
    });
    expect(api.updateVaultPassword).toHaveBeenCalledTimes(2);
    expect(api.updateVaultPassword.mock.calls[0][1]).toBe(1);
    expect(api.updateVaultPassword.mock.calls[1][1]).toBe(2);
  });
});

describe('rotateEncryptionKeys', () => {
  async function seedRotatableVault() {
    api.getVault.mockResolvedValue(
      await serverVault({
        encryptedName: await encryptCollectionName('Holiday', deriveKeys(VMK).metadataEncryptionKey),
      }),
    );
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Holiday', currentVmkVersion: 1, rotationState: 'IDLE' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
  }

  it('ACQUIREs, sweeps, then RELEASEs once zero stragglers remain', async () => {
    await seedRotatableVault();
    vi.mocked(generateVaultMasterKey).mockResolvedValueOnce(VMK_NEW.slice());
    api.updateVaultRotation
      .mockResolvedValueOnce({ rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, currentVmkVersion: 2, envelopeVersion: 2 })
      .mockResolvedValueOnce({ rotationState: 'IDLE', rotationLockedAt: null, currentVmkVersion: 2, envelopeVersion: 2 });
    await renderProbe();
    await act(async () => {
      screen.getByText('rotate').click();
    });
    expect(document.title).toBe('rotated:24');
    const acquire = api.updateVaultRotation.mock.calls[0][0] as { action: string; newVmkVersion: number; wrappedNewVmk: Uint8Array; expectedState: string };
    expect(acquire).toMatchObject({ action: 'ACQUIRE', expectedState: 'IDLE', newVmkVersion: 2 });
    expect(unwrapVmk(acquire.wrappedNewVmk, wrapKey('vaultpw'))).toEqual(VMK_NEW);
    const release = api.updateVaultRotation.mock.calls[1][0] as { action: string; newEncryptedName: Uint8Array };
    expect(release.action).toBe('RELEASE');
    expect(decryptCollectionName(release.newEncryptedName, deriveKeys(VMK_NEW).metadataEncryptionKey)).toBe('Holiday');
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', deriveKeys(VMK_NEW));
    expect(storedRegistry()[0]).toMatchObject({ currentVmkVersion: 2, rotationState: 'IDLE', name: 'Holiday' });
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('a local commit failure after RELEASE leaves the registry IDLE, not IN_PROGRESS', async () => {
    await seedRotatableVault();
    vi.mocked(generateVaultMasterKey).mockResolvedValueOnce(VMK_NEW.slice());
    api.updateVaultRotation
      .mockResolvedValueOnce({ rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, currentVmkVersion: 2, envelopeVersion: 2 })
      .mockResolvedValueOnce({ rotationState: 'IDLE', rotationLockedAt: null, currentVmkVersion: 2, envelopeVersion: 2 });
    // RELEASE reaches the server (IDLE), then the local key store fails.
    vi.mocked(storeKeys).mockRejectedValueOnce(new Error('disk full'));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.rotateEncryptionKeys('vaultpw')).rejects.toThrow('disk full');
    });
    expect(api.updateVaultRotation.mock.calls.map((c) => (c[0] as { action: string }).action)).toEqual(['ACQUIRE', 'RELEASE']);
    // The server is IDLE; the registry must not claim a rotation is still in progress.
    expect(storedRegistry()[0]).toMatchObject({ rotationState: 'IDLE' });
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('withholds RELEASE when a straggler item remains, leaving the rotation IN_PROGRESS', async () => {
    await seedRotatableVault();
    vi.mocked(generateVaultMasterKey).mockResolvedValueOnce(VMK_NEW.slice());
    api.updateVaultRotation.mockResolvedValueOnce({
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
      currentVmkVersion: 2,
      envelopeVersion: 2,
    });
    // The first list is empty; the re-list finds a straggler that appeared after ACQUIRE.
    const straggler: ItemData = {
      itemId: 'late',
      vaultId: 'v1',
      itemType: 'MEDIA',
      encryptedMetadata: new Uint8Array([1]),
      wrappedDek: new Uint8Array(97),
      dekVersion: 1,
      createdAt: new Date(0),
      updatedAt: new Date(0),
      version: 1,
    };
    vi.mocked(listAllItems).mockResolvedValueOnce([]).mockResolvedValueOnce([straggler]);
    // The keys this device actually holds are the OLD ones: storeKeys was never called.
    const oldKeys = deriveKeys(VMK);
    vi.mocked(retrieveKeys).mockResolvedValue(oldKeys as never);
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.rotateEncryptionKeys('vaultpw')).rejects.toThrow(ROTATION_INCOMPLETE);
    });
    expect(api.updateVaultRotation.mock.calls.map((c) => (c[0] as { action: string }).action)).toEqual(['ACQUIRE']);
    // The registry must NOT advertise the new version with the old KEK: getVaultKeys stays consistent.
    expect(storedRegistry()[0]).toMatchObject({ currentVmkVersion: 1, rotationState: 'IN_PROGRESS' });
    const held = await getVaultKeys();
    expect(held.kekVersion).toBe(1);
    expect(held.kek).toEqual(oldKeys.keyEncryptionKey);
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
  });

  it('sweeps a stale-version item that was present at ACQUIRE, then RELEASEs (never stranded)', async () => {
    await seedRotatableVault();
    vi.mocked(generateVaultMasterKey).mockResolvedValueOnce(VMK_NEW.slice());
    api.updateVaultRotation
      .mockResolvedValueOnce({ rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, currentVmkVersion: 2, envelopeVersion: 2 })
      .mockResolvedValueOnce({ rotationState: 'IDLE', rotationLockedAt: null, currentVmkVersion: 2, envelopeVersion: 2 });
    const item = await mediaItem(1, deriveKeys(VMK));
    vi.mocked(listAllItems).mockResolvedValueOnce([item]).mockResolvedValueOnce([]);
    await renderProbe();
    await act(async () => {
      await sessionRef.current!.rotateEncryptionKeys('vaultpw');
    });
    expect(updateItemRotation).toHaveBeenCalledTimes(1);
    const [itemId, , dekVersion] = vi.mocked(updateItemRotation).mock.calls[0];
    expect(itemId).toBe('m1');
    expect(dekVersion).toBe(2);
    expect(api.updateVaultRotation.mock.calls[1][0]).toMatchObject({ action: 'RELEASE' });
  });

  it('resumes an IN_PROGRESS rotation: sweeps stragglers with the FROM envelope, then RELEASEs', async () => {
    // The previous attempt ACQUIREd (server bumped to v2) but failed mid-sweep; the v1 envelope
    // still wraps the old VMK, the v2 envelope the new one. Resume must derive the old KEK from
    // the v1 envelope, not the (now current) v2 one, or the un-swept item never unwraps.
    api.getVault.mockResolvedValue(
      await serverVault({
        encryptedName: await encryptCollectionName('Holiday', deriveKeys(VMK).metadataEncryptionKey),
        currentVmkVersion: 2,
        envelopeVersion: 2,
        rotationState: 'IN_PROGRESS',
        rotationLockedAt: 1700000000,
        vmkEnvelopes: [
          { vmkVersion: 1, wrappedVmk: await envelope(VMK, 'vaultpw'), createdAt: new Date(0) },
          { vmkVersion: 2, wrappedVmk: await envelope(VMK_NEW, 'vaultpw'), createdAt: new Date(0) },
        ],
      }),
    );
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Holiday', currentVmkVersion: 2, rotationState: 'IN_PROGRESS' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    const item = await mediaItem(1, deriveKeys(VMK)); // still on the generation being swept from
    vi.mocked(listAllItems).mockResolvedValueOnce([item]).mockResolvedValueOnce([]);
    api.updateVaultRotation.mockResolvedValueOnce({ rotationState: 'IDLE', rotationLockedAt: null, currentVmkVersion: 2, envelopeVersion: 2 });
    await renderProbe();
    await act(async () => {
      await sessionRef.current!.rotateEncryptionKeys('vaultpw');
    });
    expect(api.updateVaultRotation.mock.calls.map((c) => (c[0] as { action: string }).action)).toEqual(['RELEASE']);
    const [, , dekVersion] = vi.mocked(updateItemRotation).mock.calls[0];
    expect(dekVersion).toBe(2);
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', deriveKeys(VMK_NEW));
    expect(storedRegistry()[0]).toMatchObject({ currentVmkVersion: 2, rotationState: 'IDLE' });
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('rejects a wrong confirmation password without ACQUIRE', async () => {
    await seedRotatableVault();
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.rotateEncryptionKeys('wrongpw')).rejects.toThrow(WRONG_VAULT_PASSWORD);
    });
    expect(api.updateVaultRotation).not.toHaveBeenCalled();
  });
});

describe('recoverVault', () => {
  let realGenerateRecoveryKey: (vmk: Uint8Array) => string;

  beforeEach(async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    realGenerateRecoveryKey = real.generateRecoveryKey;
  });

  it('re-wraps the phrase VMK under the new password and returns the SAME phrase', async () => {
    const phrase = realGenerateRecoveryKey(VMK);
    const encryptedName = await encryptCollectionName('Family', deriveKeys(VMK).metadataEncryptionKey);
    localStorage.setItem(
      'cortex_vaults:u1',
      JSON.stringify([{ vaultId: 'v1', name: 'Personal', encryptedName: bytesToBase64(encryptedName) }]),
    );
    api.getVault.mockResolvedValue(await serverVault({ encryptedName }));
    await renderProbe();
    let result: { phrase: string; vaultId: string; name: string } | undefined;
    await act(async () => {
      result = await sessionRef.current!.recoverVault(phrase, 'newpw');
    });
    expect(result).toEqual({ phrase, vaultId: 'v1', name: 'Family' });
    expect(api.updateVaultPassword).toHaveBeenCalledTimes(1);
    const [, expectedEnvelopeVersion, envelopes] = api.updateVaultPassword.mock.calls[0] as [
      string,
      number,
      { vmkVersion: number; wrappedVmk: Uint8Array }[],
    ];
    expect(expectedEnvelopeVersion).toBe(1);
    expect(unwrapVmk(envelopes[0].wrappedVmk, wrapKey('newpw'))).toEqual(VMK);
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', deriveKeys(VMK));
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(storedRegistry()[0]).toMatchObject({ name: 'Family', currentVmkVersion: 1, rotationState: 'IDLE' });
  });

  it('refuses while rotationState is not IDLE', async () => {
    const phrase = realGenerateRecoveryKey(VMK);
    api.getVault.mockResolvedValue(await serverVault({ rotationState: 'IN_PROGRESS' }));
    await renderProbe();
    await act(async () => {
      await expect(
        sessionRef.current!.recoverVault(phrase, 'newpw', { vaultId: 'v1' }),
      ).rejects.toThrow(RECOVERY_BLOCKED_BY_ROTATION);
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
  });

  it('writes nothing when the phrase does not decrypt the encryptedName', async () => {
    const wrongPhrase = realGenerateRecoveryKey(new Uint8Array(32).fill(9));
    const encryptedName = await encryptCollectionName('Family', deriveKeys(VMK).metadataEncryptionKey);
    api.getVault.mockResolvedValue(await serverVault({ encryptedName }));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.recoverVault(wrongPhrase, 'newpw', { vaultId: 'v1' })).rejects.toThrow(
        /don't open a vault on this device/,
      );
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it('identifies nothing when no known vault name decrypts (local path)', async () => {
    const wrongPhrase = realGenerateRecoveryKey(new Uint8Array(32).fill(9));
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.recoverVault(wrongPhrase, 'newpw')).rejects.toThrow(/don't open a vault on this device/);
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
  });

  it('writes nothing when there is no encryptedName and no data to prove a wrong phrase against', async () => {
    const wrongPhrase = realGenerateRecoveryKey(new Uint8Array(32).fill(9));
    api.getVault.mockResolvedValue(await serverVault({ encryptedName: null }));
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.recoverVault(wrongPhrase, 'newpw', { vaultId: 'v1' })).rejects.toThrow(
        /don't open a vault on this device/,
      );
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
  });

  it('refuses when the only candidates exist but the phrase does not open them', async () => {
    const wrongPhrase = realGenerateRecoveryKey(new Uint8Array(32).fill(9));
    api.getVault.mockResolvedValue(await serverVault({ encryptedName: null }));
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    // A collection encrypted under the correct keys — the wrong phrase's key cannot open it.
    vi.mocked(listAllCollections).mockResolvedValueOnce([
      {
        collectionId: 'c1',
        vaultId: 'v1',
        encryptedMetadata: await encryptCollectionName('Trips', deriveKeys(VMK).metadataEncryptionKey),
        itemCount: 0,
        createdAt: new Date(0),
        updatedAt: new Date(0),
      },
    ]);
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.recoverVault(wrongPhrase, 'newpw', { vaultId: 'v1' })).rejects.toThrow(
        /don't open a vault on this device/,
      );
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
  });

  it('rejects a superseded phrase when only an old-generation item exists (no encryptedName)', async () => {
    const supersededPhrase = realGenerateRecoveryKey(VMK);
    // Current generation is 2; the only candidate is a v1 item. The superseded phrase opens it,
    // but accepting it would overwrite the v2 envelope with the v1 VMK and break swept items.
    vi.mocked(listItems).mockResolvedValueOnce([await mediaItem(1, deriveKeys(VMK))]);
    api.getVault.mockResolvedValue(
      await serverVault({
        encryptedName: null,
        currentVmkVersion: 2,
        envelopeVersion: 2,
        vmkEnvelopes: [
          { vmkVersion: 1, wrappedVmk: await envelope(VMK, 'vaultpw'), createdAt: new Date(0) },
          { vmkVersion: 2, wrappedVmk: await envelope(VMK_NEW, 'vaultpw'), createdAt: new Date(0) },
        ],
      }),
    );
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.recoverVault(supersededPhrase, 'newpw', { vaultId: 'v1' })).rejects.toThrow(
        /don't open a vault on this device/,
      );
    });
    expect(api.updateVaultPassword).not.toHaveBeenCalled();
  });

  it('proves via an old-key item when the vault has no encryptedName', async () => {
    const phrase = realGenerateRecoveryKey(VMK);
    vi.mocked(listItems).mockResolvedValueOnce([await mediaItem(1, deriveKeys(VMK))]);
    api.getVault.mockResolvedValue(await serverVault({ encryptedName: null }));
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    let result: { phrase: string; vaultId: string; name: string } | undefined;
    await act(async () => {
      result = await sessionRef.current!.recoverVault(phrase, 'newpw', { vaultId: 'v1' });
    });
    expect(result).toEqual({ phrase, vaultId: 'v1', name: 'Personal' });
    expect(api.updateVaultPassword).toHaveBeenCalledTimes(1);
  });
});

describe('deleteVault', () => {
  it('confirms by unwrapping the current envelope, then loops DeleteVault until DELETED', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal', lastOpened: 2 }, { vaultId: 'v2', name: 'Work', lastOpened: 1 }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault());
    api.deleteVault
      .mockResolvedValueOnce({ deletionState: 'DELETING', deletedItems: 2, deletedCollections: 0, deletedShares: 0 })
      .mockResolvedValueOnce({ deletionState: 'DELETED', deletedItems: 1, deletedCollections: 0, deletedShares: 0 });
    await renderProbe();
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('deleted');
    expect(api.deleteVault).toHaveBeenCalledTimes(2);
    expect(document.body.dataset.deleted).toBe('3');
    expect(storedRegistry().map((v) => v.vaultId)).toEqual(['v2']);
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v2');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it('refuses a wrong password and makes no DeleteVault call', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault());
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.deleteVault('v1', 'wrongpw')).rejects.toThrow(WRONG_VAULT_PASSWORD);
    });
    expect(api.deleteVault).not.toHaveBeenCalled();
  });

  it('refuses with DELETE_REFUSED when the vault has no envelope to check', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault({ vmkEnvelopes: [], currentVmkVersion: 0, envelopeVersion: 0 }));
    await renderProbe();
    await act(async () => {
      await expect(sessionRef.current!.deleteVault('v1', 'vaultpw')).rejects.toThrow(DELETE_REFUSED);
    });
    expect(api.deleteVault).not.toHaveBeenCalled();
  });

  it('treats a 404 on a later call as success', async () => {
    const { ResourceNotFoundError } = await import('@cortex/client');
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault());
    api.deleteVault
      .mockResolvedValueOnce({ deletionState: 'DELETING', deletedItems: 5, deletedCollections: 0, deletedShares: 0 })
      .mockRejectedValueOnce(new ResourceNotFoundError({ message: 'Vault not found', $metadata: {} }));
    await renderProbe();
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('deleted');
    expect(document.body.dataset.deleted).toBe('5');
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!)).toEqual([]);
  });

  it('stops on a 409 with the server message and purges nothing', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    api.getVault.mockResolvedValue(await serverVault());
    api.deleteVault.mockRejectedValueOnce(
      new ConflictError({ message: 'A key rotation is in progress; finish it before deleting this vault', $metadata: {} }),
    );
    await renderProbe();
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('A key rotation is in progress; finish it before deleting this vault');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
  });
});

describe('composed rotate → recover → change (multi-generation vault)', () => {
  it('changeVaultPassword still succeeds after a recovery re-wrapped only the current envelope', async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    const keysOld = deriveKeys(VMK);
    const keysNew = deriveKeys(VMK_NEW);
    // A tiny stateful vault server: the composed flow drives the real session methods.
    let envelopeVersion = 1;
    let currentVmkVersion = 1;
    let rotationState: 'IDLE' | 'IN_PROGRESS' = 'IDLE';
    let encryptedName: Uint8Array | null = await encryptCollectionName('Holiday', keysOld.metadataEncryptionKey);
    let envelopes = [{ vmkVersion: 1, wrappedVmk: await envelope(VMK, 'vaultpw'), createdAt: new Date(0) }];
    const snapshot = () => ({
      vaultId: 'v1',
      vaultSalt: SALT,
      encryptedName,
      currentVmkVersion,
      envelopeVersion,
      vmkEnvelopes: envelopes.map((e) => ({ ...e })),
      rotationState,
      rotationLockedAt: null,
    });
    api.getVault.mockImplementation(async () => snapshot());
    api.updateVaultRotation.mockImplementation(
      async (args: { action: string; newVmkVersion?: number; wrappedNewVmk?: Uint8Array; newEncryptedName?: Uint8Array }) => {
        if (args.action === 'ACQUIRE') {
          envelopes = [
            ...envelopes,
            { vmkVersion: args.newVmkVersion!, wrappedVmk: args.wrappedNewVmk!, createdAt: new Date(0) },
          ];
          currentVmkVersion = args.newVmkVersion!;
          envelopeVersion += 1;
          rotationState = 'IN_PROGRESS';
        } else {
          rotationState = 'IDLE';
          if (args.newEncryptedName) encryptedName = args.newEncryptedName;
        }
        return { rotationState, rotationLockedAt: null, currentVmkVersion, envelopeVersion };
      },
    );
    api.updateVaultPassword.mockImplementation(
      async (_vaultId: string, expected: number, list: { vmkVersion: number; wrappedVmk: Uint8Array; createdAt: Date }[]) => {
        envelopes = list.map((e) => ({ ...e }));
        envelopeVersion = expected + 1;
        return { envelopeVersion };
      },
    );
    api.updateVault.mockResolvedValue(undefined);
    localStorage.setItem(
      'cortex_vaults:u1',
      JSON.stringify([{ vaultId: 'v1', name: 'Holiday', encryptedName: bytesToBase64(encryptedName), currentVmkVersion: 1, rotationState: 'IDLE' }]),
    );
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    await renderProbe();

    // 1. rotate: version 1 → 2, the new current envelope wraps VMK_NEW under the current password.
    vi.mocked(generateVaultMasterKey).mockResolvedValueOnce(VMK_NEW.slice());
    await act(async () => {
      await sessionRef.current!.rotateEncryptionKeys('vaultpw');
    });
    expect(currentVmkVersion).toBe(2);

    // 2. recover with the phrase for VMK_NEW. Recovery re-wraps ONLY the current (v2) envelope;
    //    envelope 1 stays wrapped under the pre-recovery password.
    await act(async () => {
      await sessionRef.current!.recoverVault(real.generateRecoveryKey(VMK_NEW), 'recoverypw');
    });
    expect(unwrapVmk(envelopes.find((e) => e.vmkVersion === 1)!.wrappedVmk, wrapKey('vaultpw'))).toEqual(VMK);
    expect(unwrapVmk(envelopes.find((e) => e.vmkVersion === 2)!.wrappedVmk, wrapKey('recoverypw'))).toEqual(VMK_NEW);

    // 3. the superseded password opens only envelope 1: it must be rejected, not silently accepted.
    const writesAfterRecovery = api.updateVaultPassword.mock.calls.length;
    await act(async () => {
      await expect(sessionRef.current!.changeVaultPassword('vaultpw', 'finalpw')).rejects.toThrow(WRONG_VAULT_PASSWORD);
    });
    expect(api.updateVaultPassword.mock.calls.length).toBe(writesAfterRecovery);

    // 4. change with the recovery password (the one that opens the current envelope): the
    //    un-openable superseded envelope must not block it.
    const supersededBefore = envelopes.find((e) => e.vmkVersion === 1)!.wrappedVmk;
    await act(async () => {
      await expect(sessionRef.current!.changeVaultPassword('recoverypw', 'finalpw')).resolves.toBeUndefined();
    });
    const calls = api.updateVaultPassword.mock.calls;
    const submitted = calls[calls.length - 1][2] as { vmkVersion: number; wrappedVmk: Uint8Array }[];
    expect(submitted.map((e) => e.vmkVersion)).toEqual([1, 2]);
    // The superseded envelope is passed through untouched; only the current one is re-wrapped.
    expect(submitted.find((e) => e.vmkVersion === 1)!.wrappedVmk).toEqual(supersededBefore);
    expect(unwrapVmk(submitted.find((e) => e.vmkVersion === 2)!.wrappedVmk, wrapKey('finalpw'))).toEqual(VMK_NEW);
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', keysNew);
  });
});
