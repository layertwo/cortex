/**
 * Unit tests for wrapped-DEK versioning (spec 6.15 / REQ-32).
 */

import {
  wrapDek,
  unwrapDek,
  getWrappedDekVersion,
  isDekVersionDeprecated,
  CURRENT_DEK_VERSION,
  SUPPORTED_DEK_VERSIONS,
  DEPRECATED_DEK_VERSIONS,
  DekUnwrapError,
} from '../../src/lib/envelope-encryption';

const KEK = new Uint8Array(32).fill(5);
const DEK = new Uint8Array(32).fill(7);

describe('DEK wrapping-format versioning', () => {
  it('stamps CURRENT_DEK_VERSION on new wraps and reads it back', async () => {
    const wrapped = await wrapDek(DEK, KEK);

    expect(getWrappedDekVersion(wrapped)).toBe(CURRENT_DEK_VERSION);
    expect(SUPPORTED_DEK_VERSIONS).toContain(CURRENT_DEK_VERSION);
  });

  it('unwraps a DEK wrapped with a supported version', async () => {
    const wrapped = await wrapDek(DEK, KEK);

    expect(unwrapDek(wrapped, KEK)).toEqual(DEK);
  });

  it('refuses an unsupported version', async () => {
    const wrapped = await wrapDek(DEK, KEK);
    wrapped[0] = 0x7f; // outside SUPPORTED_DEK_VERSIONS

    try {
      unwrapDek(wrapped, KEK);
      throw new Error('expected unwrapDek to throw');
    } catch (err) {
      expect(err).toBeInstanceOf(DekUnwrapError);
      expect((err as DekUnwrapError).code).toBe('WRONG_KEK_VERSION');
      expect((err as Error).message).toMatch(/unsupported/i);
    }
  });

  it('refuses a deprecated version and points at migration', async () => {
    const wrapped = await wrapDek(DEK, KEK);
    // No versions are deprecated yet; stage one to exercise the refusal branch.
    (DEPRECATED_DEK_VERSIONS as number[]).push(0x99);
    try {
      wrapped[0] = 0x99;
      expect(isDekVersionDeprecated(0x99)).toBe(true);
      expect(() => unwrapDek(wrapped, KEK)).toThrow(/deprecated/i);
    } finally {
      (DEPRECATED_DEK_VERSIONS as number[]).pop();
    }
  });

  it('treats supported versions as not deprecated', () => {
    expect(isDekVersionDeprecated(CURRENT_DEK_VERSION)).toBe(false);
    expect(isDekVersionDeprecated(0x7f)).toBe(false);
  });
});
