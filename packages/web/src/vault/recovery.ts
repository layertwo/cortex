import {
  validateRecoveryKey,
  deriveKeys,
  secureZeroize,
  zeroizeKeys,
  base64ToBytes,
  type DerivedKeys,
} from '@cortex/encryption';
import { decryptCollectionName } from '../items/collectionMetadata';

// One message for every failure. Which word is wrong, or whether the phrase is well-formed
// but for another vault, is deliberately not disclosed.
export const PHRASE_ERROR =
  "Those words don't open a vault on this device. Check each word and the order, then try again. On a new device, use your recovery kit.";

export function normalizePhrase(input: string | string[]): string {
  const text = Array.isArray(input) ? input.join(' ') : input;
  return text.trim().toLowerCase().split(/\s+/).filter(Boolean).join(' ');
}

// The 24 words are a BIP39 encoding of the vault master key (VMK), so the phrase alone yields
// the same VMK the password unwraps. Null for anything validateRecoveryKey rejects.
export function keysFromPhrase(phrase: string): { vmk: Uint8Array; keys: DerivedKeys } | null {
  try {
    const vmk = validateRecoveryKey(normalizePhrase(phrase));
    return { vmk, keys: deriveKeys(vmk) };
  } catch {
    return null;
  }
}

// Which of this device's vaults does the phrase open? Proven by decrypting each vault's
// server-encrypted name with the phrase's metadata key — entirely in the browser. Vaults with
// no encrypted name cannot be identified this way.
export function identifyVaultForPhrase(
  phrase: string,
  vaults: { vaultId: string; encryptedName?: string }[],
): string | null {
  const derived = keysFromPhrase(phrase);
  if (!derived) return null;
  try {
    for (const v of vaults) {
      if (!v.encryptedName) continue;
      try {
        decryptCollectionName(base64ToBytes(v.encryptedName), derived.keys.metadataEncryptionKey);
        return v.vaultId;
      } catch {
        // Not this vault.
      }
    }
    return null;
  } finally {
    // The phrase's VMK and derived keys are not kept past this check.
    secureZeroize(derived.vmk);
    zeroizeKeys(derived.keys);
  }
}
