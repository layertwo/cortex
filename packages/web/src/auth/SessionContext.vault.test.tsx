import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import { getCurrentUser } from 'aws-amplify/auth';
import {
  deriveKeys,
  retrieveKeys,
  deriveVaultMasterKey,
  storeKeys,
  clearKeys,
  stringToBytes,
  bytesToString,
  bytesToBase64,
} from '@cortex/encryption';
import { ConflictError, ResourceNotFoundError, type CollectionData, type ItemData, type VaultSummary } from '@cortex/client';
import { createVerifier, checkVerifier, saveVerifier, loadVerifier } from '../vault/verifier';
import { encryptCollectionName, decryptCollectionName } from '../items/collectionMetadata';
import { listItems, listAllItems } from '../api/items';
import { listAllCollections, updateCollection } from '../api/collections';
import { encryptMetadata } from '../items/metadata';

// Hoisted so the vi.mock factories below can reference these without a TDZ error.
const { SALT, MASTER, api } = vi.hoisted(() => ({
  SALT: new Uint8Array(16).fill(9),
  MASTER: new Uint8Array(32).fill(5),
  api: {
    createVault: vi.fn(),
    getVaultSalt: vi.fn(),
    getVault: vi.fn(),
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

vi.mock('../api/items', () => ({ listAllItems: vi.fn(async () => []), listItems: vi.fn(async () => []) }));
vi.mock('../api/collections', () => ({
  listAllCollections: vi.fn(async () => []),
  updateCollection: vi.fn(async () => {}),
}));

// Real verifier + real deriveKeys/encrypt/decrypt; mock only the slow Argon2id step.
vi.mock('@cortex/encryption', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@cortex/encryption')>();
  return {
    ...actual,
    deriveVaultMasterKey: vi.fn(async () => MASTER),
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
  REKEYED_ERROR,
  CANCELLED_ERROR,
  type SessionValue,
} from './SessionContext';

// The rotation tests drive the session directly instead of through Probe buttons.
const sessionRef: { current: SessionValue | null } = { current: null };

function Probe() {
  const s = useSession();
  sessionRef.current = s;
  return (
    <div>
      <span data-testid="status">{s.status}</span>
      <span data-testid="rotation-interrupted">{String(s.rotationInterrupted)}</span>
      <span data-testid="types">
        {typeof s.changeVaultPassword},{typeof s.rotationInterrupted}
      </span>
      <button
        onClick={() =>
          s.setupVault('vaultpw')
            .then((r) => (document.title = r))
            .catch((e) => (document.title = e.message))
        }
      >
        setup
      </button>
      <button onClick={() => s.unlockVault('vaultpw').catch((e) => (document.title = e.message))}>
        unlock
      </button>
      <button onClick={() => s.changeVaultPassword('vaultpw', 'newvaultpw').catch(() => {})}>
        change
      </button>
      <span data-testid="vaults">{s.vaults.map((v) => v.name).join(',')}</span>
      <span data-testid="active">{s.activeVault?.name ?? ''}</span>
      <span data-testid="version">{s.vaultVersion}</span>
      <button
        onClick={() =>
          s.setupVault('vaultpw', 'Family')
            .then((r) => (document.title = r))
            .catch((e) => (document.title = e.message))
        }
      >
        setup-family
      </button>
      <button onClick={() => s.switchVault('v9').then((r) => (document.title = r))}>switch-v9</button>
      <button
        onClick={() =>
          s.renameVault('v1', 'Work')
            .then(() => (document.title = 'renamed'))
            .catch((e) => (document.title = e.message))
        }
      >
        rename-v1
      </button>
      <button onClick={() => s.logout()}>logout</button>
      <button onClick={() => s.signInAccount('a@b.com', 'pw')}>signin</button>
      <button
        onClick={() =>
          s.recoverVault(document.body.dataset.phrase ?? '', 'newpw')
            .then((r) => (document.title = 'recovered:' + r.vaultId + ':' + r.phrase.split(' ').length))
            .catch((e) => (document.title = e.message))
        }
      >
        recover
      </button>
      <button
        onClick={() =>
          s.recoverVault(document.body.dataset.phrase ?? '', 'newpw', undefined, { vaultId: 'v1' })
            .then((r) => (document.title = 'recovered:' + r.vaultId))
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

// The account gate is asynchronous (getCurrentUser, then ListVaults): wait for it to route
// before driving the session, otherwise registry writers see no account yet.
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
    kekVersion: 1,
    rotationState: 'IDLE',
    createdAt: new Date(0),
    updatedAt: new Date(0),
    ...over,
  };
}

function storedRegistry(): Record<string, unknown>[] {
  return JSON.parse(localStorage.getItem('cortex_vaults:u1') ?? '[]') as Record<string, unknown>[];
}

beforeEach(() => {
  localStorage.clear();
  document.title = '';
  // Offline by default: the gate keeps whatever registry a test seeded. Tests that exercise
  // the server path override this with mockResolvedValue.
  api.listAllVaults.mockRejectedValue(new Error('offline'));
  api.updateVault.mockResolvedValue(undefined);
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
    expect(storedRegistry()[0]).toMatchObject({ vaultId: 'v1', name: 'Photos', kekVersion: 1, rotationState: 'IDLE' });
    expect(storedRegistry()[0]).not.toHaveProperty('vaultSalt');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBeNull(); // pointed at the dropped vault
  });

  it('a password change elsewhere: sync overwrites the stale local blob so the new password unlocks', async () => {
    const stale = deriveKeys(new Uint8Array(32).fill(42));
    const current = deriveKeys(MASTER);
    saveVerifier('v1', await createVerifier(stale.metadataEncryptionKey));
    const serverVerifier = await createVerifier(current.metadataEncryptionKey);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    api.listAllVaults.mockResolvedValue([summary({ verifier: stringToBytes(serverVerifier), kekVersion: 2 })]);
    await renderProbe();
    expect(loadVerifier('v1')).toBe(serverVerifier);
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
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

describe('SessionContext vault', () => {
  it('setupVault creates a vault, stores keys, unlocks, returns recovery phrase', async () => {
    api.createVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT });
    await renderProbe();
    await act(async () => {
      screen.getByText('setup').click();
    });
    expect(api.createVault).toHaveBeenCalled();
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(document.title.split(' ')).toHaveLength(24);
  });

  it('setupVault is two calls: CreateVault, then UpdateVault with the encrypted name and the verifier', async () => {
    const keys = deriveKeys(MASTER);
    api.createVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT });
    await renderProbe();
    await act(async () => {
      screen.getByText('setup-family').click();
    });
    expect(api.updateVault).toHaveBeenCalledTimes(1);
    const [vaultId, fields] = api.updateVault.mock.calls[0] as [string, { encryptedName: Uint8Array; verifier: Uint8Array }];
    expect(vaultId).toBe('v1');
    expect(bytesToString(fields.verifier)).toBe(loadVerifier('v1'));
    expect(decryptCollectionName(fields.encryptedName, keys.metadataEncryptionKey)).toBe('Family');
    const [stored] = storedRegistry();
    expect(stored).toMatchObject({
      vaultId: 'v1',
      name: 'Family',
      encryptedName: bytesToBase64(fields.encryptedName),
      kekVersion: 1,
      rotationState: 'IDLE',
    });
    expect(stored).not.toHaveProperty('vaultSalt');
    expect(stored).not.toHaveProperty('verifier');
  });

  it('setupVault leaves nothing local when UpdateVault fails', async () => {
    api.createVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT });
    api.updateVault.mockRejectedValueOnce(new Error('Network error'));
    await renderProbe();
    await act(async () => {
      screen.getByText('setup').click();
    });
    expect(document.title).toBe('Network error');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    expect(loadVerifier('v1')).toBeNull();
    expect(storedRegistry()).toEqual([]);
  });

  it('unlockVault with the correct password unlocks', async () => {
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVaultSalt.mockResolvedValue(SALT);
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
    });

    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('unlockVault sets rotationInterrupted when GetVault reports a non-IDLE rotation state', async () => {
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVaultSalt.mockResolvedValue(SALT);
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
    });

    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
  });

  it('unlockVault with the wrong password throws and stays locked', async () => {
    const wrong = deriveKeys(new Uint8Array(32).fill(42));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', await createVerifier(wrong.metadataEncryptionKey));
    api.getVaultSalt.mockResolvedValue(SALT);

    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(document.title).toBe('Incorrect vault password');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it('unlockVault hard-fails (does not unlock) when the verifier is missing', async () => {
    localStorage.setItem('cortex_vault_id:u1', 'v1'); // vault id present, but no verifier blob
    api.getVaultSalt.mockResolvedValue(SALT);

    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(document.title).toMatch(/verifier missing/i);
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it('unlockVault on a new device uses the server salt and verifier, then saves the verifier locally', async () => {
    const keys = deriveKeys(MASTER);
    const verifier = await createVerifier(keys.metadataEncryptionKey);
    api.listAllVaults.mockResolvedValue([summary({ verifier: stringToBytes(verifier) })]);
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
      verifier: stringToBytes(verifier), // server already has one: GetVault confirms it
    });
    await renderProbe();
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal');
    expect(storedRegistry()[0]).not.toHaveProperty('verifier');
    expect(loadVerifier('v1')).toBeNull();

    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(loadVerifier('v1')).toBe(verifier);
    expect(api.getVaultSalt).not.toHaveBeenCalled();
    expect(api.updateVault).not.toHaveBeenCalled();
  });

  it('unlockVault uploads a legacy local verifier when the server has none', async () => {
    const keys = deriveKeys(MASTER);
    const local = await createVerifier(keys.metadataEncryptionKey);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', local);
    api.listAllVaults.mockResolvedValue([summary()]); // listed, but no verifier stored server-side
    api.getVault.mockResolvedValueOnce({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
      verifier: null, // GetVault confirms the server truly has none
    });
    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(api.updateVault).toHaveBeenCalledWith('v1', { verifier: stringToBytes(local) });
  });

  it('unlockVault does not upload the local verifier when GetVault reports the server already has one', async () => {
    // This session never synced (no ListVaults call succeeded), so `entry.verifier` is unknown;
    // only GetVault's fresh read can tell the difference between "server has none" and
    // "this session doesn't know yet" (final review Important 1).
    const keys = deriveKeys(MASTER);
    const local = await createVerifier(keys.metadataEncryptionKey);
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', local);
    api.getVaultSalt.mockResolvedValue(SALT);
    api.getVault.mockResolvedValueOnce({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
      verifier: stringToBytes('server-already-has-a-verifier'),
    });

    await renderProbe();
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(api.updateVault).not.toHaveBeenCalled();
  });

  it('unlockVault decrypts the server-side name into the registry', async () => {
    const keys = deriveKeys(MASTER);
    const verifier = await createVerifier(keys.metadataEncryptionKey);
    const encryptedName = await encryptCollectionName('Family', keys.metadataEncryptionKey);
    api.listAllVaults.mockResolvedValue([summary({ verifier: stringToBytes(verifier), encryptedName })]);
    await renderProbe();
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal');
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('vaults')).toHaveTextContent('Family');
    expect(screen.getByTestId('active')).toHaveTextContent('Family');
    expect(storedRegistry()[0]).toMatchObject({ name: 'Family', encryptedName: bytesToBase64(encryptedName) });
  });
});

describe('renameVault', () => {
  it('encrypts the name for the server, then updates the registry', async () => {
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    (retrieveKeys as Mock).mockResolvedValueOnce(keys as never);
    await renderProbe();
    await act(async () => {
      screen.getByText('rename-v1').click();
    });
    expect(document.title).toBe('renamed');
    const [vaultId, fields] = api.updateVault.mock.calls[0] as [string, { encryptedName: Uint8Array }];
    expect(vaultId).toBe('v1');
    expect(decryptCollectionName(fields.encryptedName, keys.metadataEncryptionKey)).toBe('Work');
    expect(screen.getByTestId('vaults')).toHaveTextContent('Work');
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
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal');
  });

  it('leaves the registry alone when the server rejects the rename', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    (retrieveKeys as Mock).mockResolvedValueOnce(deriveKeys(MASTER) as never);
    api.updateVault.mockRejectedValueOnce(new Error('Network error'));
    await renderProbe();
    await act(async () => {
      screen.getByText('rename-v1').click();
    });
    expect(document.title).toBe('Network error');
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal');
    expect(storedRegistry()[0]).toEqual({ vaultId: 'v1', name: 'Personal' });
  });
});

