import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { deriveKeys, retrieveKeys } from '@cortex/encryption';
import { createVerifier, saveVerifier } from '../vault/verifier';
import { listItems } from '../api/items';
import { listCollections } from '../api/collections';
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
vi.mock('../api/collections', () => ({ listCollections: vi.fn(async () => []) }));

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

import { SessionProvider, useSession } from './SessionContext';

function Probe() {
  const s = useSession();
  return (
    <div>
      <span data-testid="status">{s.status}</span>
      <span data-testid="rotation-interrupted">{String(s.rotationInterrupted)}</span>
      <span data-testid="types">
        {typeof s.changeVaultPassword},{typeof s.rotationInterrupted}
      </span>
      <button onClick={() => s.setupVault('vaultpw').then((r) => (document.title = r))}>setup</button>
      <button onClick={() => s.unlockVault('vaultpw').catch((e) => (document.title = e.message))}>
        unlock
      </button>
      <button onClick={() => s.changeVaultPassword('vaultpw', 'newvaultpw').catch(() => {})}>
        change
      </button>
      <span data-testid="vaults">{s.vaults.map((v) => v.name).join(',')}</span>
      <span data-testid="active">{s.activeVault?.name ?? ''}</span>
      <span data-testid="version">{s.vaultVersion}</span>
      <button onClick={() => s.setupVault('vaultpw', 'Family').then((r) => (document.title = r))}>setup-family</button>
      <button onClick={() => s.switchVault('v9').then((r) => (document.title = r))}>switch-v9</button>
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
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  document.title = '';
});

describe('SessionContext vault', () => {
  it('setupVault creates a vault, stores keys, unlocks, returns recovery phrase', async () => {
    api.createVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT });
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('setup');
    await act(async () => {
      screen.getByText('setup').click();
    });
    expect(api.createVault).toHaveBeenCalled();
    expect(localStorage.getItem('cortex_vault_id')).toBe('v1');
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(document.title.split(' ')).toHaveLength(24);
  });

  it('unlockVault with the correct password unlocks', async () => {
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vault_id', 'v1');
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVaultSalt.mockResolvedValue(SALT);
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IDLE',
      rotationLockedAt: null,
    });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('unlock');
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('false');
  });

  it('unlockVault sets rotationInterrupted when GetVault reports a non-IDLE rotation state', async () => {
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vault_id', 'v1');
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVaultSalt.mockResolvedValue(SALT);
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
    });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('unlock');
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(screen.getByTestId('rotation-interrupted')).toHaveTextContent('true');
  });

  it('unlockVault with the wrong password throws and stays locked', async () => {
    const wrong = deriveKeys(new Uint8Array(32).fill(42));
    localStorage.setItem('cortex_vault_id', 'v1');
    saveVerifier('v1', await createVerifier(wrong.metadataEncryptionKey));
    api.getVaultSalt.mockResolvedValue(SALT);

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('unlock');
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(document.title).toBe('Incorrect vault password');
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it('unlockVault hard-fails (does not unlock) when the verifier is missing', async () => {
    localStorage.setItem('cortex_vault_id', 'v1'); // vault id present, but no verifier blob
    api.getVaultSalt.mockResolvedValue(SALT);

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('unlock');
    await act(async () => {
      screen.getByText('unlock').click();
    });
    expect(document.title).toMatch(/verifier missing/i);
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });
});

describe('changeVaultPassword', () => {
  it('is exposed on SessionValue as a function, alongside rotationInterrupted as a boolean', async () => {
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    expect(await screen.findByTestId('types')).toHaveTextContent('function,boolean');
    // Full integration coverage (wrong-password fast-fail, sweep, phrase gate) lives in
    // ChangeVaultPassword.test.tsx (Task 9) — this is just the wiring smoke test.
    expect(api.getVault).not.toHaveBeenCalled();
  });

  it('resuming an interrupted rotation ACQUIREs with the vault\'s actual rotationState, not a hardcoded IDLE', async () => {
    // Regression test: GetVault reporting IN_PROGRESS (a crashed mid-sweep attempt)
    // must NOT cause the ACQUIRE call to assert expectedState: 'IDLE' — the backend's
    // conditional write would then always throw ConflictError, since the vault is
    // genuinely IN_PROGRESS and the 7-day staleness window hasn't elapsed. The resume
    // path must ACQUIRE using the vault's own current state.
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vault_id', 'v1');
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVault.mockResolvedValue({
      vaultId: 'v1',
      vaultSalt: SALT,
      kekVersion: 1,
      rotationState: 'IN_PROGRESS',
      rotationLockedAt: 1700000000,
    });
    api.updateVaultRotation.mockResolvedValue({ rotationState: 'IN_PROGRESS', rotationLockedAt: Date.now() });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('change');
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
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('setup-family');
    await act(async () => {
      screen.getByText('setup-family').click();
    });
    expect(screen.getByTestId('vaults')).toHaveTextContent('Family');
    expect(screen.getByTestId('active')).toHaveTextContent('Family');
    expect(localStorage.getItem('cortex_vault_id')).toBe('v2');
  });

  it('switchVault reports locked when that vault has no keys on this device', async () => {
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id', 'v1');
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('switch-v9');
    await act(async () => {
      screen.getByText('switch-v9').click();
    });
    expect(document.title).toBe('locked');
    expect(localStorage.getItem('cortex_vault_id')).toBe('v1');
  });

  it('switchVault unlocks and activates when keys exist on this device', async () => {
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id', 'v1');
    (retrieveKeys as Mock).mockResolvedValueOnce({
      keyEncryptionKey: new Uint8Array(32),
      metadataEncryptionKey: new Uint8Array(32),
    } as never);
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('switch-v9');
    const versionBefore = Number(screen.getByTestId('version').textContent);
    await act(async () => {
      screen.getByText('switch-v9').click();
    });
    expect(document.title).toBe('unlocked');
    expect(localStorage.getItem('cortex_vault_id')).toBe('v9');
    expect(screen.getByTestId('active')).toHaveTextContent('Work');
    expect(Number(screen.getByTestId('version').textContent)).toBe(versionBefore + 1);
  });

  it('switchVault resolves locked (not a throw) when retrieveKeys rejects on a storage error', async () => {
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }, { vaultId: 'v9', name: 'Work' }]));
    localStorage.setItem('cortex_vault_id', 'v1');
    (retrieveKeys as Mock).mockRejectedValueOnce(new Error('Failed to retrieve keys: IndexedDB unavailable'));
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('switch-v9');
    await act(async () => {
      screen.getByText('switch-v9').click();
    });
    expect(document.title).toBe('locked');
    expect(localStorage.getItem('cortex_vault_id')).toBe('v1');
  });
});

