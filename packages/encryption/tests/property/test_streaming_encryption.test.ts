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

describe('chunk tamper rejection (server is untrusted)', () => {
  const plaintext = new TextEncoder().encode('a sensitive chunk of bytes');

  test('reorder: a chunk decrypted at the wrong index fails', () => {
    const ct = encryptChunk(plaintext, params({ index: 5 }));
    expect(() => decryptChunk(ct, params({ index: 9 }))).toThrow('authentication failed');
  });

  test('truncate: a non-final chunk read as final fails', () => {
    const ct = encryptChunk(plaintext, params({ index: 2, isFinal: false }));
    expect(() => decryptChunk(ct, params({ index: 2, isFinal: true }))).toThrow('authentication failed');
  });

  test('splice: a chunk from another file (contentId) fails', () => {
    const ct = encryptChunk(plaintext, params({ contentId: 'file-A' }));
    expect(() => decryptChunk(ct, params({ contentId: 'file-B' }))).toThrow('authentication failed');
  });

  test('wrong key: a different DEK fails', () => {
    const ct = encryptChunk(plaintext, params());
    expect(() => decryptChunk(ct, params({ dek: new Uint8Array(32).fill(6) }))).toThrow('authentication failed');
  });

  test('wrong noncePrefix (header tamper) fails', () => {
    const ct = encryptChunk(plaintext, params());
    expect(() => decryptChunk(ct, params({ noncePrefix: new Uint8Array(8).fill(8) }))).toThrow('authentication failed');
  });

  test('header tamper: a different chunkSize in chunk 0 AAD fails', () => {
    // chunkSize lives in the AAD (chunk 0) but NOT the nonce — this proves the
    // header-binding hardening, not just the nonce path.
    const ct = encryptChunk(plaintext, params({ index: 0, header: buildStreamHeader(8 * 1024 * 1024, new Uint8Array(8).fill(7)) }));
    const tampered = buildStreamHeader(4 * 1024 * 1024, new Uint8Array(8).fill(7));
    expect(() => decryptChunk(ct, params({ index: 0, header: tampered }))).toThrow('authentication failed');
  });

  test('bit-flip in ciphertext fails', () => {
    const ct = encryptChunk(plaintext, params());
    ct[0] ^= 0x01;
    expect(() => decryptChunk(ct, params())).toThrow('authentication failed');
  });
});