describe('changeVaultPassword', () => {
  it('is exposed on SessionValue as a function, alongside rotationInterrupted as a boolean', async () => {
    await renderProbe();
    expect(screen.getByTestId('types')).toHaveTextContent('function,boolean');
    // Full integration coverage (wrong-password fast-fail, sweep, phrase gate) lives in
    // ChangeVaultPassword.test.tsx (Task 9), this is just the wiring smoke test.
    expect(api.getVault).not.toHaveBeenCalled();
  });

  it('resuming an interrupted rotation ACQUIREs with the vault\'s actual rotationState, not a hardcoded IDLE', async () => {
    // Regression test: GetVault reporting IN_PROGRESS (a crashed mid-sweep attempt)
    // must NOT cause the ACQUIRE call to assert expectedState: 'IDLE', the backend's
    // conditional write would then always throw ConflictError, since the vault is
    // genuinely IN_PROGRESS and the 7-day staleness window hasn't elapsed. The resume
    // path must ACQUIRE using the vault's own current state.
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
    });
    api.updateVaultRotation.mockResolvedValue({ rotationState: 'IN_PROGRESS', rotationLockedAt: Date.now() });

    await renderProbe();
    await act(async () => {
      screen.getByText('change').click();
    });

    expect(api.updateVaultRotation).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'ACQUIRE', expectedState: 'IN_PROGRESS' }),
    );
  });
});

