import { describe, it, expect, beforeEach } from 'vitest';
import { deriveKeys, generateRecoveryKey, bytesToBase64 } from '@cortex/encryption';
import { encryptCollectionName } from '../items/collectionMetadata';
import { keysFromPhrase, identifyVaultForPhrase, normalizePhrase, PHRASE_ERROR } from './recovery';

const MASTER = new Uint8Array(32).fill(5);
const PHRASE = generateRecoveryKey(MASTER);

beforeEach(() => localStorage.clear());

describe('recovery', () => {
  it('normalizes case and whitespace', () => {
    expect(normalizePhrase('  Alpha   BRAVO\ncharlie ')).toBe('alpha bravo charlie');
    expect(normalizePhrase(['a', ' b', 'C'])).toBe('a b c');
  });

  it('derives the VMK and the same keys from the phrase as from the master key', () => {
    const r = keysFromPhrase(PHRASE)!;
    expect(r.vmk).toEqual(MASTER);
    expect(r.keys.metadataEncryptionKey).toEqual(deriveKeys(MASTER).metadataEncryptionKey);
  });

  it('returns null for anything that is not a valid 24-word phrase', () => {
    expect(keysFromPhrase('not a phrase')).toBeNull();
    expect(keysFromPhrase(PHRASE.split(' ').slice(0, 12).join(' '))).toBeNull();
  });

  it('identifies the vault whose encrypted name the phrase decrypts', async () => {
    const other = await encryptCollectionName('Other', deriveKeys(new Uint8Array(32).fill(9)).metadataEncryptionKey);
    const mine = await encryptCollectionName('Mine', deriveKeys(MASTER).metadataEncryptionKey);
    const vaults = [
      { vaultId: 'v1', encryptedName: bytesToBase64(other) },
      { vaultId: 'v2', encryptedName: bytesToBase64(mine) },
    ];
    expect(identifyVaultForPhrase(PHRASE, vaults)).toBe('v2');
    expect(identifyVaultForPhrase(PHRASE, [vaults[0]])).toBeNull();
    expect(identifyVaultForPhrase(PHRASE, [{ vaultId: 'v3' }])).toBeNull(); // no name to prove against
    expect(identifyVaultForPhrase('garbage', vaults)).toBeNull();
  });

  it('exposes one generic error string', () => {
    expect(PHRASE_ERROR).toMatch(/don't open a vault on this device/);
  });
});
