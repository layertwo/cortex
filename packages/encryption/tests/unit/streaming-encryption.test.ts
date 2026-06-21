import {
  STREAM_HEADER_SIZE,
  STREAM_VERSION,
  buildStreamHeader,
  parseStreamHeader,
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
