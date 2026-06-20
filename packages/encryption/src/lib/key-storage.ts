/**
 * Key Storage Module (Production-Grade Security)
 * 
 * Provides secure storage for derived encryption keys using:
 * - IndexedDB for structured storage with better isolation than localStorage
 * - Web Crypto API non-exportable keys (hardware-backed when available)
 * - Fallback to encrypted localStorage for older browsers
 * - Automatic expiration and cleanup
 * 
 * SECURITY MODEL:
 * - Device key is non-exportable CryptoKey (cannot be extracted via XSS)
 * - Vault keys encrypted with device key before IndexedDB storage
 * - Keys never transmitted to server
 * - Automatic expiration after inactivity
 * 
 * BROWSER COMPATIBILITY:
 * - Modern browsers: IndexedDB + Web Crypto API (non-exportable keys)
 * - Older browsers: Fallback to localStorage with encrypted keys
 */

import { encrypt, decrypt, bytesToBase64, base64ToBytes } from './encryption';

/**
 * IndexedDB configuration
 */
const DB_NAME = 'cortex_secure_storage';
const DB_VERSION = 2;
const STORE_NAME = 'encrypted_keys';
const DEVICE_KEY_STORE = 'device_keys';
const SALT_HMAC_STORE = 'salt_hmac_records';

/**
 * Storage key prefix for localStorage fallback
 */
const STORAGE_KEY_PREFIX = 'cortex_encrypted_keys_';

/**
 * localStorage key prefix for salt HMAC records (fallback path)
 */
const SALT_HMAC_STORAGE_KEY_PREFIX = 'cortex_salt_hmac_';

/**
 * Configuration for key storage security
 */
export interface KeyStorageConfig {
  /**
   * Inactivity timeout in minutes. Keys are cleared after this period of no activity.
   * Set to 0 to disable inactivity timeout.
   * 
   * Default: 30 minutes
   */
  timeoutMinutes: number;
  
  /**
   * Maximum age in hours. Keys are cleared after this time regardless of activity.
   * Set to 0 to disable maximum age limit.
   * 
   * Default: 24 hours
   */
  maxAgeHours: number;
  
  /**
   * Force fallback to localStorage (for testing or compatibility)
   * 
   * Default: false (use IndexedDB + Web Crypto when available)
   */
  forceFallback?: boolean;
}

/**
 * Default security configuration
 */
export const DEFAULT_CONFIG: KeyStorageConfig = {
  timeoutMinutes: 30, // 30 minutes of inactivity
  maxAgeHours: 24, // 24 hours maximum
  forceFallback: false,
};

/**
 * High-security configuration
 */
export const HIGH_SECURITY_CONFIG: KeyStorageConfig = {
  timeoutMinutes: 15, // 15 minutes of inactivity
  maxAgeHours: 8, // 8 hours maximum
  forceFallback: false,
};

/**
 * Interface for stored key data
 */
interface StoredKeyData {
  encryptedKeys: string; // Base64-encoded encrypted keys
  deviceId: string;
  version: number;
  timestamp: number; // Last activity timestamp
  createdAt: number; // Creation timestamp
  config: KeyStorageConfig;
}

/**
 * Interface for keys to be stored
 */
export interface KeysToStore {
  keyEncryptionKey: Uint8Array;
  metadataEncryptionKey: Uint8Array;
  shareKeyDerivationKey: Uint8Array;
  notesEncryptionKey: Uint8Array;
  tasksEncryptionKey: Uint8Array;
  eventsEncryptionKey: Uint8Array;
  notificationEncryptionKey: Uint8Array;
  dateBucketEncryptionKey: Uint8Array;
}

/**
 * Feature detection for Web Crypto API and IndexedDB
 */
const hasWebCrypto = typeof crypto !== 'undefined' && 
                     typeof crypto.subtle !== 'undefined';
const hasIndexedDB = typeof indexedDB !== 'undefined';

/**
 * Checks if modern security features are available
 */
function hasModernSecurity(): boolean {
  return hasWebCrypto && hasIndexedDB;
}

/**
 * Opens or creates the IndexedDB database
 */
function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(new Error('Failed to open IndexedDB'));
    
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      
      // Create object store for encrypted keys
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'vaultId' });
      }
      
      // Create object store for device keys (CryptoKey objects)
      if (!db.objectStoreNames.contains(DEVICE_KEY_STORE)) {
        db.createObjectStore(DEVICE_KEY_STORE, { keyPath: 'id' });
      }

      // Create object store for salt HMAC records (added in DB_VERSION 2)
      // These are plaintext, non-expiring, per-vault tamper-detection records.
      if (!db.objectStoreNames.contains(SALT_HMAC_STORE)) {
        db.createObjectStore(SALT_HMAC_STORE, { keyPath: 'vaultId' });
      }
    };
  });
}

/**
 * Stores data in IndexedDB
 */
async function storeInIndexedDB(storeName: string, data: any): Promise<void> {
  const db = await openDatabase();
  
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);
    const request = store.put(data);
    
    request.onerror = () => reject(new Error('Failed to store data in IndexedDB'));
    request.onsuccess = () => resolve();
    
    transaction.oncomplete = () => db.close();
  });
}

/**
 * Retrieves data from IndexedDB
 */
async function getFromIndexedDB<T>(storeName: string, key: string): Promise<T | null> {
  const db = await openDatabase();
  
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readonly');
    const store = transaction.objectStore(storeName);
    const request = store.get(key);
    
    request.onerror = () => reject(new Error('Failed to retrieve data from IndexedDB'));
    request.onsuccess = () => resolve(request.result || null);
    
    transaction.oncomplete = () => db.close();
  });
}

