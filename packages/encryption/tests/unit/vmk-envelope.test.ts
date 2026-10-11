/**
 * Unit tests for Vault Master Key (VMK) envelope wrapping.
 */

import {
  generateVaultMasterKey,
  wrapVmk,
  unwrapVmk,
  DekUnwrapError,
} from '../../src/lib/envelope-encryption';

describe('VMK envelope wrapping', () => {
  it('round-trips a VMK and rejects a wrong wrapping key', async () => {
    const vmk = await generateVaultMasterKey();
    const key = new Uint8Array(32).fill(4);
    const wrapped = await wrapVmk(vmk, key);
    expect(wrapped.length).toBe(61);
    expect(wrapped[0]).toBe(0x01);
    expect(unwrapVmk(wrapped, key)).toEqual(vmk);
    expect(() => unwrapVmk(wrapped, new Uint8Array(32).fill(5))).toThrow(DekUnwrapError);
  });

  it('rejects a wrong length and an unsupported version', async () => {
    const vmk = await generateVaultMasterKey();
    const key = new Uint8Array(32).fill(4);
    const wrapped = await wrapVmk(vmk, key);

    expect(() => unwrapVmk(wrapped.slice(0, 60), key)).toThrow(
      expect.objectContaining({ code: 'CORRUPTED_DEK' }),
    );

    const badVersion = wrapped.slice();
    badVersion[0] = 0x7f;
    expect(() => unwrapVmk(badVersion, key)).toThrow(
      expect.objectContaining({ code: 'WRONG_KEK_VERSION' }),
    );
  });
});
