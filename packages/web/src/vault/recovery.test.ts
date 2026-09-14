import { describe, it, expect, beforeEach } from 'vitest';
import { deriveKeys, generateRecoveryKey } from '@cortex/encryption';
import { createVerifier, saveVerifier } from './verifier';
import { keysFromPhrase, identifyVaultForPhrase, normalizePhrase, PHRASE_ERROR } from './recovery';

const MASTER = new Uint8Array(32).fill(5);
const PHRASE = generateRecoveryKey(MASTER);

beforeEach(() => localStorage.clear());

describe('recovery', () => {
  it('normalizes case and whitespace', () => {
    expect(normalizePhrase('  Alpha   BRAVO\ncharlie ')).toBe('alpha bravo charlie');
    expect(normalizePhrase(['a', ' b', 'C'])).toBe('a b c');
  });

  it('derives the same keys from the phrase as from the master key', () => {
    const r = keysFromPhrase(PHRASE)!;
    expect(r.master).toEqual(MASTER);
    expect(r.keys.metadataEncryptionKey).toEqual(deriveKeys(MASTER).metadataEncryptionKey);
  });

  it('returns null for anything that is not a valid 24-word phrase', () => {
    expect(keysFromPhrase('not a phrase')).toBeNull();
    expect(keysFromPhrase(PHRASE.split(' ').slice(0, 12).join(' '))).toBeNull();
  });

  it('identifies the vault whose verifier the phrase opens', async () => {
    saveVerifier('v1', await createVerifier(deriveKeys(new Uint8Array(32).fill(9)).metadataEncryptionKey));
    saveVerifier('v2', await createVerifier(deriveKeys(MASTER).metadataEncryptionKey));
    expect(identifyVaultForPhrase(PHRASE, ['v1', 'v2'])).toBe('v2');
    expect(identifyVaultForPhrase(PHRASE, ['v1'])).toBeNull();
    expect(identifyVaultForPhrase('garbage', ['v2'])).toBeNull();
  });

  it('exposes one generic error string', () => {
    expect(PHRASE_ERROR).toMatch(/don't open a vault on this device/);
  });
});