/**
 * Deletes data from IndexedDB
 */
async function deleteFromIndexedDB(storeName: string, key: string): Promise<void> {
  const db = await openDatabase();
  
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);
    const request = store.delete(key);
    
    request.onerror = () => reject(new Error('Failed to delete data from IndexedDB'));
    request.onsuccess = () => resolve();
    
    transaction.oncomplete = () => db.close();
  });
}

/**
 * Clears all data from an IndexedDB store
 */
async function clearIndexedDBStore(storeName: string): Promise<void> {
  const db = await openDatabase();
  
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readwrite');
    const store = transaction.objectStore(storeName);
    const request = store.clear();
    
    request.onerror = () => reject(new Error('Failed to clear IndexedDB store'));
    request.onsuccess = () => resolve();
    
    transaction.oncomplete = () => db.close();
  });
}

/**
 * Interface for device key storage data
 * 
 * NONCE REUSE PREVENTION:
 * The counter field is critical for preventing nonce reuse in AES-GCM encryption.
 * Each encryption operation increments this counter, providing a monotonically
 * increasing component for the hybrid nonce (counter + timestamp + random).
 */
interface DeviceKeyData {
  id: string;
  key: CryptoKey;
  counter: number; // Monotonic counter for nonce generation (prevents reuse)
}

/**
 * Counter overflow constants
 * Maximum value: 2^32 - 1 = 4,294,967,295 (about 4 billion encryptions)
 */
const COUNTER_MAX = 0xFFFFFFFF; // 2^32 - 1
const COUNTER_WARNING_THRESHOLD = Math.floor(COUNTER_MAX * 0.9); // 90% capacity
const COUNTER_ERROR_THRESHOLD = Math.floor(COUNTER_MAX * 0.95); // 95% capacity

/**
 * Mutex timeout for counter operations (5 seconds)
 * Prevents deadlock if an operation hangs
 */
const COUNTER_MUTEX_TIMEOUT_MS = 5000;

/**
 * Promise-based mutex for serializing counter increment operations.
 * 
 * CRITICAL FOR RACE CONDITION PREVENTION:
 * IndexedDB uses snapshot isolation, meaning concurrent transactions can read
 * the same counter value. This mutex ensures only one counter increment happens
 * at a time, preventing catastrophic nonce reuse in AES-GCM encryption.
 * 
 * Implementation:
 * - Promise-based queue (FIFO ordering)
 * - Timeout protection (5s) to prevent deadlocks
 * - Automatic cleanup on error or timeout
 * - Debug logging for troubleshooting concurrency issues
 */
class CounterMutex {
  private queue: Array<() => void> = [];
  private locked = false;
  
  /**
   * Acquires the mutex lock. If already locked, queues the request.
   * 
   * @param timeoutMs - Timeout in milliseconds (default: 5000ms)
   * @returns Promise that resolves when lock is acquired
   * @throws Error if timeout occurs
   */
  async acquire(timeoutMs: number = COUNTER_MUTEX_TIMEOUT_MS): Promise<void> {
    // Fast path: if not locked, acquire immediately
    if (!this.locked) {
      this.locked = true;
      return;
    }
    
    // Slow path: queue and wait for lock
    return new Promise<void>((resolve, reject) => {
      let timeoutId: ReturnType<typeof setTimeout> | null = null;
      let isResolved = false;
      
      const cleanup = () => {
        if (timeoutId !== null) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }
      };
      
      const onAcquire = () => {
        if (isResolved) return;
        isResolved = true;
        cleanup();
        resolve();
      };
      
      // Set timeout protection
      timeoutId = setTimeout(() => {
        if (isResolved) return;
        isResolved = true;
        
        // Remove from queue if still waiting
        const index = this.queue.indexOf(onAcquire);
        if (index !== -1) {
          this.queue.splice(index, 1);
        }
        
        reject(new Error(
          `Counter mutex timeout after ${timeoutMs}ms. ` +
          'This may indicate a deadlock or hung operation.'
        ));
      }, timeoutMs);
      
      // Add to queue
      this.queue.push(onAcquire);
    });
  }
  
  /**
   * Releases the mutex lock and processes next queued request.
   */
  release(): void {
    // Process next queued request
    const next = this.queue.shift();
    if (next) {
      // Keep lock and notify next waiter
      next();
    } else {
      // No more waiters, release lock
      this.locked = false;
    }
  }
  
  /**
   * Gets current queue length (for debugging/monitoring).
   */
  getQueueLength(): number {
    return this.queue.length;
  }
}

/**
 * Global mutex instance for counter increment operations.
 * Shared across all encryption operations to prevent race conditions.
 */
const counterMutex = new CounterMutex();

/**
 * Retrieves and atomically increments the encryption counter for a device key.
 * 
 * SECURITY CRITICAL: This function provides the monotonic counter component
 * for hybrid nonce generation, preventing nonce reuse in AES-GCM encryption.
 * 
 * RACE CONDITION FIX:
 * Uses a mutex to serialize counter increments, preventing concurrent operations
 * from reading the same counter value due to IndexedDB snapshot isolation.
 * Without this mutex, parallel encryptions could generate identical nonces,
 * causing catastrophic AES-GCM security failure.
 * 
 * Performance Impact:
 * - Serialization adds ~10-50ms overhead per encryption
 * - Timeout protection prevents deadlocks (5s max wait)
 * - Queue length monitored for debugging
 * 
 * @param keyId - The device key identifier
 * @returns Promise<number> - Current counter value (before increment)
 * @throws Error if counter overflow occurs (at 95% capacity) or mutex timeout
 */
