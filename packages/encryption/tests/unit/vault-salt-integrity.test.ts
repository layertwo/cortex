import { hmac } from '@noble/hashes/hmac';
import { sha256 } from '@noble/hashes/sha2';
import {
  computeSaltHmac,
  verifySaltHmac,
  bindSaltHmac,
  resetSaltHmac,
  getStoredSaltHmac,
  SaltIntegrityError,
} from '../../src/lib/vault-salt-integrity';
import {
  storeSaltHmacRecord,
  retrieveSaltHmacRecord,
  clearSaltHmacRecord,
  type KeyStorageConfig,
  DEFAULT_CONFIG,
} from '../../src/lib/key-storage';

// ---------------------------------------------------------------------------
// Storage config shared across describe blocks
// ---------------------------------------------------------------------------

const FALLBACK_CONFIG: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };

// Minimal localStorage mock needed so that the key-storage fallback path works
// in this test file (vault-salt-integrity.test.ts is loaded independently of
// key-storage-secure.test.ts which sets up the mock for its own suite).
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

// ---------------------------------------------------------------------------
// computeSaltHmac
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// verifySaltHmac
// ---------------------------------------------------------------------------

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
    expect(verifySaltHmac(saltHmacKey, tampered, new Uint8Array(32))).toBe(false);
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

  it('returns false (not throws) when saltHmacKey has wrong length', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    expect(() => verifySaltHmac(new Uint8Array(16), salt, mac)).not.toThrow();
    expect(verifySaltHmac(new Uint8Array(16), salt, mac)).toBe(false);
  });

  it('returns false (not throws) when salt has wrong length', () => {
    const mac = computeSaltHmac(saltHmacKey, salt);
    expect(() => verifySaltHmac(saltHmacKey, new Uint8Array(8), mac)).not.toThrow();
    expect(verifySaltHmac(saltHmacKey, new Uint8Array(8), mac)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// bindSaltHmac
// ---------------------------------------------------------------------------

describe('bindSaltHmac', () => {
  afterEach(async () => {
    // Clean up any records written during the test
    await clearSaltHmacRecord('vault-bind-1', FALLBACK_CONFIG);
    await clearSaltHmacRecord('vault-bind-already-bound', FALLBACK_CONFIG);
  });

  it('persists the HMAC when no prior binding exists', async () => {
    const vaultId = 'vault-bind-1';
    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);

    await bindSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG });

    const retrieved = await getStoredSaltHmac(vaultId, FALLBACK_CONFIG);
    expect(retrieved).not.toBeNull();
    expect(verifySaltHmac(saltHmacKey, salt, retrieved!)).toBe(true);
  });

  it('throws ALREADY_BOUND when a binding already exists', async () => {
    const vaultId = 'vault-bind-already-bound';
    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);

    await bindSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG });

    await expect(
      bindSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG })
    ).rejects.toMatchObject({
      name: 'SaltIntegrityError',
      code: 'ALREADY_BOUND',
    });
  });
});

// ---------------------------------------------------------------------------
// resetSaltHmac
// ---------------------------------------------------------------------------

describe('resetSaltHmac', () => {
  afterEach(async () => {
    await clearSaltHmacRecord('vault-reset-overwrite', FALLBACK_CONFIG);
    await clearSaltHmacRecord('vault-reset-new', FALLBACK_CONFIG);
  });

  it('overwrites an existing binding silently', async () => {
    const vaultId = 'vault-reset-overwrite';
    const saltHmacKey1 = new Uint8Array(32).fill(0xab);
    const salt1 = new Uint8Array(16).fill(0xcd);
    const saltHmacKey2 = new Uint8Array(32).fill(0x11);
    const salt2 = new Uint8Array(16).fill(0x22);

    await bindSaltHmac({ vaultId, saltHmacKey: saltHmacKey1, salt: salt1, config: FALLBACK_CONFIG });
    await resetSaltHmac({ vaultId, saltHmacKey: saltHmacKey2, salt: salt2, config: FALLBACK_CONFIG });

    const retrieved = await getStoredSaltHmac(vaultId, FALLBACK_CONFIG);
    expect(retrieved).not.toBeNull();
    // The stored value should reflect the second call (key2 / salt2)
    expect(verifySaltHmac(saltHmacKey2, salt2, retrieved!)).toBe(true);
    // And NOT the first call
    expect(verifySaltHmac(saltHmacKey1, salt1, retrieved!)).toBe(false);
  });

  it('succeeds when no prior binding exists', async () => {
    const vaultId = 'vault-reset-new';
    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);

    // Should not throw even though there is no existing record
    await expect(
      resetSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG })
    ).resolves.not.toThrow();

    const retrieved = await getStoredSaltHmac(vaultId, FALLBACK_CONFIG);
    expect(retrieved).not.toBeNull();
    expect(verifySaltHmac(saltHmacKey, salt, retrieved!)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// getStoredSaltHmac
// ---------------------------------------------------------------------------

describe('getStoredSaltHmac', () => {
  afterEach(async () => {
    await clearSaltHmacRecord('vault-get-present', FALLBACK_CONFIG);
  });

  it('returns null when no record exists', async () => {
    const result = await getStoredSaltHmac(
      'vault-get-' + Math.random(),
      FALLBACK_CONFIG
    );
    expect(result).toBeNull();
  });

  it('returns the bound HMAC after bindSaltHmac', async () => {
    const vaultId = 'vault-get-present';
    const saltHmacKey = new Uint8Array(32).fill(0xab);
    const salt = new Uint8Array(16).fill(0xcd);

    await bindSaltHmac({ vaultId, saltHmacKey, salt, config: FALLBACK_CONFIG });

    const result = await getStoredSaltHmac(vaultId, FALLBACK_CONFIG);
    expect(result).toBeInstanceOf(Uint8Array);
    expect(result).toHaveLength(32);
    expect(verifySaltHmac(saltHmacKey, salt, result!)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Modern IndexedDB path round-trip
// ---------------------------------------------------------------------------
// TODO: fake-indexeddb is not installed in this workspace.
// Add a real modern-path round-trip test once the dependency is added:
//   npm install --save-dev fake-indexeddb
// Then import 'fake-indexeddb/auto' at the top of this file and uncomment:
//
// describe('storeSaltHmacRecord + retrieveSaltHmacRecord — modern IndexedDB path', () => {
//   it('round-trips the saltHmac through real IndexedDB (no forceFallback)', async () => {
//     const vaultId = 'vault-idb-' + Math.random();
//     const mac = new Uint8Array(32).fill(0x11);
//     await storeSaltHmacRecord(vaultId, mac); // no config → modern path
//     const retrieved = await retrieveSaltHmacRecord(vaultId);
//     expect(retrieved).toBeInstanceOf(Uint8Array);
//     expect(Buffer.from(retrieved!).equals(Buffer.from(mac))).toBe(true);
//   });
// });

describe('storeSaltHmacRecord + retrieveSaltHmacRecord — modern IndexedDB path', () => {
  it.skip(
    'round-trips the saltHmac through real IndexedDB (no forceFallback) — ' +
      'TODO: deferred until fake-indexeddb is added as a dev dependency',
    () => { /* deferred */ }
  );
});
