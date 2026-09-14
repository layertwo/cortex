import { validateRecoveryKey, deriveKeys, type DerivedKeys } from '@cortex/encryption';
import { checkVerifier, loadVerifier } from './verifier';

// One message for every failure. Which word is wrong, or whether the phrase is well-formed
// but for another vault, is deliberately not disclosed.
export const PHRASE_ERROR =
  "Those words don't open a vault on this device. Check each word and the order, then try again. On a new device, use your recovery kit.";

export function normalizePhrase(input: string | string[]): string {
  const text = Array.isArray(input) ? input.join(' ') : input;
  return text.trim().toLowerCase().split(/\s+/).filter(Boolean).join(' ');
}

// The 24 words are a BIP39 encoding of the vault master key, so the phrase alone yields the
// same derived keys the password would. Null for anything validateRecoveryKey rejects.
export function keysFromPhrase(phrase: string): { master: Uint8Array; keys: DerivedKeys } | null {
  try {
    const master = validateRecoveryKey(normalizePhrase(phrase));
    return { master, keys: deriveKeys(master) };
  } catch {
    return null;
  }
}

// Which of this device's vaults does the phrase open? Checked against the local verifiers,
// entirely in the browser.
export function identifyVaultForPhrase(phrase: string, vaultIds: string[]): string | null {
  const derived = keysFromPhrase(phrase);
  if (!derived) return null;
  for (const id of vaultIds) {
    const v = loadVerifier(id);
    if (v && checkVerifier(v, derived.keys.metadataEncryptionKey)) return id;
  }
  return null;
}
