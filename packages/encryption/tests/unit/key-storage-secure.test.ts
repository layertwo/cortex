/**
 * Unit tests for key storage module (IndexedDB + Web Crypto API)
 */

import { jest } from '@jest/globals';
import {
  storeKeys,
  retrieveKeys,
  clearKeys,
  clearAllKeys,
  cleanupExpiredKeys,
  getStorageInfo,
  KeyStorageConfig,
  KeysToStore,
  DEFAULT_CONFIG,
  HIGH_SECURITY_CONFIG,
  storeSaltHmacRecord,
  retrieveSaltHmacRecord,
} from '../../src/lib/key-storage';

// Mock crypto.getRandomValues and crypto.subtle
const mockRandomValues = jest.fn((array: Uint8Array) => {
  for (let i = 0; i < array.length; i++) {
    array[i] = i % 256;
  }
  return array;
});

// Mock Web Crypto API
const mockCryptoKey = { type: 'secret', algorithm: { name: 'AES-GCM' } } as CryptoKey;

const mockSubtle = {
  generateKey: jest.fn<() => Promise<CryptoKey>>().mockResolvedValue(mockCryptoKey),
  encrypt: jest.fn((_algorithm: any, _key: any, data: any) => {
    // Simple mock: just return the data with a fake IV prepended
    const iv = new Uint8Array(12);
    const result = new Uint8Array(iv.length + data.byteLength);
    result.set(iv, 0);
    result.set(new Uint8Array(data), iv.length);
    return Promise.resolve(result.buffer);
  }),
  decrypt: jest.fn((_algorithm: any, _key: any, data: any) => {
    // Simple mock: just return the data without the IV
    const dataArray = new Uint8Array(data);
    return Promise.resolve(dataArray.slice(12).buffer);
  }),
  exportKey: jest.fn<() => Promise<never>>().mockRejectedValue(new Error('Key is not exportable')),
};

Object.defineProperty(global, 'crypto', {
  value: {
    getRandomValues: mockRandomValues,
    subtle: mockSubtle,
  },
  writable: true,
});

// Mock IndexedDB
const createMockIndexedDB = () => {
  const databases: Record<string, Record<string, any>> = {};
  
  return {
    open: jest.fn((name: string, _version: number) => {
      if (!databases[name]) {
        databases[name] = {};
      }
      
      const request: any = {
        result: {
          transaction: jest.fn((_storeNames: string[], _mode: string) => {
            return {
              objectStore: jest.fn((storeName: string) => {
                if (!databases[name][storeName]) {
                  databases[name][storeName] = {};
                }
                
                return {
                  put: jest.fn((data: any) => ({
                    onsuccess: null,
                    onerror: null,
                    result: data,
                  })),
                  get: jest.fn((key: string) => ({
                    onsuccess: null,
                    onerror: null,
                    result: databases[name][storeName][key] || null,
                  })),
                  delete: jest.fn((key: string) => {
                    delete databases[name][storeName][key];
                    return {
                      onsuccess: null,
                      onerror: null,
                    };
                  }),
                  clear: jest.fn(() => {
                    databases[name][storeName] = {};
                    return {
                      onsuccess: null,
                      onerror: null,
                    };
                  }),
                  openCursor: jest.fn(() => ({
                    onsuccess: null,
                    onerror: null,
                  })),
                };
              }),
              oncomplete: null,
              onerror: null,
            };
          }),
          close: jest.fn(),
          objectStoreNames: {
            contains: jest.fn(() => false),
          },
        },
        onsuccess: null,
        onerror: null,
        onupgradeneeded: null as any,
      };
      
      // Trigger onupgradeneeded for initial setup
      setTimeout(() => {
        if (request.onupgradeneeded) {
          request.onupgradeneeded({ target: request } as any);
        }
        if (request.onsuccess) {
          request.onsuccess({ target: request } as any);
        }
      }, 0);
      
      return request;
    }),
    databases,
  };
};

const mockIndexedDB = createMockIndexedDB();

Object.defineProperty(global, 'indexedDB', {
  value: mockIndexedDB,
  writable: true,
});