describe('recoverVault', () => {
  it('re-secures the vault the phrase opens and unlocks it', async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    document.body.dataset.phrase = real.generateRecoveryKey(MASTER);
    const keys = deriveKeys(MASTER);
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    saveVerifier('v1', await createVerifier(keys.metadataEncryptionKey));
    api.getVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', rotationLockedAt: null });
    api.updateVaultRotation.mockResolvedValue({ rotationState: 'IDLE', rotationLockedAt: null });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('recover');
    await act(async () => {
      screen.getByText('recover').click();
    });
    expect(document.title).toBe('recovered:v1:24');
    expect(screen.getByTestId('status')).toHaveTextContent('unlocked');
    expect(api.updateVaultRotation).toHaveBeenCalledWith(expect.objectContaining({ action: 'RELEASE', kekVersion: 2 }));
    expect(localStorage.getItem('cortex_vault_id')).toBe('v1');
  });

  it('rejects with the generic message when the phrase opens nothing here', async () => {
    document.body.dataset.phrase = 'alpha bravo charlie';
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('recover');
    await act(async () => {
      screen.getByText('recover').click();
    });
    expect(document.title).toMatch(/don't open a vault on this device/);
    expect(screen.getByTestId('status')).toHaveTextContent('signedInVaultLocked');
  });

  it("new device: a wrong phrase against a vault with a collection throws PHRASE_ERROR before any rotation write", async () => {
    const real = await vi.importActual<typeof import('@cortex/encryption')>('@cortex/encryption');
    document.body.dataset.phrase = real.generateRecoveryKey(new Uint8Array(32).fill(7));
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    // No verifier saved for v1 — simulates a new device that has never opened this vault.
    vi.mocked(listItems).mockResolvedValueOnce([]);
    vi.mocked(listCollections).mockResolvedValueOnce([
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

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('recover-kit');
    await act(async () => {
      screen.getByText('recover-kit').click();
    });
    expect(document.title).toMatch(/don't open a vault on this device/);
    expect(vi.mocked(listCollections)).toHaveBeenCalledWith('v1');
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
    localStorage.setItem('cortex_vaults', JSON.stringify([{ vaultId: 'v1', name: 'Personal' }]));
    // No verifier saved for v1 — simulates a new device.
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
        dekVersion: 2, // kekVersion + 1 — under the NEW key, not readable with these keys
        createdAt: new Date(0),
        updatedAt: new Date(0),
        version: 1,
      },
      {
        itemId: 'still-old-key',
        vaultId: 'v1',
        itemType: 'MEDIA',
        encryptedMetadata: oldKeyMetadata,
        dekVersion: 1, // == kekVersion — still under the OLD key, the real proof candidate
        createdAt: new Date(0),
        updatedAt: new Date(0),
        version: 1,
      },
    ]);
    api.getVault.mockResolvedValue({ vaultId: 'v1', vaultSalt: SALT, kekVersion: 1, rotationState: 'IDLE', rotationLockedAt: null });
    api.updateVaultRotation.mockResolvedValue({ rotationState: 'IDLE', rotationLockedAt: null });

    render(
      <SessionProvider>
        <Probe />
      </SessionProvider>,
    );
    await screen.findByText('recover-kit');
    await act(async () => {
      screen.getByText('recover-kit').click();
    });
    expect(document.title).toMatch(/^recovered:v1/);
    expect(api.updateVaultRotation).toHaveBeenCalledWith(expect.objectContaining({ action: 'ACQUIRE' }));
  });
});