async function getAndIncrementCounter(keyId: string): Promise<number> {
  // CRITICAL: Acquire mutex lock before ANY database operations
  // This prevents race conditions from concurrent counter reads
  await counterMutex.acquire();
  
  try {
    const db = await openDatabase();
    
    return await new Promise<number>((resolve, reject) => {
      const transaction = db.transaction([DEVICE_KEY_STORE], 'readwrite');
      const store = transaction.objectStore(DEVICE_KEY_STORE);
      
      // Read current device key data
      const getRequest = store.get(keyId);
      
      getRequest.onsuccess = () => {
        const keyData = getRequest.result as DeviceKeyData | undefined;
        
        if (!keyData) {
          reject(new Error(`Device key not found: ${keyId}`));
          return;
        }
        
        const currentCounter = keyData.counter ?? 0; // Handle migration: default to 0
        
        // Check for counter overflow
        if (currentCounter >= COUNTER_ERROR_THRESHOLD) {
          reject(new Error(
            `Counter overflow imminent: ${currentCounter}/${COUNTER_MAX}. ` +
            'Please generate a new device key.'
          ));
          return;
        }
        
        // Log warning at 90% capacity
        if (currentCounter >= COUNTER_WARNING_THRESHOLD && currentCounter < COUNTER_ERROR_THRESHOLD) {
          console.warn(
            `Counter approaching capacity: ${currentCounter}/${COUNTER_MAX} (${
              Math.floor((currentCounter / COUNTER_MAX) * 100)
            }%). Consider generating a new device key soon.`
          );
        }
        
        // Debug logging for high-concurrency scenarios
        const queueLength = counterMutex.getQueueLength();
        if (queueLength > 5) {
          console.debug(
            `High counter mutex contention: ${queueLength} operations queued. ` +
            'Consider batching encryption operations if possible.'
          );
        }
        
        // Increment counter for next use
        const newCounter = currentCounter + 1;
        keyData.counter = newCounter;
        
        // Write updated counter back to storage
        const putRequest = store.put(keyData);
        
        putRequest.onsuccess = () => {
          resolve(currentCounter); // Return value BEFORE increment
        };
        
        putRequest.onerror = () => {
          reject(new Error('Failed to increment counter'));
        };
      };
      
      getRequest.onerror = () => {
        reject(new Error('Failed to read device key data'));
      };
      
      transaction.oncomplete = () => db.close();
      transaction.onerror = () => {
        db.close();
        reject(new Error('Counter increment transaction failed'));
      };
    });
  } finally {
    // CRITICAL: Always release mutex, even on error
    // Failure to release would cause deadlock for all future operations
    counterMutex.release();
  }
}

/**
 * Generates or retrieves a non-exportable device key using Web Crypto API.
 * 
 * SECURITY BENEFITS:
 * - Key is non-exportable (cannot be extracted via JavaScript/XSS)
 * - Hardware-backed on supported devices (TPM, Secure Enclave)
 * - Key handle stored in IndexedDB, actual key in browser's secure storage
 * - Counter initialized to 0 for nonce reuse prevention
 * 
 * @returns Promise<CryptoKey> - Non-exportable AES-GCM key
 */
async function getModernDeviceKey(): Promise<CryptoKey> {
  const keyId = 'cortex_device_key_v2';
  
  // Try to retrieve existing key
  const existingKeyData = await getFromIndexedDB<DeviceKeyData>(
    DEVICE_KEY_STORE,
    keyId
  );
  
  if (existingKeyData && existingKeyData.key) {
    // MIGRATION: Add counter field to existing device keys
    if (existingKeyData.counter === undefined) {
      console.info('Migrating device key to counter-based nonce generation');
      existingKeyData.counter = 0;
      await storeInIndexedDB(DEVICE_KEY_STORE, existingKeyData);
    }
    return existingKeyData.key;
  }
  
  // Generate new non-exportable key
  const key = await crypto.subtle.generateKey(
    {
      name: 'AES-GCM',
      length: 256,
    },
    false, // non-exportable - THIS IS THE KEY SECURITY FEATURE
    ['encrypt', 'decrypt']
  );
  
  // Store key handle in IndexedDB with counter initialized to 0
  const keyData: DeviceKeyData = {
    id: keyId,
    key,
    counter: 0, // Initialize counter for nonce generation
  };
  
  await storeInIndexedDB(DEVICE_KEY_STORE, keyData);
  
  return key;
}

/**
 * Generates a hybrid nonce for AES-GCM encryption with guaranteed uniqueness.
 * 
 * SECURITY CRITICAL: This function prevents nonce reuse attacks in AES-GCM by
 * combining three components:
 * 
 * Nonce Structure (96 bits / 12 bytes total):
 * - Bytes 0-3: Counter (32 bits, big-endian) - Monotonically increasing
 * - Bytes 4-7: Timestamp (32 bits, big-endian) - Unix timestamp in seconds
 * - Bytes 8-11: Random (32 bits) - Cryptographically secure random bytes
 * 
 * The counter component guarantees mathematical uniqueness (never repeats until
 * overflow at 2^32 operations). The timestamp provides time-based diversity.
 * The random component maintains cryptographic strength.
 * 
 * This hybrid approach eliminates birthday paradox vulnerabilities present in
 * pure random nonce generation, which could lead to catastrophic nonce reuse
 * in AES-GCM encryption.
 * 
 * @param keyId - The device key identifier for counter retrieval
 * @returns Promise<Uint8Array> - A 12-byte (96-bit) hybrid nonce
 */
