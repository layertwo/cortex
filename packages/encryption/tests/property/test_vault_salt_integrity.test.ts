/**
 * Property-Based Tests for Vault Salt Integrity
 *
 * These tests verify universal properties of the salt HMAC binding mechanism,
 * ensuring the HMAC correctly detects salt tampering under all inputs.
 *
 * Property 27b: Salt HMAC binds salt to vault master key (REQ 22.6-22.12)
 */

import * as fc from 'fast-check';
import { deriveVaultMasterKey, deriveKeys } from '../../src/lib/key-management';
import { computeSaltHmac, verifySaltHmac } from '../../src/lib/vault-salt-integrity';

const NUM_RUNS = 25;

const arbPassword = fc.string({ minLength: 12, maxLength: 64 });
const arbSalt = fc.uint8Array({ minLength: 16, maxLength: 16 });
const arbMac = fc.uint8Array({ minLength: 32, maxLength: 32 });

describe('Property 27b: Salt HMAC binds salt to vault master key (REQ 22.6-22.12)', () => {
  /**
   * Sub-property 1: verify succeeds on unchanged salt.
   *
   * For any password + salt, the HMAC computed locally verifies as true
   * against itself.
   */
  it('verify succeeds when the salt is unchanged', async () => {
    await fc.assert(
      fc.asyncProperty(arbPassword, arbSalt, async (password, salt) => {
        const masterKey = await deriveVaultMasterKey(password, salt);
        const { saltHmacKey } = deriveKeys(masterKey);
        const mac = computeSaltHmac(saltHmacKey, salt);
        expect(verifySaltHmac(saltHmacKey, salt, mac)).toBe(true);
      }),
      { numRuns: NUM_RUNS }
    );
  });

  /**
   * Sub-property 2: verify fails on replaced salt.
   *
   * For any password + two distinct salts, the HMAC over salt1 does NOT
   * verify against salt2.
   */
  it('verify fails when the salt is replaced (tamper detection)', async () => {
    await fc.assert(
      fc.asyncProperty(arbPassword, arbSalt, arbSalt, async (password, originalSalt, swappedSalt) => {
        fc.pre(!Buffer.from(originalSalt).equals(Buffer.from(swappedSalt)));
        const masterKey = await deriveVaultMasterKey(password, originalSalt);
        const { saltHmacKey } = deriveKeys(masterKey);
        const mac = computeSaltHmac(saltHmacKey, originalSalt);
        expect(verifySaltHmac(saltHmacKey, swappedSalt, mac)).toBe(false);
      }),
      { numRuns: NUM_RUNS }
    );
  });

  /**
   * Sub-property 3: verify fails on tampered HMAC.
   *
   * For any password + salt + random 32-byte buffer that is not the
   * legitimate HMAC, verify returns false.
   */
  it('verify fails when the HMAC is tampered with', async () => {
    await fc.assert(
      fc.asyncProperty(arbPassword, arbSalt, arbMac, async (password, salt, tamperedMac) => {
        const masterKey = await deriveVaultMasterKey(password, salt);
        const { saltHmacKey } = deriveKeys(masterKey);
        const realMac = computeSaltHmac(saltHmacKey, salt);
        fc.pre(!Buffer.from(realMac).equals(Buffer.from(tamperedMac)));
        expect(verifySaltHmac(saltHmacKey, salt, tamperedMac)).toBe(false);
      }),
      { numRuns: NUM_RUNS }
    );
  });
});
