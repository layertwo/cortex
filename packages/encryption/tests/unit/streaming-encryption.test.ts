import {
  STREAM_HEADER_SIZE,
  STREAM_VERSION,
  buildStreamHeader,
  parseStreamHeader,
  generateNoncePrefix,
  deriveChunkNonce,
  NONCE_PREFIX_SIZE,
} from '../../src/lib/streaming-encryption';

describe('stream header codec', () => {
  const prefix = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);

  it('round-trips version, chunkSize, noncePrefix', () => {
    const header = buildStreamHeader(8 * 1024 * 1024, prefix);
    expect(header.length).toBe(STREAM_HEADER_SIZE);
    expect(header[0]).toBe(STREAM_VERSION);
    const parsed = parseStreamHeader(header);
    expect(parsed.version).toBe(STREAM_VERSION);
    expect(parsed.chunkSize).toBe(8 * 1024 * 1024);
    expect(parsed.noncePrefix).toEqual(prefix);
  });

  it('encodes chunkSize big-endian', () => {
    const header = buildStreamHeader(0x01020304, prefix);
    expect(Array.from(header.slice(1, 5))).toEqual([0x01, 0x02, 0x03, 0x04]);
  });

  it('rejects a wrong-size nonce prefix', () => {
    expect(() => buildStreamHeader(1024, new Uint8Array(4))).toThrow('nonce prefix');
  });

  it('rejects a header that is too short', () => {
    expect(() => parseStreamHeader(new Uint8Array(STREAM_HEADER_SIZE - 1))).toThrow('too short');
  });

  it('rejects an unsupported version', () => {
    const header = buildStreamHeader(1024, prefix);
    header[0] = 0x99;
    expect(() => parseStreamHeader(header)).toThrow('version');
  });
});

describe('chunk nonce derivation', () => {
  const prefix = new Uint8Array([10, 11, 12, 13, 14, 15, 16, 17]);

  it('generates an 8-byte prefix', async () => {
    expect((await generateNoncePrefix()).length).toBe(NONCE_PREFIX_SIZE);
  });

  it('produces a 12-byte nonce = prefix ‖ uint32_be(index)', () => {
    const nonce = deriveChunkNonce(prefix, 0x00000005);
    expect(nonce.length).toBe(12);
    expect(Array.from(nonce.slice(0, 8))).toEqual(Array.from(prefix));
    expect(Array.from(nonce.slice(8))).toEqual([0x00, 0x00, 0x00, 0x05]);
  });

  it('is distinct per index', () => {
    expect(deriveChunkNonce(prefix, 1)).not.toEqual(deriveChunkNonce(prefix, 2));
  });

  it('rejects a wrong-size prefix and out-of-range index', () => {
    expect(() => deriveChunkNonce(new Uint8Array(4), 0)).toThrow('nonce prefix');
    expect(() => deriveChunkNonce(prefix, -1)).toThrow('index');
    expect(() => deriveChunkNonce(prefix, 0x1_0000_0000)).toThrow('index');
  });
});
