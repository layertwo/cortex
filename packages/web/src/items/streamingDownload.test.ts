import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generateDek, wrapDek, generateNoncePrefix, buildStreamHeader, encryptChunk,
} from '@cortex/encryption';
import type { FileMetadata } from './metadata';

const api = vi.hoisted(() => ({ getDownloadUrl: vi.fn(async () => 'https://s3/get') }));
vi.mock('../api/items', () => api);

import { downloadFileStreaming, type DownloadSink } from './streamingDownload';

const kek = new Uint8Array(32).fill(7);

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

// Build the on-disk chunked object [wrappedDek(97)][header(13)][chunk0…chunkN].
async function buildObject(plaintext: Uint8Array, contentId: string, chunkSize: number): Promise<Uint8Array> {
  const dek = await generateDek();
  const wrappedDek = await wrapDek(dek, kek, contentId);
  const noncePrefix = await generateNoncePrefix();
  const header = buildStreamHeader(chunkSize, noncePrefix);
  const partCount = Math.max(1, Math.ceil(plaintext.length / chunkSize));
  const chunks: Uint8Array[] = [];
  for (let i = 0; i < partCount; i++) {
    chunks.push(encryptChunk(plaintext.slice(i * chunkSize, (i + 1) * chunkSize), {
      dek, noncePrefix, index: i, isFinal: i === partCount - 1, contentId, header,
    }));
  }
  return concat([wrappedDek, header, ...chunks]);
}

// ReadableStream that hands out `readSize` bytes per pull — small value stresses framing.
function streamOf(bytes: Uint8Array, readSize = 7): ReadableStream<Uint8Array> {
  let pos = 0;
  return new ReadableStream({
    pull(c) {
      if (pos >= bytes.length) { c.close(); return; }
      c.enqueue(bytes.slice(pos, pos + readSize));
      pos += readSize;
    },
  });
}

function fakeSink() {
  const writes: Uint8Array[] = [];
  const state = { closed: false, aborted: false };
  const sink: DownloadSink = {
    write: (b) => { writes.push(b); },
    close: () => { state.closed = true; },
    abort: () => { state.aborted = true; },
  };
  return { sink, writes, state };
}

const meta = (contentId: string): FileMetadata =>
  ({ name: 'f.bin', contentType: 'application/octet-stream', size: 0, contentId, streamVersion: 1 });

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('downloadFileStreaming', () => {
  it.each([
    ['empty', 0],
    ['sub-chunk', 3],
    ['exact multiple', 8],
    ['multi-chunk + remainder', 21],
  ])('round-trips %s (chunkSize 4)', async (_label, size) => {
    const plaintext = new Uint8Array(Array.from({ length: size }, (_, i) => (i * 7) & 0xff));
    const contentId = crypto.randomUUID();
    const object = await buildObject(plaintext, contentId, 4);
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(object) })));

    const { sink, writes, state } = fakeSink();
    await downloadFileStreaming('i1', meta(contentId), kek, sink);

    expect(Array.from(concat(writes))).toEqual(Array.from(plaintext));
    expect(state.closed).toBe(true);
    expect(state.aborted).toBe(false);
  });

  it('aborts the sink and throws an integrity error on a tampered chunk', async () => {
    const plaintext = new Uint8Array(20);
    const contentId = crypto.randomUUID();
    const object = await buildObject(plaintext, contentId, 4);
    object[object.length - 1] ^= 0xff; // flip a byte in the final tag
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(object) })));

    const { sink, state } = fakeSink();
    await expect(downloadFileStreaming('i1', meta(contentId), kek, sink))
      .rejects.toThrow(/integrity/i);
    expect(state.aborted).toBe(true);
    expect(state.closed).toBe(false);
  });

  it('throws when the DEK cannot be unwrapped (wrong contentId binding)', async () => {
    const object = await buildObject(new Uint8Array(4), crypto.randomUUID(), 4);
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(object) })));
    const { sink } = fakeSink();
    await expect(downloadFileStreaming('i1', meta('wrong-content-id'), kek, sink)).rejects.toThrow();
  });
});
