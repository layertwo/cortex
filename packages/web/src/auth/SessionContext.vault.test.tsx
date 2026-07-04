import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { deriveKeys } from '@cortex/encryption';
import { createVerifier, saveVerifier } from '../vault/verifier';

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

// Real verifier + real deriveKeys/encrypt/decrypt; mock only the slow Argon2id step.
vi.mock('@cortex/encryption', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@cortex/encryption')>();
  return {
    ...actual,
    deriveVaultMasterKey: vi.fn(async () => MASTER),
    generateRecoveryKey: vi.fn(() => 'word '.repeat(24).trim()),
    storeKeys: vi.fn(async () => {}),
    clearKeys: vi.fn(async () => {}),
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