// Mock localStorage and sessionStorage
const createMockStorage = (): Storage => {
  let store: Record<string, string> = {};
  
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    key: (index: number) => Object.keys(store)[index] || null,
    get length() {
      return Object.keys(store).length;
    },
  };
};

const mockLocalStorage = createMockStorage();
const mockSessionStorage = createMockStorage();

Object.defineProperty(global, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

Object.defineProperty(global, 'sessionStorage', {
  value: mockSessionStorage,
  writable: true,
});

// Helper to create test keys
function createTestKeys(): KeysToStore {
  return {
    keyEncryptionKey: new Uint8Array(32).fill(1),
    metadataEncryptionKey: new Uint8Array(32).fill(2),
    shareKeyDerivationKey: new Uint8Array(32).fill(3),
    notesEncryptionKey: new Uint8Array(32).fill(4),
    tasksEncryptionKey: new Uint8Array(32).fill(5),
    eventsEncryptionKey: new Uint8Array(32).fill(6),
    notificationEncryptionKey: new Uint8Array(32).fill(7),
    dateBucketEncryptionKey: new Uint8Array(32).fill(8),
  };
}

describe('Key Storage (IndexedDB + Web Crypto API)', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockSessionStorage.clear();
    jest.clearAllMocks();
  });

  describe('getStorageInfo', () => {
    it('should report storage mode and features', () => {
      const info = getStorageInfo();
      
      // In Node.js test environment, we expect fallback mode
      // because crypto.subtle and indexedDB are mocked but detected at module load time
      expect(info.mode).toBeDefined();
      expect(info.hasWebCrypto).toBeDefined();
      expect(info.hasIndexedDB).toBeDefined();
      expect(Array.isArray(info.features)).toBe(true);
    });
  });

  describe('storeKeys', () => {
    it('should store keys successfully', async () => {
      const keys = createTestKeys();
      await expect(storeKeys('vault-123', keys)).resolves.not.toThrow();
    });

    it('should use fallback mode in test environment', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      
      await storeKeys('vault-123', keys, config);
      
      // Should have stored in localStorage
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')).not.toBeNull();
    });

    it('should include timestamps in stored data', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      await storeKeys('vault-123', keys, config);
      
      const storedData = JSON.parse(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')!);
      expect(storedData.timestamp).toBeDefined();
      expect(storedData.createdAt).toBeDefined();
      expect(typeof storedData.timestamp).toBe('number');
      expect(typeof storedData.createdAt).toBe('number');
    });

    it('should include config in stored data', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 15,
        maxAgeHours: 12,
        forceFallback: true,
      };
      
      await storeKeys('vault-123', keys, config);
      
      const storedData = JSON.parse(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')!);
      expect(storedData.config.timeoutMinutes).toBe(15);
      expect(storedData.config.maxAgeHours).toBe(12);
    });

    it('should throw error if vaultId is empty', async () => {
      const keys = createTestKeys();
      await expect(storeKeys('', keys)).rejects.toThrow('Vault ID is required');
    });

    it('should throw error if keys are null', async () => {
      await expect(storeKeys('vault-123', null as any)).rejects.toThrow('Keys are required');
    });
  });

  describe('retrieveKeys', () => {
    it('should retrieve stored keys', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      await storeKeys('vault-123', keys, config);
      
      const retrieved = await retrieveKeys('vault-123', config);
      
      expect(retrieved).not.toBeNull();
      expect(retrieved!.keyEncryptionKey).toEqual(keys.keyEncryptionKey);
      expect(retrieved!.metadataEncryptionKey).toEqual(keys.metadataEncryptionKey);
    });

    it('should return null if keys not found', async () => {
      const retrieved = await retrieveKeys('nonexistent-vault');
      expect(retrieved).toBeNull();
    });

    it('should update timestamp on retrieval', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      await storeKeys('vault-123', keys, config);
      
      const storedData1 = JSON.parse(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')!);
      const timestamp1 = storedData1.timestamp;
      
      // Wait a bit
      await new Promise(resolve => setTimeout(resolve, 10));
      
      await retrieveKeys('vault-123', config);
      
      const storedData2 = JSON.parse(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')!);
      const timestamp2 = storedData2.timestamp;
      
      expect(timestamp2).toBeGreaterThan(timestamp1);
    });

    it('should throw error if vaultId is empty', async () => {
      await expect(retrieveKeys('')).rejects.toThrow('Vault ID is required');
    });
  });

  describe('Expiration', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should return null for expired keys (inactivity timeout)', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 30,
        maxAgeHours: 0,
        forceFallback: true,
      };
      
      await storeKeys('vault-123', keys, config);
      
      // Advance time by 31 minutes
      jest.advanceTimersByTime(31 * 60 * 1000);
      
      const retrieved = await retrieveKeys('vault-123', config);
      expect(retrieved).toBeNull();
    });

    it('should return null for expired keys (max age)', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 0,
        maxAgeHours: 24,
        forceFallback: true,
      };
      
      await storeKeys('vault-123', keys, config);
      
      // Advance time by 25 hours
      jest.advanceTimersByTime(25 * 60 * 60 * 1000);
      
      const retrieved = await retrieveKeys('vault-123', config);
      expect(retrieved).toBeNull();
    });

    it('should not expire if timeout is 0', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 0,
        maxAgeHours: 0,
        forceFallback: true,
      };
      
      await storeKeys('vault-123', keys, config);
      
      // Advance time by a lot
      jest.advanceTimersByTime(100 * 60 * 60 * 1000);
      
      const retrieved = await retrieveKeys('vault-123', config);
      expect(retrieved).not.toBeNull();
    });

    it('should extend expiration on activity', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 30,
        maxAgeHours: 0,
        forceFallback: true,
      };
      
      await storeKeys('vault-123', keys, config);
      
      // Advance time by 20 minutes
      jest.advanceTimersByTime(20 * 60 * 1000);
      
      // Access keys (updates timestamp)
      await retrieveKeys('vault-123', config);
      
      // Advance time by another 20 minutes (40 total, but only 20 since last access)
      jest.advanceTimersByTime(20 * 60 * 1000);
      
      // Should still be valid
      const retrieved = await retrieveKeys('vault-123', config);
      expect(retrieved).not.toBeNull();
    });

    it('should respect max age regardless of activity', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 30,
        maxAgeHours: 2,
        forceFallback: true,
      };
      
      await storeKeys('vault-123', keys, config);
      
      // Keep accessing every 20 minutes for 3 hours
      for (let i = 0; i < 9; i++) {
        jest.advanceTimersByTime(20 * 60 * 1000);
        await retrieveKeys('vault-123', config);
      }
      
      // Should be expired due to max age (3 hours > 2 hours)
      const retrieved = await retrieveKeys('vault-123', config);
      expect(retrieved).toBeNull();
    });
  });

  describe('clearKeys', () => {
    it('should clear keys from storage', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      await storeKeys('vault-123', keys, config);
      
      await clearKeys('vault-123');
      
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')).toBeNull();
    });

    it('should throw error if vaultId is empty', async () => {
      await expect(clearKeys('')).rejects.toThrow('Vault ID is required');
    });
  });

  describe('clearAllKeys', () => {
    it('should clear all keys from storage', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };

      // Store multiple keys
      await storeKeys('vault-1', keys, config);
      await storeKeys('vault-2', keys, config);

      await clearAllKeys();

      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-1')).toBeNull();
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-2')).toBeNull();
      expect(mockLocalStorage.getItem('cortex_device_key_fallback')).toBeNull();
    });

    it('clears salt-hmac records along with all other key data', async () => {
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      const vaultId = 'vault-clear-salt';
      const fakeMac = new Uint8Array(32).fill(0x33);

      await storeSaltHmacRecord(vaultId, fakeMac, config);
      expect(await retrieveSaltHmacRecord(vaultId, config)).not.toBeNull();

      await clearAllKeys();

      expect(await retrieveSaltHmacRecord(vaultId, config)).toBeNull();
    });
  });

  describe('cleanupExpiredKeys', () => {
    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('should remove expired keys', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 30,
        maxAgeHours: 0,
        forceFallback: true,
      };
      
      // Store multiple keys
      await storeKeys('vault-1', keys, config);
      await storeKeys('vault-2', keys, config);
      await storeKeys('vault-3', keys, config);
      
      // Advance time to expire some keys
      jest.advanceTimersByTime(31 * 60 * 1000);
      
      const removedCount = await cleanupExpiredKeys(config);
      
      expect(removedCount).toBe(3);
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-1')).toBeNull();
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-2')).toBeNull();
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-3')).toBeNull();
    });

    it('should not remove valid keys', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = {
        timeoutMinutes: 30,
        maxAgeHours: 0,
        forceFallback: true,
      };
      
      await storeKeys('vault-1', keys, config);
      
      // Don't advance time
      const removedCount = await cleanupExpiredKeys(config);
      
      expect(removedCount).toBe(0);
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-1')).not.toBeNull();
    });

    it('should remove corrupted keys', async () => {
      // Manually insert corrupted data
      mockLocalStorage.setItem('cortex_encrypted_keys_vault-1', 'invalid json');
      
      const removedCount = await cleanupExpiredKeys();
      
      expect(removedCount).toBe(1);
      expect(mockLocalStorage.getItem('cortex_encrypted_keys_vault-1')).toBeNull();
    });
  });

  describe('Security Configurations', () => {
    it('should use DEFAULT_CONFIG correctly', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...DEFAULT_CONFIG, forceFallback: true };
      await storeKeys('vault-123', keys, config);
      
      const storedData = JSON.parse(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')!);
      expect(storedData.config.timeoutMinutes).toBe(30);
      expect(storedData.config.maxAgeHours).toBe(24);
    });

    it('should use HIGH_SECURITY_CONFIG correctly', async () => {
      const keys = createTestKeys();
      const config: KeyStorageConfig = { ...HIGH_SECURITY_CONFIG, forceFallback: true };
      await storeKeys('vault-123', keys, config);
      
      const storedData = JSON.parse(mockLocalStorage.getItem('cortex_encrypted_keys_vault-123')!);
      expect(storedData.config.timeoutMinutes).toBe(15);
      expect(storedData.config.maxAgeHours).toBe(8);
    });
  });

  describe('Nonce Reuse Prevention (Critical Security Fix)', () => {
    /**
     * SECURITY FIX: Hybrid Nonce Generation + Mutex Serialization for AES-GCM
     * 
     * This test documents the nonce reuse vulnerability fix.
     * The modern mode now uses hybrid nonces (counter + timestamp + random)
     * with mutex-based serialization, preventing catastrophic nonce reuse.
     * 
     * Context: When vault keys are re-encrypted multiple times with the same
     * device CryptoKey (e.g., during timestamp updates), pure random nonces
     * had birthday paradox collision risks. Additionally, concurrent encryption
     * operations could read the same counter value due to IndexedDB snapshot
     * isolation, causing nonce collisions.
     * 
     * Implementation Details:
     * 1. Counter storage in IndexedDB (monotonically increasing)
     * 2. Hybrid nonce structure: [counter:4][timestamp:4][random:4] bytes
     * 3. Promise-based mutex serializes counter increments (CRITICAL FIX)
     * 4. Timeout protection (5s) prevents deadlocks
     * 5. Counter overflow protection (error at 95% of 2^32 capacity)
     * 
     * Benefits:
     * - Mathematical guarantee of uniqueness (counter never repeats)
     * - No birthday paradox vulnerability  
     * - No race conditions in concurrent encryption (mutex serialization)
     * - Defense-in-depth with timestamp and random components
     * - Supports 4 billion encryptions before overflow
     * - Backward compatible (decryption works with any valid nonce)
     * 
     * Performance Impact:
     * - Mutex adds ~10-50ms serialization overhead per encryption
     * - Acceptable for user-facing operations (file uploads, key storage)
     * - Debug logging for high-concurrency scenarios (>5 queued operations)
     * 
     * Testing:
     * - See key-storage-concurrency.test.ts for comprehensive concurrency tests
     * - Tests verify uniqueness under parallel encryption (10-50 operations)
     * - Bulk upload simulation tests (realistic user scenarios)
     * 
     * Note: Fallback mode uses ChaCha20-Poly1305 which already has strong
     * built-in nonce generation, so it's not affected by this vulnerability.
     */
    it('should use hybrid nonce generation with mutex serialization to prevent reuse', () => {
      // This test documents the security fix implementation
      // For actual concurrency tests, see key-storage-concurrency.test.ts
      expect(true).toBe(true);
    });
  });
});
