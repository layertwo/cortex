import fc from 'fast-check';
import {
  encryptChunk,
  decryptChunk,
  buildStreamHeader,
  type ChunkParams,
} from '../../src/lib/streaming-encryption';

function params(over: Partial<ChunkParams> = {}): ChunkParams {
  return {
    dek: new Uint8Array(32).fill(5),
    noncePrefix: new Uint8Array(8).fill(7),
    index: 0,
    isFinal: false,
    contentId: 'content-1',
    header: buildStreamHeader(8 * 1024 * 1024, new Uint8Array(8).fill(7)),
    ...over,
  };
}

describe('chunk encrypt/decrypt', () => {
  test('round-trips a chunk of any size at any index', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uint8Array({ minLength: 0, maxLength: 4096 }),
        fc.integer({ min: 0, max: 1000 }),
        fc.boolean(),
        async (plaintext, index, isFinal) => {
          const p = params({ index, isFinal });
          const ct = encryptChunk(plaintext, p);
          expect(ct.length).toBe(plaintext.length + 16); // tag appended
          if (plaintext.length > 0) expect(ct.slice(0, plaintext.length)).not.toEqual(plaintext);
          expect(decryptChunk(ct, p)).toEqual(plaintext);
        },
      ),
      { numRuns: 100 },
    );
  });

  test('rejects a DEK of the wrong size', () => {
    expect(() => encryptChunk(new Uint8Array(1), params({ dek: new Uint8Array(16) }))).toThrow('DEK');
  });
});