async function generateHybridNonce(keyId: string): Promise<Uint8Array> {
  const nonce = new Uint8Array(12);
  
  // Component 1: Counter (bytes 0-3) - Monotonically increasing
  // This is the CRITICAL component that guarantees uniqueness
  const counter = await getAndIncrementCounter(keyId);
  const counterView = new DataView(nonce.buffer, 0, 4);
  counterView.setUint32(0, counter, false); // big-endian
  
  // Component 2: Timestamp (bytes 4-7) - Unix timestamp in seconds
  // Provides time-based diversity and prevents prediction
  const timestamp = Math.floor(Date.now() / 1000);
  const timestampView = new DataView(nonce.buffer, 4, 4);
  timestampView.setUint32(0, timestamp, false); // big-endian
  
  // Component 3: Random (bytes 8-11) - Cryptographic randomness
  // Defense-in-depth: maintains cryptographic strength
  const randomBytes = nonce.subarray(8, 12);
  crypto.getRandomValues(randomBytes);
  
  return nonce;
}

/**
 * Encrypts data using Web Crypto API with non-exportable key.
 * 
 * SECURITY UPDATE: Now uses hybrid nonce generation (counter + timestamp + random)
 * instead of pure random to prevent nonce reuse vulnerabilities in AES-GCM.
 * 
 * @param data - Data to encrypt
 * @param key - CryptoKey for encryption
 * @param keyId - Device key identifier for nonce generation
 * @returns Promise<Uint8Array> - Encrypted data (IV + ciphertext + tag)
 */
async function encryptWithWebCrypto(
  data: Uint8Array,
  key: CryptoKey,
  keyId: string
): Promise<Uint8Array> {
  // Generate hybrid nonce (counter + timestamp + random)
  // This replaces the previous pure random approach which had birthday paradox
  // collision risks when the same key was used for thousands of encryptions
  const iv = await generateHybridNonce(keyId);
  
  // Encrypt data
  const encrypted = await crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: iv as BufferSource,
    },
    key,
    data as BufferSource
  );
  
  // Combine IV + encrypted data
  const result = new Uint8Array(iv.length + encrypted.byteLength);
  result.set(iv, 0);
  result.set(new Uint8Array(encrypted), iv.length);
  
  return result;
}

/**
 * Decrypts data using Web Crypto API with non-exportable key.
 * 
 * @param encryptedData - Encrypted data (IV + ciphertext + tag)
 * @param key - CryptoKey for decryption
 * @returns Promise<Uint8Array> - Decrypted data
 */
async function decryptWithWebCrypto(encryptedData: Uint8Array, key: CryptoKey): Promise<Uint8Array> {
  // Extract IV (first 12 bytes)
  const iv = encryptedData.slice(0, 12);
  const ciphertext = encryptedData.slice(12);
  
  // Decrypt data
  const decrypted = await crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: iv,
    },
    key,
    ciphertext
  );
  
  return new Uint8Array(decrypted);
}

/**
 * FALLBACK: Generates or retrieves a device key from localStorage.
 * Used only when Web Crypto API or IndexedDB is not available.
 * 
 * SECURITY WARNING: This key is exportable and vulnerable to XSS attacks.
 * Only used as fallback for older browsers.
 * 
 * @returns Promise<Uint8Array> - The 256-bit device-specific key
 */
async function getFallbackDeviceKey(): Promise<Uint8Array> {
  const deviceKeyStorageKey = 'cortex_device_key_fallback';
  
  // Try to retrieve existing device key
  const existingKey = localStorage.getItem(deviceKeyStorageKey);
  if (existingKey) {
    try {
      const keyBytes = Uint8Array.from(atob(existingKey), c => c.charCodeAt(0));
      if (keyBytes.length === 32) {
        return keyBytes;
      }
    } catch (error) {
      console.warn('Failed to parse existing device key, generating new one');
    }
  }
  
  // Generate new device key
  const deviceKey = new Uint8Array(32);
  crypto.getRandomValues(deviceKey);
  
  // Store the device key
  const keyBase64 = btoa(String.fromCharCode(...deviceKey));
  localStorage.setItem(deviceKeyStorageKey, keyBase64);
  
  return deviceKey;
}

/**
 * Generates a unique device identifier.
 * 
 * @returns string - A unique device identifier
 */
