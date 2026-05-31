import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';
import {
  computeSaltHmac,
  verifySaltHmac,
  bindSaltHmac,
  resetSaltHmac,
  SaltIntegrityError,
} from '../../src/lib/vault-salt-integrity';
import { storeKeys, retrieveKeys, type KeysToStore, DEFAULT_CONFIG, type KeyStorageConfig } from '../../src/lib/key-storage';

// ---------------------------------------------------------------------------
// Storage helpers shared across the new describe blocks
// ---------------------------------------------------------------------------

const FALLBACK_CONFIG: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };

function createTestBundle(): KeysToStore {
  return {
    dataEncryptionKey: new Uint8Array(32).fill(1),
    metadataEncryptionKey: new Uint8Array(32).fill(2),
    shareKeyDerivationKey: new Uint8Array(32).fill(3),
    notesEncryptionKey: new Uint8Array(32).fill(4),
    tasksEncryptionKey: new Uint8Array(32).fill(5),
    eventsEncryptionKey: new Uint8Array(32).fill(6),
    notificationEncryptionKey: new Uint8Array(32).fill(7),
    dateBucketEncryptionKey: new Uint8Array(32).fill(8),
  };
}

// Minimal localStorage mock needed so that key-storage fallback path works in
// this test file (vault-salt-integrity.test.ts is loaded independently of
// key-storage-secure.test.ts which already sets up the mock for its own suite).
if (typeof localStorage === 'undefined') {
  let store: Record<string, string> = {};
  const mockStorage = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() { return Object.keys(store).length; },
  };
  Object.defineProperty(global, 'localStorage', { value: mockStorage, writable: true });
}

describe('computeSaltHmac', () => {
  it('returns HMAC-SHA256(saltHmacKey, salt) as a 32-byte Uint8Array', () => {
    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);

    const result = computeSaltHmac(saltHmacKey, salt);
    const expected = hmac(sha256, saltHmacKey, salt);

    expect(result).toBeInstanceOf(Uint8Array);
    expect(result).toHaveLength(32);
    expect(Buffer.from(result).equals(Buffer.from(expected))).toBe(true);
  });

  it('rejects a saltHmacKey that is not 32 bytes', () => {
    expect(() => computeSaltHmac(new Uint8Array(16), new Uint8Array(16))).toThrow(
      /saltHmacKey must be 32 bytes/
    );
  });

  it('rejects a salt that is not 16 bytes', () => {
    expect(() => computeSaltHmac(new Uint8Array(32), new Uint8Array(8))).toThrow(
      /salt must be 16 bytes/
    );
  });
});

describe('verifySaltHmac', () => {
  const saltHmacKey = new Uint8Array(32).fill(0xab);
  const salt = new Uint8Array(16).fill(0xcd);

  it('returns true for an HMAC computed over the same salt with the same key', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    expect(verifySaltHmac(saltHmacKey, salt, mac)).toBe(true);
  });

  it('returns false for a tampered HMAC (single bit flipped)', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    const tampered = new Uint8Array(mac);
    tampered[0] ^= 0x01;
    expect(verifySaltHmac(saltHmacKey, salt, tampered)).toBe(false);
  });

  it('returns false when the salt has been replaced', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    const replacedSalt = new Uint8Array(16).fill(0xee);
    expect(verifySaltHmac(saltHmacKey, replacedSalt, mac)).toBe(false);
  });

  it('returns false when the stored HMAC is the wrong length', () => {
    expect(verifySaltHmac(saltHmacKey, salt, new Uint8Array(31))).toBe(false);
  });
});

describe('bindSaltHmac', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('computes the HMAC and persists it on the stored bundle', async () => {
    const vaultId = 'vault-bind-1';
    const bundle = createTestBundle();
    await storeKeys(vaultId, bundle, FALLBACK_CONFIG);

    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);
    await bindSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG });

    const retrieved = await retrieveKeys(vaultId, FALLBACK_CONFIG);
    expect(retrieved?.saltHmac).toBeDefined();
    expect(verifySaltHmac(saltHmacKey, salt, retrieved!.saltHmac!)).toBe(true);
  });

  it('throws SaltIntegrityError(NO_BUNDLE) if no bundle is stored for the vault', async () => {
    await expect(
      bindSaltHmac({
        vaultId: 'unknown-vault-' + Math.random(),
        saltHmacKey: new Uint8Array(32),
        salt: new Uint8Array(16),
        config: FALLBACK_CONFIG,
      })
    ).rejects.toMatchObject({
      name: 'SaltIntegrityError',
      code: 'NO_BUNDLE',
    });
  });
});

describe('resetSaltHmac', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('overwrites an existing stored saltHmac with a freshly-computed one', async () => {
    const vaultId = 'vault-reset-1';
    const staleHmac = new Uint8Array(32).fill(0x00);
    const bundle = createTestBundle();
    await storeKeys(vaultId, { ...bundle, saltHmac: staleHmac }, FALLBACK_CONFIG);

    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);
    await resetSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG });

    const retrieved = await retrieveKeys(vaultId, FALLBACK_CONFIG);
    expect(retrieved?.saltHmac).toBeDefined();
    expect(verifySaltHmac(saltHmacKey, salt, retrieved!.saltHmac!)).toBe(true);
    expect(Buffer.from(retrieved!.saltHmac!).equals(Buffer.from(staleHmac))).toBe(false);
  });
});
