/**
 * Wiring test for task 6.2: deriveKeys() must produce the Key Encryption Key (KEK)
 * that envelope encryption (wrapDek/unwrapDek) consumes.
 *
 * Under envelope encryption each file is encrypted with a per-file random DEK, and
 * that DEK is wrapped by a vault-level KEK. Before this fix deriveKeys() produced a
 * `dataEncryptionKey` (context "cortex-data-encryption-v1") that nothing consumed,
 * while wrapDek/unwrapDek took a `kek` parameter that deriveKeys never produced.
 * This test proves the loop is closed: the KEK from deriveKeys() actually wraps and
 * unwraps a file's DEK.
 */

import { deriveKeys } from '../../src/lib/key-management';
import { encryptFileWithDek, decryptFileWithDek } from '../../src/lib/envelope-encryption';

describe('KEK wiring (task 6.2)', () => {
  const mockMasterKey = (): Uint8Array => {
    const k = new Uint8Array(32);
    crypto.getRandomValues(k);
    return k;
  };

  it('exposes a 32-byte keyEncryptionKey', () => {
    const keys = deriveKeys(mockMasterKey());
    expect(keys.keyEncryptionKey).toBeInstanceOf(Uint8Array);
    expect(keys.keyEncryptionKey.length).toBe(32);
  });

  it('the derived KEK round-trips a file through envelope encryption', async () => {
    const keys = deriveKeys(mockMasterKey());
    const content = new TextEncoder().encode('zero-knowledge file payload');

    const { encryptedContent, wrappedDek } = await encryptFileWithDek(
      content,
      keys.keyEncryptionKey,
      'file-123'
    );
    const decrypted = decryptFileWithDek(
      encryptedContent,
      wrappedDek,
      keys.keyEncryptionKey,
      'file-123'
    );

    expect(decrypted).toEqual(content);
  });
});
