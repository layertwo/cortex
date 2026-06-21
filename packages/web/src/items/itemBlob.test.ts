import { describe, it, expect } from 'vitest';
import { encodeItemBlob, decodeItemBlob, WRAPPED_DEK_SIZE } from './itemBlob';

describe('item blob codec', () => {
  it('round-trips wrappedDek + ciphertext', () => {
    const wrappedDek = new Uint8Array(WRAPPED_DEK_SIZE).fill(7);
    const ciphertext = new Uint8Array([1, 2, 3, 4, 5]);
    const blob = encodeItemBlob(wrappedDek, ciphertext);
    expect(blob.length).toBe(WRAPPED_DEK_SIZE + 5);
    const out = decodeItemBlob(blob);
    expect(out.wrappedDek).toEqual(wrappedDek);
    expect(out.ciphertext).toEqual(ciphertext);
  });

  it('rejects a wrong-size wrappedDek on encode', () => {
    expect(() => encodeItemBlob(new Uint8Array(10), new Uint8Array(1))).toThrow('wrapped DEK');
  });

  it('rejects a blob too short to hold a wrapped DEK', () => {
    expect(() => decodeItemBlob(new Uint8Array(WRAPPED_DEK_SIZE - 1))).toThrow('too short');
  });
});