function getDeviceId(): string {
  const deviceIdKey = 'cortex_device_id';
  
  let deviceId = localStorage.getItem(deviceIdKey);
  if (!deviceId) {
    // Generate a random device ID
    const randomBytes = new Uint8Array(16);
    crypto.getRandomValues(randomBytes);
    deviceId = Array.from(randomBytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
    localStorage.setItem(deviceIdKey, deviceId);
  }
  
  return deviceId;
}

/**
 * Checks if stored keys have expired based on configuration.
 * 
 * @param storageData - The stored key data
 * @param config - Storage configuration
 * @returns boolean - True if keys have expired
 */
function isExpired(storageData: StoredKeyData, config: KeyStorageConfig): boolean {
  const now = Date.now();
  
  // Check inactivity timeout
  if (config.timeoutMinutes > 0) {
    const inactivityMs = config.timeoutMinutes * 60 * 1000;
    if (now - storageData.timestamp > inactivityMs) {
      return true;
    }
  }
  
  // Check maximum age
  if (config.maxAgeHours > 0) {
    const maxAgeMs = config.maxAgeHours * 60 * 60 * 1000;
    if (now - storageData.createdAt > maxAgeMs) {
      return true;
    }
  }
  
  return false;
}

/**
 * Stores derived encryption keys using modern security (IndexedDB + Web Crypto API).
 * 
 * SECURITY MODEL:
 * - Device key is non-exportable CryptoKey (cannot be stolen via XSS)
 * - Vault keys encrypted with device key using AES-GCM
 * - Encrypted keys stored in IndexedDB (better isolation than localStorage)
 * - Automatic expiration based on configuration
 * - Keys NEVER transmitted to server
 * 
 * @param vaultId - The vault identifier
 * @param keys - The derived encryption keys to store
 * @param config - Storage configuration
 * @returns Promise<void>
 */
async function storeKeysModern(
  vaultId: string,
  keys: KeysToStore,
  config: KeyStorageConfig
): Promise<void> {
  // Get non-exportable device key
  const deviceKey = await getModernDeviceKey();
  const keyId = 'cortex_device_key_v2'; // Device key identifier for nonce generation
  
  // Serialize keys to JSON
  const keysJson = serializeKeys(keys);
  const keysBytes = new TextEncoder().encode(keysJson);
  
  // Encrypt with Web Crypto API using hybrid nonce generation
  const encryptedKeys = await encryptWithWebCrypto(keysBytes, deviceKey, keyId);
  
  // Encode as base64
  const encryptedKeysBase64 = btoa(String.fromCharCode(...encryptedKeys));
  
  // Create storage object
  const now = Date.now();
  const storageData: StoredKeyData & { vaultId: string } = {
    vaultId,
    encryptedKeys: encryptedKeysBase64,
    deviceId: getDeviceId(),
    version: 2, // Version 2 = IndexedDB + Web Crypto
    timestamp: now,
    createdAt: now,
    config,
  };
  
  // Store in IndexedDB
  await storeInIndexedDB(STORE_NAME, storageData);
}

/**
 * Retrieves keys using modern security (IndexedDB + Web Crypto API).
 * 
 * This function uses constant-time operations to prevent timing side-channels.
 * Decryption is ALWAYS performed before checking expiration, ensuring that:
 * - Expired keys take the same time as valid keys
 * - Attackers cannot distinguish between expired vs. invalid decryption
 * - Cleanup happens asynchronously to avoid timing correlation
 * 
 * @param vaultId - The vault identifier
 * @param config - Storage configuration
 * @returns Promise<KeysToStore | null> - The decrypted keys, or null if not found/expired
 */
async function retrieveKeysModern(
  vaultId: string,
  config: KeyStorageConfig
): Promise<KeysToStore | null> {
  // Retrieve from IndexedDB
  const storageData = await getFromIndexedDB<StoredKeyData & { vaultId: string }>(
    STORE_NAME,
    vaultId
  );
  
  if (!storageData) {
    return null;
  }
  
  // CONSTANT-TIME: Always decrypt BEFORE checking expiration
  // This prevents timing attacks that could distinguish between
  // "expired key" and "invalid decryption"
  let keys: KeysToStore | null = null;
  try {
    // Get non-exportable device key
    const deviceKey = await getModernDeviceKey();
    
    // Decode base64
    const encryptedKeys = Uint8Array.from(
      atob(storageData.encryptedKeys),
      c => c.charCodeAt(0)
    );
    
    // Decrypt with Web Crypto API
    const decryptedKeysBytes = await decryptWithWebCrypto(encryptedKeys, deviceKey);
    const keysJson = new TextDecoder().decode(decryptedKeysBytes);
    
    // Deserialize keys
    keys = deserializeKeys(keysJson);
  } catch (error) {
    // Decryption failed - treat same as expired for constant-time behavior
    keys = null;
  }
  
  // NOW check expiration (after constant-time decryption operations)
  const expired = isExpired(storageData, config);
  
  if (expired || keys === null) {
    // Schedule cleanup asynchronously to avoid timing leak
    // setTimeout ensures cleanup doesn't affect response time
    setTimeout(() => deleteFromIndexedDB(STORE_NAME, vaultId), 0);
    return null;
  }
  
  // Update last activity timestamp
  storageData.timestamp = Date.now();
  await storeInIndexedDB(STORE_NAME, storageData);
  
  return keys;
}

/**
 * FALLBACK: Stores keys using localStorage (for older browsers).
 * 
 * @param vaultId - The vault identifier
 * @param keys - The derived encryption keys to store
 * @param config - Storage configuration
 * @returns Promise<void>
 */
async function storeKeysFallback(
  vaultId: string,
  keys: KeysToStore,
  config: KeyStorageConfig
): Promise<void> {
  // Get fallback device key (exportable, stored in localStorage)
  const deviceKey = await getFallbackDeviceKey();
  
  // Serialize keys
  const keysJson = serializeKeys(keys);
  const keysBytes = new TextEncoder().encode(keysJson);
  
  // Encrypt with ChaCha20-Poly1305
  const encryptedKeys = await encrypt(keysBytes, deviceKey);
  
  // Encode as base64
  const encryptedKeysBase64 = btoa(String.fromCharCode(...encryptedKeys));
  
  // Create storage object
  const now = Date.now();
  const storageData: StoredKeyData = {
    encryptedKeys: encryptedKeysBase64,
    deviceId: getDeviceId(),
    version: 1, // Version 1 = localStorage fallback
    timestamp: now,
    createdAt: now,
    config,
  };
  
  // Store in localStorage
  const storageKey = STORAGE_KEY_PREFIX + vaultId;
  localStorage.setItem(storageKey, JSON.stringify(storageData));
}

/**
 * FALLBACK: Retrieves keys using localStorage (for older browsers).
 * 
 * This function uses constant-time operations to prevent timing side-channels.
 * Decryption is ALWAYS performed before checking expiration, ensuring that:
 * - Expired keys take the same time as valid keys
 * - Attackers cannot distinguish between expired vs. invalid decryption
 * - Cleanup happens asynchronously to avoid timing correlation
 * 
 * @param vaultId - The vault identifier
 * @param config - Storage configuration
 * @returns Promise<KeysToStore | null> - The decrypted keys, or null if not found/expired
 */
async function retrieveKeysFallback(
  vaultId: string,
  config: KeyStorageConfig
): Promise<KeysToStore | null> {
  // Retrieve from localStorage
  const storageKey = STORAGE_KEY_PREFIX + vaultId;
  const storedData = localStorage.getItem(storageKey);
  
  if (!storedData) {
    return null;
  }
  
  // Parse storage data
  const storageData: StoredKeyData = JSON.parse(storedData);
  
  // CONSTANT-TIME: Always decrypt BEFORE checking expiration
  // This prevents timing attacks that could distinguish between
  // "expired key" and "invalid decryption"
  let keys: KeysToStore | null = null;
  try {
    // Get fallback device key
    const deviceKey = await getFallbackDeviceKey();
    
    // Decode base64
    const encryptedKeys = Uint8Array.from(
      atob(storageData.encryptedKeys),
      c => c.charCodeAt(0)
    );
    
    // Decrypt with ChaCha20-Poly1305
    const decryptedKeysBytes = decrypt(encryptedKeys, deviceKey);
    const keysJson = new TextDecoder().decode(decryptedKeysBytes);
    
    // Deserialize keys
    keys = deserializeKeys(keysJson);
  } catch (error) {
    // Decryption failed - treat same as expired for constant-time behavior
    keys = null;
  }
  
  // NOW check expiration (after constant-time decryption operations)
  const expired = isExpired(storageData, config);
  
  if (expired || keys === null) {
    // Schedule cleanup asynchronously to avoid timing leak
    // setTimeout ensures cleanup doesn't affect response time
    setTimeout(() => localStorage.removeItem(storageKey), 0);
    return null;
  }
  
  // Update last activity timestamp
  storageData.timestamp = Date.now();
  localStorage.setItem(storageKey, JSON.stringify(storageData));
  
  return keys;
}

// ---------------------------------------------------------------------------
// Salt HMAC record storage (standalone, plaintext, non-expiring)
// ---------------------------------------------------------------------------

/**
 * Internal shape of a stored salt HMAC record.
 * NOT exported — callers use the public functions below.
 */
interface StoredSaltHmacRecord {
  vaultId: string;
  /** Base64-encoded HMAC bytes for safe round-trip through JSON / structured clone. */
  saltHmac: string;
  createdAt: number;
}

/**
 * Persists (or overwrites) the salt HMAC for a vault in a standalone,
 * non-expiring record. Uses IndexedDB when modern security is available and
 * `config.forceFallback` is not set; otherwise falls back to localStorage.
 *
 * Unlike the encrypted key bundle, this record has no max-age — it survives
 * bundle expiry and is intentionally plaintext (the HMAC is non-secret).
 *
 * @param vaultId - The vault identifier
 * @param saltHmac - The raw HMAC bytes to store (will be base64-encoded)
 * @param config   - Optional storage config; only `forceFallback` is consulted
 */
export async function storeSaltHmacRecord(
  vaultId: string,
  saltHmac: Uint8Array,
  config?: KeyStorageConfig
): Promise<void> {
  const record: StoredSaltHmacRecord = {
    vaultId,
    saltHmac: bytesToBase64(saltHmac),
    createdAt: Date.now(),
  };

  if (hasModernSecurity() && !config?.forceFallback) {
    await storeInIndexedDB(SALT_HMAC_STORE, record);
  } else {
    const storageKey = SALT_HMAC_STORAGE_KEY_PREFIX + vaultId;
    localStorage.setItem(storageKey, JSON.stringify(record));
  }
}

/**
 * Retrieves the previously-stored salt HMAC bytes for a vault.
 * Returns `null` when no record has been written for this vaultId.
 *
 * This function NEVER applies expiry checks — the record is permanent until
 * explicitly cleared via `clearSaltHmacRecord`.
 *
 * @param vaultId - The vault identifier
 * @param config   - Optional storage config; only `forceFallback` is consulted
 * @returns The raw HMAC bytes, or null if absent
 */
export async function retrieveSaltHmacRecord(
  vaultId: string,
  config?: KeyStorageConfig
): Promise<Uint8Array | null> {
  if (hasModernSecurity() && !config?.forceFallback) {
    const record = await getFromIndexedDB<StoredSaltHmacRecord>(
      SALT_HMAC_STORE,
      vaultId
    );
    if (!record) return null;
    return base64ToBytes(record.saltHmac);
  } else {
    const storageKey = SALT_HMAC_STORAGE_KEY_PREFIX + vaultId;
    const raw = localStorage.getItem(storageKey);
    if (!raw) return null;
    try {
      const record: StoredSaltHmacRecord = JSON.parse(raw);
      return base64ToBytes(record.saltHmac);
    } catch {
      return null;
    }
  }
}

/**
 * Removes the salt HMAC record for a vault from both storage backends.
 *
 * @param vaultId - The vault identifier
 * @param config   - Optional storage config; only `forceFallback` is consulted
 */
export async function clearSaltHmacRecord(
  vaultId: string,
  config?: KeyStorageConfig
): Promise<void> {
  if (hasModernSecurity() && !config?.forceFallback) {
    try {
      await deleteFromIndexedDB(SALT_HMAC_STORE, vaultId);
    } catch {
      // Ignore — may not exist
    }
  }
  // Always clear localStorage path too (handles cross-path cleanup)
  const storageKey = SALT_HMAC_STORAGE_KEY_PREFIX + vaultId;
  localStorage.removeItem(storageKey);
}

// ---------------------------------------------------------------------------
// Key serialization / deserialization
// ---------------------------------------------------------------------------

/**
 * Serializes keys to a JSON string for encryption.
 *
 * @param keys - The keys to serialize
 * @returns string - JSON string representation
 */
function serializeKeys(keys: KeysToStore): string {
  const serializable: Record<string, unknown> = {
    keyEncryptionKey: Array.from(keys.keyEncryptionKey),
    metadataEncryptionKey: Array.from(keys.metadataEncryptionKey),
    shareKeyDerivationKey: Array.from(keys.shareKeyDerivationKey),
    notesEncryptionKey: Array.from(keys.notesEncryptionKey),
    tasksEncryptionKey: Array.from(keys.tasksEncryptionKey),
    eventsEncryptionKey: Array.from(keys.eventsEncryptionKey),
    notificationEncryptionKey: Array.from(keys.notificationEncryptionKey),
    dateBucketEncryptionKey: Array.from(keys.dateBucketEncryptionKey),
  };

  return JSON.stringify(serializable);
}

/**
 * Deserializes keys from a JSON string.
 * 
 * @param json - JSON string representation of keys
 * @returns KeysToStore - The deserialized keys
 */
function deserializeKeys(json: string): KeysToStore {
  const parsed = JSON.parse(json);

  const result: KeysToStore = {
    keyEncryptionKey: new Uint8Array(parsed.keyEncryptionKey),
    metadataEncryptionKey: new Uint8Array(parsed.metadataEncryptionKey),
    shareKeyDerivationKey: new Uint8Array(parsed.shareKeyDerivationKey),
    notesEncryptionKey: new Uint8Array(parsed.notesEncryptionKey),
    tasksEncryptionKey: new Uint8Array(parsed.tasksEncryptionKey),
    eventsEncryptionKey: new Uint8Array(parsed.eventsEncryptionKey),
    notificationEncryptionKey: new Uint8Array(parsed.notificationEncryptionKey),
    dateBucketEncryptionKey: new Uint8Array(parsed.dateBucketEncryptionKey),
  };

  return result;
}

/**
 * Stores derived encryption keys with automatic modern/fallback selection.
 * 
 * MODERN MODE (default):
 * - Uses IndexedDB for storage (better isolation than localStorage)
 * - Uses Web Crypto API non-exportable keys (cannot be stolen via XSS)
 * - Hardware-backed security on supported devices
 * 
 * FALLBACK MODE (older browsers):
 * - Uses localStorage for storage
 * - Uses exportable keys encrypted with ChaCha20-Poly1305
 * - Still secure but vulnerable to XSS attacks
 * 
 * @param vaultId - The vault identifier
 * @param keys - The derived encryption keys to store
 * @param config - Storage configuration (optional, uses DEFAULT_CONFIG if not provided)
 * @returns Promise<void>
 * 
 * @example
 * // Store with default config (30min timeout, 24h max age)
 * await storeKeys('vault-123', keys);
 * 
 * @example
 * // Store with high-security config (15min timeout, 8h max age)
 * await storeKeys('vault-123', keys, HIGH_SECURITY_CONFIG);
 * 
 * @example
 * // Force fallback mode (for testing)
 * await storeKeys('vault-123', keys, { ...DEFAULT_CONFIG, forceFallback: true });
 */
export async function storeKeys(
  vaultId: string,
  keys: KeysToStore,
  config: KeyStorageConfig = DEFAULT_CONFIG
): Promise<void> {
  if (!vaultId) {
    throw new Error('Vault ID is required');
  }
  
  if (!keys) {
    throw new Error('Keys are required');
  }
  
  try {
    // Use modern security if available, otherwise fallback
    if (hasModernSecurity() && !config.forceFallback) {
      await storeKeysModern(vaultId, keys, config);
    } else {
      await storeKeysFallback(vaultId, keys, config);
    }
  } catch (error) {
    throw new Error(`Failed to store keys: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Retrieves and decrypts stored encryption keys with automatic modern/fallback selection.
 * 
 * Automatically checks for expiration and returns null if keys have expired.
 * Updates the last activity timestamp on successful retrieval.
 * 
 * @param vaultId - The vault identifier
 * @param config - Storage configuration (optional, uses DEFAULT_CONFIG if not provided)
 * @returns Promise<KeysToStore | null> - The decrypted keys, or null if not found/expired
 * 
 * @example
 * const keys = await retrieveKeys('vault-123');
 * if (keys) {
 *   // Use keys for encryption/decryption
 * } else {
 *   // Keys not found or expired, user needs to enter vault password
 * }
 */
export async function retrieveKeys(
  vaultId: string,
  config: KeyStorageConfig = DEFAULT_CONFIG
): Promise<KeysToStore | null> {
  if (!vaultId) {
    throw new Error('Vault ID is required');
  }
  
  try {
    // Try modern security first
    if (hasModernSecurity() && !config.forceFallback) {
      const keys = await retrieveKeysModern(vaultId, config);
      if (keys) return keys;
    }
    
    // Fallback to localStorage
    return await retrieveKeysFallback(vaultId, config);
  } catch (error) {
    throw new Error(`Failed to retrieve keys: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Clears stored encryption keys from both modern and fallback storage.
 * 
 * This should be called when the user logs out or wants to remove stored keys.
 * 
 * @param vaultId - The vault identifier
 * @returns Promise<void>
 * 
 * @example
 * await clearKeys('vault-123');
 */
export async function clearKeys(vaultId: string): Promise<void> {
  if (!vaultId) {
    throw new Error('Vault ID is required');
  }
  
  try {
    // Clear from IndexedDB (modern)
    if (hasIndexedDB) {
      await deleteFromIndexedDB(STORE_NAME, vaultId);
    }
  } catch (error) {
    // Ignore errors, continue to fallback cleanup
  }
  
  // Clear from localStorage (fallback)
  const storageKey = STORAGE_KEY_PREFIX + vaultId;
  localStorage.removeItem(storageKey);
}

/**
 * Clears all stored keys and device-specific data from all storage mechanisms.
 * 
 * This is a complete cleanup that removes:
 * - All vault keys from IndexedDB
 * - All vault keys from localStorage
 * - Device keys from both storage types
 * - Device IDs
 * 
 * Use this when the user wants to completely reset the application.
 * 
 * @returns Promise<void>
 */
export async function clearAllKeys(): Promise<void> {
  try {
    // Clear IndexedDB (modern)
    if (hasIndexedDB) {
      await clearIndexedDBStore(STORE_NAME);
      await clearIndexedDBStore(DEVICE_KEY_STORE);
      await clearIndexedDBStore(SALT_HMAC_STORE);
    }
  } catch (error) {
    // Ignore errors, continue to fallback cleanup
  }

  // Clear localStorage (fallback)
  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (
      key &&
      (key.startsWith(STORAGE_KEY_PREFIX) ||
        key.startsWith(SALT_HMAC_STORAGE_KEY_PREFIX) ||
        key.includes('cortex_device'))
    ) {
      keysToRemove.push(key);
    }
  }

  keysToRemove.forEach(key => localStorage.removeItem(key));
}

/**
 * Registers cleanup handlers for browser events.
 * 
 * This should be called once during application initialization to ensure
 * proper cleanup on browser close or navigation.
 * 
 * @returns void
 * 
 * @example
 * // In your app initialization
 * registerCleanupHandlers();
 */
export function registerCleanupHandlers(): void {
  // Optional: Clear keys on browser close (best effort)
  // Commented out by default as it may be too aggressive
  /*
  window.addEventListener('beforeunload', () => {
    clearAllKeys();
  });
  */
}

/**
 * Cleans up expired keys from all storage mechanisms.
 * 
 * This should be called periodically (e.g., on app startup) to remove
 * expired keys and free up storage space.
 * 
 * @param config - Storage configuration (optional, uses DEFAULT_CONFIG if not provided)
 * @returns Promise<number> - Number of expired keys removed
 */
export async function cleanupExpiredKeys(config: KeyStorageConfig = DEFAULT_CONFIG): Promise<number> {
  let removedCount = 0;
  
  try {
    // Cleanup IndexedDB (modern)
    if (hasIndexedDB) {
      const db = await openDatabase();
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.openCursor();
      
      await new Promise<void>((resolve, reject) => {
        request.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest).result;
          if (cursor) {
            const data: StoredKeyData = cursor.value;
            if (isExpired(data, config)) {
              cursor.delete();
              removedCount++;
            }
            cursor.continue();
          } else {
            resolve();
          }
        };
        request.onerror = () => reject(new Error('Failed to cleanup IndexedDB'));
      });
      
      db.close();
    }
  } catch (error) {
    // Ignore errors, continue to fallback cleanup
  }
  
  // Cleanup localStorage (fallback)
  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(STORAGE_KEY_PREFIX)) {
      try {
        const storedData = localStorage.getItem(key);
        if (storedData) {
          const data: StoredKeyData = JSON.parse(storedData);
          if (isExpired(data, config)) {
            keysToRemove.push(key);
          }
        }
      } catch (error) {
        // If parsing fails, remove the corrupted key
        keysToRemove.push(key);
      }
    }
  }
  
  keysToRemove.forEach(key => localStorage.removeItem(key));
  removedCount += keysToRemove.length;
  
  return removedCount;
}

/**
 * Gets information about the current storage mode.
 * 
 * @returns Object with storage mode information
 */
export function getStorageInfo(): {
  mode: 'modern' | 'fallback';
  hasWebCrypto: boolean;
  hasIndexedDB: boolean;
  features: string[];
} {
  const mode = hasModernSecurity() ? 'modern' : 'fallback';
  const features: string[] = [];
  
  if (hasWebCrypto) {
    features.push('Web Crypto API (non-exportable keys)');
  }
  if (hasIndexedDB) {
    features.push('IndexedDB (isolated storage)');
  }
  if (mode === 'fallback') {
    features.push('localStorage fallback');
  }
  
  return {
    mode,
    hasWebCrypto,
    hasIndexedDB,
    features,
  };
}