describe('vault registry integration', () => {
  it('setupVault registers the vault under its name and makes it active', async () => {
    api.createVault.mockResolvedValue({ vaultId: 'v2', vaultSalt: SALT });
    await renderProbe();
    await act(async () => {
      screen.getByText('setup-family').click();
    });
    expect(screen.getByTestId('vaults')).toHaveTextContent('Family');
    expect(screen.getByTestId('active')).toHaveTextContent('Family');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v2');
  });

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
    (retrieveKeys as Mock).mockResolvedValueOnce({
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
    expect(screen.getByTestId('active')).toHaveTextContent('Work');
    expect(Number(screen.getByTestId('version').textContent)).toBe(versionBefore + 1);
  });

  it('switchVault resolves locked (not a throw) when retrieveKeys rejects on a storage error', async () => {
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    (retrieveKeys as Mock).mockRejectedValueOnce(new Error('Failed to retrieve keys: IndexedDB unavailable'));
    await renderProbe();
    await act(async () => {
      screen.getByText('switch-v9').click();
    });
    expect(document.title).toBe('locked');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
  });
});

describe('recoverVault', () => {
  it('re-secures the vault the phrase opens and unlocks it', async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    document.body.dataset.phrase = real.generateRecoveryKey(MASTER);
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.listAllVaults.mockResolvedValue([{ vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', createdAt: new Date(0), updatedAt: new Date(0) }]);
    api.getVault.mockResolvedValue({
      vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', rotationLockedAt: null,
      encryptedName: null, verifier: null, pendingVaultSalt: null, pendingVerifier: null,
    });
    api.updateVaultRotation.mockImplementation(async (args: { action: string; newVaultSalt?: Uint8Array; newVerifier?: Uint8Array }) =>
      args.action === 'ACQUIRE'
        ? { rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, pendingVaultSalt: args.newVaultSalt ?? null, pendingVerifier: args.newVerifier ?? null }
        : { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null },
    );

    await renderProbe();
    const listAllVaultsCallsBeforeRecovery = api.listAllVaults.mock.calls.length;
    await act(async () => {
      screen.getByText('recover').click();
    });
    expect(document.title).toBe('recovered:v1:24');
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(api.updateVaultRotation).toHaveBeenCalledWith(expect.objectContaining({ action: 'RELEASE', kekVersion: 2 }));
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
    // ListVaults is eventually consistent: a re-sync after RELEASE could read this stale mock
    // (still kekVersion 1) and stomp the commit rotateVault just made. There must be no sync
    // after RELEASE, and the registry row must already carry the rotation's own commit.
    expect(api.listAllVaults).toHaveBeenCalledTimes(listAllVaultsCallsBeforeRecovery);
    expect(storedRegistry().find((v) => v.vaultId === 'v1')).toMatchObject({
      kekVersion: 2,
      rotationState: 'IDLE',
      name: 'Personal',
    });
  });

  it('rejects with the generic message when the phrase opens nothing here', async () => {
    document.body.dataset.phrase = 'alpha bravo charlie';
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    await renderProbe();
    await act(async () => {
      screen.getByText('recover').click();
    });
    expect(document.title).toMatch(/don't open a vault on this device/);
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it("new device: a wrong phrase against a vault with a collection throws PHRASE_ERROR before any rotation write", async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    document.body.dataset.phrase = real.generateRecoveryKey(new Uint8Array(32).fill(7));
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    // No verifier saved for v1, simulates a new device that has never opened this vault.
    vi.mocked(listItems).mockResolvedValueOnce([]);
    vi.mocked(listAllCollections).mockResolvedValueOnce([
      {
        collectionId: 'c1',
        vaultId: 'v1',
        encryptedMetadata: new Uint8Array([1, 2, 3]),
        itemCount: 0,
        createdAt: new Date(0),
        updatedAt: new Date(0),
      },
    ]);
    api.getVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', rotationLockedAt: null });

    await renderProbe();
    await act(async () => {
      screen.getByText('recover-kit').click();
    });
    expect(document.title).toMatch(/don't open a vault on this device/);
    expect(vi.mocked(listAllCollections)).toHaveBeenCalledWith('v1');
    expect(api.updateVaultRotation).not.toHaveBeenCalled();
  });

  it('new device: proof succeeds against an old-key item even when a partial sweep left a newer-key item unreadable', async () => {
    // Regression for Important #1: a retry after a sweep that died partway through must not
    // reject the correct phrase just because the first item happens to already be under the
    // new metadata key.
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    const phrase = real.generateRecoveryKey(MASTER);
    document.body.dataset.phrase = phrase;
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    // No verifier saved for v1, simulates a new device.
    const oldKeyMetadata = await encryptMetadata(
      { name: 'a.jpg', contentType: 'image/jpeg', size: 1, contentId: 'c1' },
      keys.metadataEncryptionKey,
    );
    vi.mocked(listItems).mockResolvedValueOnce([
      {
        itemId: 'already-rotated',
        vaultId: 'v1',
        itemType: 'MEDIA',
        encryptedMetadata: new Uint8Array([9, 9, 9]), // already re-keyed by a prior partial sweep
        dekVersion: 2, // kekVersion + 1, under the NEW key, not readable with these keys
        createdAt: new Date(0),
        updatedAt: new Date(0),
        version: 1,
      },
      {
        itemId: 'still-old-key',
        vaultId: 'v1',
        itemType: 'MEDIA',
        encryptedMetadata: oldKeyMetadata,
        dekVersion: 1, // == kekVersion, still under the OLD key, the real proof candidate
        createdAt: new Date(0),
        updatedAt: new Date(0),
        version: 1,
      },
    ]);
    api.listAllVaults.mockResolvedValue([{ vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', createdAt: new Date(0), updatedAt: new Date(0) }]);
    api.getVault.mockResolvedValue({
      vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', rotationLockedAt: null,
      encryptedName: null, verifier: null, pendingVaultSalt: null, pendingVerifier: null,
    });
    api.updateVaultRotation.mockImplementation(async (args: { action: string; newVaultSalt?: Uint8Array; newVerifier?: Uint8Array }) =>
      args.action === 'ACQUIRE'
        ? { rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, pendingVaultSalt: args.newVaultSalt ?? null, pendingVerifier: args.newVerifier ?? null }
        : { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null },
    );

    await renderProbe();
    await act(async () => {
      screen.getByText('recover-kit').click();
    });
    expect(document.title).toMatch(/^recovered:v1/);
    expect(api.updateVaultRotation).toHaveBeenCalledWith(expect.objectContaining({ action: 'ACQUIRE' }));
  });

  it('recovery meets a staged pair from an earlier attempt: start over goes PAUSE, ABANDON, re-ACQUIRE IDLE', async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    document.body.dataset.phrase = real.generateRecoveryKey(MASTER);
    const keys = deriveKeys(MASTER);
    const verifier = await createVerifier(keys.metadataEncryptionKey);
    localStorage.setItem('cortex_account', 'u1');
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    saveVerifier('v1', verifier);
    api.listAllVaults.mockResolvedValue([
      { vaultId: 'v1', vaultSalt: SALT, verifier: stringToBytes(verifier), kekVersion: 1, rotationState: 'PAUSED', createdAt: new Date(0), updatedAt: new Date(0) },
    ]);
    api.getVault.mockResolvedValue({
      vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'PAUSED', rotationLockedAt: 1700000000,
      encryptedName: null, verifier: stringToBytes(verifier), pendingVaultSalt: new Uint8Array(16).fill(3), pendingVerifier: null,
    });
    // The staged pair belongs to a password this user no longer knows.
    const stagedVerifier = await createVerifier(deriveKeys(new Uint8Array(32).fill(7)).metadataEncryptionKey);
    const staged = { pendingVaultSalt: new Uint8Array(16).fill(3), pendingVerifier: stringToBytes(stagedVerifier) };
    let abandoned = false;
    api.updateVaultRotation.mockImplementation(async (args: { action: string; newVaultSalt?: Uint8Array; newVerifier?: Uint8Array }) => {
      if (args.action === 'ACQUIRE') {
        return abandoned
          ? { rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000100, pendingVaultSalt: args.newVaultSalt ?? null, pendingVerifier: args.newVerifier ?? null }
          : { rotationState: 'IN_PROGRESS', rotationLockedAt: 1700000000, ...staged };
      }
      if (args.action === 'PAUSE') return { rotationState: 'PAUSED', rotationLockedAt: 1700000000, ...staged };
      if (args.action === 'ABANDON') {
        abandoned = true;
        return { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null };
      }
      return { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null };
    });
    const onStagedMismatch = vi.fn().mockResolvedValueOnce({ action: 'startOver' });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked'));
    const listAllVaultsCallsBeforeRecovery = api.listAllVaults.mock.calls.length;

    let result: { phrase: string; vaultId: string; name: string } | null = null;
    await act(async () => {
      result = await sessionRef.current!.recoverVault(document.body.dataset.phrase ?? '', 'newpw', undefined, undefined, onStagedMismatch);
    });

    expect(onStagedMismatch).toHaveBeenCalledWith(1700000000, undefined);
    expect(api.updateVaultRotation.mock.calls.map((c: unknown[]) => (c[0] as { action: string }).action)).toEqual([
      'ACQUIRE', 'PAUSE', 'ABANDON', 'ACQUIRE', 'RELEASE',
    ]);
    expect(api.updateVaultRotation.mock.calls[3][0]).toMatchObject({ action: 'ACQUIRE', expectedState: 'IDLE' });
    expect(result!.vaultId).toBe('v1');
    expect(result!.phrase.split(' ')).toHaveLength(24);
    expect(api.listAllVaults).toHaveBeenCalledTimes(listAllVaultsCallsBeforeRecovery);
    expect(storedRegistry().find((v) => v.vaultId === 'v1')).toMatchObject({ kekVersion: 2, rotationState: 'IDLE' });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
  });
});

describe('rotation with the staged pair', () => {
  // deriveVaultMasterKey is mocked (Argon2id is slow); map passwords to distinct masters so a
  // password typed at the resume dialog really does derive different keys. The salt is ignored.
  const MASTERS: Record<string, Uint8Array> = {
    newvaultpw: new Uint8Array(32).fill(6),
    staged: new Uint8Array(32).fill(7),
  };
  const STAGED_SALT = new Uint8Array(16).fill(3);
  const LOCKED_AT = 1700000000;
  const bogusItem: ItemData = {
    itemId: 'i1',
    vaultId: 'v1',
    itemType: 'MEDIA',
    encryptedMetadata: new Uint8Array([1, 2, 3]), // undecryptable: makes rotateItems throw
    wrappedDek: new Uint8Array(97),
    dekVersion: 1,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    version: 1,
  };

  beforeEach(() => {
    vi.mocked(deriveVaultMasterKey).mockImplementation(async (password: string) => MASTERS[password] ?? MASTER);
  });

  // A vault this device unlocked before (local verifier blob) that the server also lists.
  async function seedVault(record: Record<string, unknown> = {}) {
    const keys = deriveKeys(MASTER);
    const verifier = await createVerifier(keys.metadataEncryptionKey);
    const encryptedName = await encryptCollectionName('Holiday', keys.metadataEncryptionKey);
    localStorage.setItem('cortex_account', 'u1');
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Holiday', kekVersion: 1, rotationState: 'IDLE' }]));
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    saveVerifier('v1', verifier);
    api.listAllVaults.mockResolvedValue([
      { vaultId: 'v1', vaultSalt: SALT, verifier: stringToBytes(verifier), encryptedName, kekVersion: 1, rotationState: 'IDLE', createdAt: new Date(0), updatedAt: new Date(0) },
    ]);
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
      encryptedName,
      verifier: stringToBytes(verifier),
      pendingVaultSalt: null,
      pendingVerifier: null,
      ...record,
    });
    return keys;
  }

  // Server that accepts this attempt's pair: ACQUIRE echoes the salt and verifier it was sent.
  function echoRotation() {
    api.updateVaultRotation.mockImplementation(async (args: { action: string; newVaultSalt?: Uint8Array; newVerifier?: Uint8Array }) =>
      args.action === 'ACQUIRE'
        ? { rotationState: 'IN_PROGRESS', rotationLockedAt: LOCKED_AT, pendingVaultSalt: args.newVaultSalt ?? null, pendingVerifier: args.newVerifier ?? null }
        : { rotationState: args.action === 'PAUSE' ? 'PAUSED' : 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null },
    );
  }

  // Server holding an earlier attempt's pair: ACQUIRE returns it until ABANDON succeeds, after
  // which ACQUIRE echoes the caller's pair. `abandon` is the ABANDON outcome.
  function stagedRotation(stagedVerifier: string, abandon: 'ok' | Error = 'ok') {
    let abandoned = false;
    const staged = { pendingVaultSalt: STAGED_SALT, pendingVerifier: stringToBytes(stagedVerifier) };
    api.updateVaultRotation.mockImplementation(async (args: { action: string; newVaultSalt?: Uint8Array; newVerifier?: Uint8Array }) => {
      switch (args.action) {
        case 'ACQUIRE':
          return abandoned
            ? { rotationState: 'IN_PROGRESS', rotationLockedAt: LOCKED_AT + 100, pendingVaultSalt: args.newVaultSalt ?? null, pendingVerifier: args.newVerifier ?? null }
            : { rotationState: 'IN_PROGRESS', rotationLockedAt: LOCKED_AT, ...staged };
        case 'PAUSE':
          return { rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT, ...staged };
        case 'ABANDON':
          if (abandon !== 'ok') throw abandon;
          abandoned = true;
          return { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null };
        default:
          return { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null };
      }
    });
  }

  async function mount() {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked'));
  }

  // Cast, not inferred: whichever fields a given test actually reads off a call are always
  // present for that action (ACQUIRE always carries newVaultSalt/newVerifier when this attempt
  // sent them, RELEASE always carries newEncryptedName); tests that check absence use
  // toBeUndefined(), which does not need the stricter optional type.
  type RotationCallArgs = {
    action: string;
    expectedState: string;
    kekVersion?: number;
    newVaultSalt: Uint8Array;
    newVerifier: Uint8Array;
    newEncryptedName: Uint8Array;
  };
  const rotationCalls = () => api.updateVaultRotation.mock.calls.map((c: unknown[]) => c[0] as RotationCallArgs);
  const callFor = (action: string, nth = 0) => rotationCalls().filter((a) => a.action === action)[nth];
  const registryEntry = () => (JSON.parse(localStorage.getItem('cortex_vaults:u1') ?? '[]') as { vaultId: string; kekVersion?: number; rotationState?: string; encryptedName?: string; name: string }[]).find((v) => v.vaultId === 'v1');

  it('happy path: ACQUIRE stages a fresh pair, RELEASE carries the name under the new keys and no verifier', async () => {
    await seedVault();
    echoRotation();
    await mount();

    let phrase = '';
    await act(async () => {
      phrase = await sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw');
    });

    expect(phrase.split(' ')).toHaveLength(24);
    const acquire = callFor('ACQUIRE');
    expect(acquire.expectedState).toBe('IDLE');
    expect(acquire.newVaultSalt).toBeInstanceOf(Uint8Array);
    expect(acquire.newVaultSalt.length).toBe(16);
    const keysNew = deriveKeys(MASTERS.newvaultpw);
    const sentVerifier = bytesToString(acquire.newVerifier);
    expect(checkVerifier(sentVerifier, keysNew.metadataEncryptionKey)).toBe(true);

    const release = callFor('RELEASE');
    expect(release).toMatchObject({ expectedState: 'IN_PROGRESS', kekVersion: 2 });
    expect(release.newVerifier).toBeUndefined();
    expect(release.newVaultSalt).toBeUndefined();
    expect(decryptCollectionName(release.newEncryptedName, keysNew.metadataEncryptionKey)).toBe('Holiday');

    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'RELEASE']);
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBe(sentVerifier);
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', keysNew);
    expect(registryEntry()).toMatchObject({ kekVersion: 2, rotationState: 'IDLE', name: 'Holiday' });
    expect(typeof registryEntry()?.encryptedName).toBe('string');
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('resume with the same password: uses the staged pair and finishes without the dialog', async () => {
    await seedVault({ rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT });
    const stagedKeys = deriveKeys(MASTERS.newvaultpw);
    const stagedVerifier = await createVerifier(stagedKeys.metadataEncryptionKey);
    stagedRotation(stagedVerifier);
    const onStagedMismatch = vi.fn();
    await mount();

    await act(async () => {
      await sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch);
    });

    expect(onStagedMismatch).not.toHaveBeenCalled();
    expect(callFor('ACQUIRE').expectedState).toBe('PAUSED');
    // The staged verifier, not the one this attempt generated, is what gets committed locally.
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBe(stagedVerifier);
    expect(decryptCollectionName(callFor('RELEASE').newEncryptedName, stagedKeys.metadataEncryptionKey)).toBe('Holiday');
    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'RELEASE']);
  });

  it('PAUSE on failure: a sweep error pauses on the server, marks the registry PAUSED and raises the banner', async () => {
    await seedVault();
    echoRotation();
    vi.mocked(listAllItems).mockResolvedValueOnce([bogusItem]);
    await mount();

    await act(async () => {
      await expect(sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw')).rejects.toThrow(/ciphertext/i);
    });

    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'PAUSE']);
    expect(callFor('PAUSE').expectedState).toBe('IN_PROGRESS');
    expect(registryEntry()).toMatchObject({ rotationState: 'PAUSED' });
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
    expect(localStorage.getItem('cortex_vault_verifier_v1')).not.toBeNull();
    expect(vi.mocked(storeKeys)).not.toHaveBeenCalled();
  });

  it('collection sweep sends metadataVersion: target and expectedMetadataVersion: current', async () => {
    const keysOld = await seedVault();
    echoRotation();
    const col: CollectionData = {
      collectionId: 'c1',
      vaultId: 'v1',
      encryptedMetadata: await encryptCollectionName('Trips', keysOld.metadataEncryptionKey),
      itemCount: 0,
      createdAt: new Date(0),
      updatedAt: new Date(0),
    };
    vi.mocked(listAllCollections).mockResolvedValueOnce([col]);
    await mount();

    await act(async () => {
      await sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw');
    });

    expect(vi.mocked(listAllCollections)).toHaveBeenCalledWith('v1');
    expect(vi.mocked(updateCollection)).toHaveBeenCalledTimes(1);
    const [id, vaultId, bytes, version, expected] = vi.mocked(updateCollection).mock.calls[0];
    expect([id, vaultId, version, expected]).toEqual(['c1', 'v1', 2, 1]);
    expect(decryptCollectionName(bytes, deriveKeys(MASTERS.newvaultpw).metadataEncryptionKey)).toBe('Trips');
  });

  it('mismatch then finish: the dialog password opens the staged pair; a wrong one re-prompts with the error', async () => {
    await seedVault({ rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT });
    const stagedKeys = deriveKeys(MASTERS.staged);
    const stagedVerifier = await createVerifier(stagedKeys.metadataEncryptionKey);
    stagedRotation(stagedVerifier);
    const onStagedMismatch = vi
      .fn()
      .mockResolvedValueOnce({ action: 'finish', password: 'nope' })
      .mockResolvedValueOnce({ action: 'finish', password: 'staged' });
    await mount();

    let phrase = '';
    await act(async () => {
      phrase = await sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch);
    });

    expect(phrase.split(' ')).toHaveLength(24);
    expect(onStagedMismatch).toHaveBeenCalledTimes(2);
    expect(onStagedMismatch).toHaveBeenNthCalledWith(1, LOCKED_AT, undefined);
    expect(onStagedMismatch).toHaveBeenNthCalledWith(2, LOCKED_AT, WRONG_VAULT_PASSWORD);
    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'RELEASE']);
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBe(stagedVerifier);
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', stagedKeys);
    expect(decryptCollectionName(callFor('RELEASE').newEncryptedName, stagedKeys.metadataEncryptionKey)).toBe('Holiday');
  });

  it('mismatch then start over: PAUSE, ABANDON, then re-ACQUIRE with expectedState IDLE and this attempt\'s pair', async () => {
    await seedVault({ rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT });
    const stagedVerifier = await createVerifier(deriveKeys(MASTERS.staged).metadataEncryptionKey);
    stagedRotation(stagedVerifier);
    const onStagedMismatch = vi.fn().mockResolvedValueOnce({ action: 'startOver' });
    await mount();

    let phrase = '';
    await act(async () => {
      phrase = await sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch);
    });

    expect(phrase.split(' ')).toHaveLength(24);
    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'PAUSE', 'ABANDON', 'ACQUIRE', 'RELEASE']);
    expect(callFor('ACQUIRE', 0).expectedState).toBe('PAUSED');
    expect(callFor('PAUSE').expectedState).toBe('IN_PROGRESS');
    expect(callFor('ABANDON').expectedState).toBe('PAUSED');
    expect(callFor('ACQUIRE', 1).expectedState).toBe('IDLE');
    // Both ACQUIREs carry the same fresh pair; the second one is the one the server accepts.
    expect(Array.from(callFor('ACQUIRE', 1).newVaultSalt)).toEqual(Array.from(callFor('ACQUIRE', 0).newVaultSalt));
    const keysNew = deriveKeys(MASTERS.newvaultpw);
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBe(bytesToString(callFor('ACQUIRE', 1).newVerifier));
    expect(vi.mocked(storeKeys)).toHaveBeenCalledWith('v1', keysNew);
    expect(registryEntry()).toMatchObject({ kekVersion: 2, rotationState: 'IDLE' });
  });

  it('start over when files were already re-keyed: ABANDON 409 with the re-keyed text becomes REKEYED_ERROR', async () => {
    await seedVault({ rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT });
    const stagedVerifier = await createVerifier(deriveKeys(MASTERS.staged).metadataEncryptionKey);
    stagedRotation(stagedVerifier, new Error('Some files were already re-keyed; finish the password change with the new password'));
    const onStagedMismatch = vi.fn().mockResolvedValueOnce({ action: 'startOver' });
    await mount();

    await act(async () => {
      await expect(
        sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch),
      ).rejects.toThrow(REKEYED_ERROR);
    });

    // ABANDON is never retried and the lock was already released by PAUSE: no second PAUSE, no re-ACQUIRE.
    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'PAUSE', 'ABANDON']);
    expect(registryEntry()).toMatchObject({ rotationState: 'PAUSED' });
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
  });

  it('start over when another device holds the lock: any other ABANDON error surfaces as the server message', async () => {
    await seedVault({ rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT });
    const stagedVerifier = await createVerifier(deriveKeys(MASTERS.staged).metadataEncryptionKey);
    stagedRotation(stagedVerifier, new Error('A vault password change is already in progress on another device'));
    const onStagedMismatch = vi.fn().mockResolvedValueOnce({ action: 'startOver' });
    await mount();

    await act(async () => {
      await expect(
        sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch),
      ).rejects.toThrow('A vault password change is already in progress on another device');
    });

    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'PAUSE', 'ABANDON']);
  });

  it('start over succeeds, then the re-ACQUIRE throws: no second PAUSE (lock already released) and the registry lands IDLE, not PAUSED', async () => {
    await seedVault({ rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT });
    const stagedVerifier = await createVerifier(deriveKeys(MASTERS.staged).metadataEncryptionKey);
    const staged = { pendingVaultSalt: STAGED_SALT, pendingVerifier: stringToBytes(stagedVerifier) };
    let abandoned = false;
    api.updateVaultRotation.mockImplementation(async (args: { action: string }) => {
      switch (args.action) {
        case 'ACQUIRE':
          // After ABANDON, this attempt no longer holds the lock; the re-ACQUIRE fails
          // for an unrelated reason (e.g. a network blip), with the server left IDLE.
          if (abandoned) throw new Error('network down');
          return { rotationState: 'IN_PROGRESS', rotationLockedAt: LOCKED_AT, ...staged };
        case 'PAUSE':
          return { rotationState: 'PAUSED', rotationLockedAt: LOCKED_AT, ...staged };
        case 'ABANDON':
          abandoned = true;
          return { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null };
        default:
          return { rotationState: 'IDLE', rotationLockedAt: null, pendingVaultSalt: null, pendingVerifier: null };
      }
    });
    const onStagedMismatch = vi.fn().mockResolvedValueOnce({ action: 'startOver' });
    await mount();

    await act(async () => {
      await expect(
        sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch),
      ).rejects.toThrow('network down');
    });

    // Exactly one PAUSE (Start over's own, before ABANDON) — the failed re-ACQUIRE sends no second one.
    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'PAUSE', 'ABANDON', 'ACQUIRE']);
    expect(registryEntry()).toMatchObject({ rotationState: 'IDLE' });
    // The server and the registry both say IDLE, so the Dashboard banner must not claim an
    // interrupted rotation for the rest of the session (final review M2).
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('mismatch then cancel: throws CANCELLED_ERROR and pauses the rotation', async () => {
    await seedVault({ rotationState: 'IDLE' });
    const stagedVerifier = await createVerifier(deriveKeys(MASTERS.staged).metadataEncryptionKey);
    stagedRotation(stagedVerifier);
    const onStagedMismatch = vi.fn().mockResolvedValueOnce({ action: 'cancel' });
    await mount();

    await act(async () => {
      await expect(
        sessionRef.current!.changeVaultPassword('vaultpw', 'newvaultpw', undefined, onStagedMismatch),
      ).rejects.toThrow(CANCELLED_ERROR);
    });

    expect(rotationCalls().map((a: { action: string }) => a.action)).toEqual(['ACQUIRE', 'PAUSE']);
    expect(callFor('PAUSE').expectedState).toBe('IN_PROGRESS');
    expect(registryEntry()).toMatchObject({ rotationState: 'PAUSED' });
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
    expect(vi.mocked(storeKeys)).not.toHaveBeenCalled();
  });
});

