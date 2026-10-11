/**
 * Property-Based Tests for VMK envelope wrapping.
 */

import * as fc from 'fast-check';
import {
  wrapVmk,
  unwrapVmk,
  DekUnwrapError,
} from '../../src/lib/envelope-encryption';

describe('VMK envelope property tests', () => {
  it('Property: VMK wrap/unwrap round-trips; a wrong wrapping key fails', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 32, maxLength: 32 }),
        fc.uint8Array({ minLength: 32, maxLength: 32 }),
        fc.uint8Array({ minLength: 32, maxLength: 32 }),
        async (vmk, key, other) => {
          const wrapped = await wrapVmk(vmk, key);
          expect(unwrapVmk(wrapped, key)).toEqual(vmk);
          if (Buffer.from(key).equals(Buffer.from(other))) return true;
          expect(() => unwrapVmk(wrapped, other)).toThrow(DekUnwrapError);
        },
      ),
      { numRuns: 100 },
    );
  });
});