describe('deleteVault', () => {
  const serverVault = (vaultId: string, verifier?: string) => ({
    vaultId,
    vaultSalt: SALT,
    kekVersion: 1,
    rotationState: 'IDLE' as const,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    ...(verifier ? { verifier: new TextEncoder().encode(verifier) } : {}),
  });
  const batch = (deletedItems: number, deletionState: 'DELETING' | 'DELETED') => ({
    deletionState,
    deletedItems,
    deletedCollections: 0,
    deletedShares: 0,
  });
  // Render and wait for the gate (ListVaults sync) so the server salt/verifier are in state.
  async function mount(server: ReturnType<typeof serverVault>[]) {
    api.listAllVaults.mockResolvedValue(server);
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked'));
  }

  beforeEach(() => {
    localStorage.setItem('cortex_account', 'u1');
    localStorage.setItem(
      'cortex_vaults:u1',
      JSON.stringify([
        { vaultId: 'v1', name: 'Personal', lastOpened: 2 },
        { vaultId: 'v2', name: 'Work', lastOpened: 1 },
      ]),
    );
    localStorage.setItem('cortex_vault_id:u1', 'v1');
    localStorage.setItem('cortex_welcome_done:v1', '1');
    delete document.body.dataset.deleted;
  });

  it('loops until DELETED, reports progress, purges the vault locally and hands over to the most recently opened vault', async () => {
    const good = await createVerifier(deriveKeys(MASTER).metadataEncryptionKey);
    saveVerifier('v1', good);
    api.deleteVault.mockResolvedValueOnce(batch(2, 'DELETING')).mockResolvedValueOnce(batch(1, 'DELETED'));
    await mount([serverVault('v1', good), serverVault('v2', good)]);
    api.listAllVaults.mockResolvedValue([serverVault('v2', good)]); // the server no longer lists v1
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('deleted');
    expect(api.deleteVault).toHaveBeenCalledTimes(2);
    expect(api.deleteVault).toHaveBeenCalledWith('v1');
    expect(document.body.dataset.deleted).toBe('3');
    expect(clearKeys).toHaveBeenCalledWith('v1');
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBeNull();
    expect(localStorage.getItem('cortex_welcome_done:v1')).toBeNull();
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!).map((v: { vaultId: string }) => v.vaultId)).toEqual(['v2']);
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v2');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
    expect(screen.getByTestId('vaults')).toHaveTextContent('Work');
  });

  it('treats a 404 on a later call as success and leaves no active vault when none remain', async () => {
    const good = await createVerifier(deriveKeys(MASTER).metadataEncryptionKey);
    localStorage.setItem('cortex_vaults:u1', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    api.deleteVault
      .mockResolvedValueOnce(batch(5, 'DELETING'))
      .mockRejectedValueOnce(new ResourceNotFoundError({ message: 'Vault not found', $metadata: {} }));
    await mount([serverVault('v1', good)]);
    api.listAllVaults.mockResolvedValue([]);
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('deleted');
    expect(api.deleteVault).toHaveBeenCalledTimes(2);
    expect(document.body.dataset.deleted).toBe('5');
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!)).toEqual([]);
    expect(localStorage.getItem('cortex_vault_id:u1')).toBeNull();
    expect(screen.getByTestId('vaults').textContent).toBe('');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it('treats a 404 on the first call as an error: surfaces the message and purges nothing', async () => {
    // Spec §3.5 / §7: only a 404 on a later call means "already gone"; on the first call the
    // vault this device believes in does not exist server-side, which the user must see.
    const good = await createVerifier(deriveKeys(MASTER).metadataEncryptionKey);
    api.deleteVault.mockRejectedValueOnce(new ResourceNotFoundError({ message: 'Vault not found', $metadata: {} }));
    await mount([serverVault('v1', good), serverVault('v2', good)]);
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('Vault not found');
    expect(api.deleteVault).toHaveBeenCalledTimes(1);
    expect(clearKeys).not.toHaveBeenCalled();
    expect(localStorage.getItem('cortex_vault_verifier_v1')).toBeNull(); // never saved: nothing to purge
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!)).toHaveLength(2);
    expect(screen.getByTestId('vaults')).toHaveTextContent('Personal,Work');
  });

  it('stops on a 409 with the server message and purges nothing', async () => {
    const good = await createVerifier(deriveKeys(MASTER).metadataEncryptionKey);
    api.deleteVault.mockRejectedValueOnce(
      new ConflictError({
        message: 'A vault password change is in progress; wait for it to finish or pause it first',
        $metadata: {},
      }),
    );
    await mount([serverVault('v1', good), serverVault('v2', good)]);
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('A vault password change is in progress; wait for it to finish or pause it first');
    expect(api.deleteVault).toHaveBeenCalledTimes(1);
    expect(clearKeys).not.toHaveBeenCalled();
    expect(localStorage.getItem('cortex_vault_id:u1')).toBe('v1');
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!)).toHaveLength(2);
  });

  it('refuses when neither the server nor this device has a verifier, and makes no call', async () => {
    await mount([serverVault('v1'), serverVault('v2')]);
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('Unlock this vault once on a device that knows its password');
    expect(api.deleteVault).not.toHaveBeenCalled();
    expect(api.getVaultSalt).not.toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!)).toHaveLength(2);
  });

  it('rejects a wrong password against the server verifier and makes no call', async () => {
    const other = await createVerifier(deriveKeys(new Uint8Array(32).fill(42)).metadataEncryptionKey);
    await mount([serverVault('v1', other), serverVault('v2', other)]);
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('Incorrect vault password');
    expect(api.deleteVault).not.toHaveBeenCalled();
  });

  it('does not resurrect the deleted vault via a stale post-delete ListVaults read', async () => {
    const good = await createVerifier(deriveKeys(MASTER).metadataEncryptionKey);
    saveVerifier('v1', good);
    api.deleteVault.mockResolvedValueOnce(batch(1, 'DELETED'));
    await mount([serverVault('v1', good), serverVault('v2', good)]);
    // Deliberately leave listAllVaults resolving to the stale, pre-delete list (it is an
    // eventually-consistent DynamoDB query): a real read racing the delete could still
    // include v1 immediately afterwards. No re-sync should happen at all.
    const callsBeforeDelete = api.listAllVaults.mock.calls.length;
    await act(async () => {
      screen.getByText('delete-v1').click();
    });
    expect(document.title).toBe('deleted');
    expect(api.listAllVaults.mock.calls.length).toBe(callsBeforeDelete);
    expect(JSON.parse(localStorage.getItem('cortex_vaults:u1')!).map((v: { vaultId: string }) => v.vaultId)).toEqual(['v2']);
  });
});
