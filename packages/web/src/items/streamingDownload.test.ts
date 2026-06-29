import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generateDek, wrapDek, generateNoncePrefix, buildStreamHeader, encryptChunk,
} from '@cortex/encryption';
import type { FileMetadata } from './metadata';

const api = vi.hoisted(() => ({ getDownloadUrl: vi.fn(async () => 'https://s3/get') }));
vi.mock('../api/items', () => api);

import { downloadFileStreaming, pickSink, type DownloadSink } from './streamingDownload';

const kek = new Uint8Array(32).fill(7);

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

// Build the on-disk chunked object [header(13)][chunk0…chunkN]; the wrapped DEK
// now travels separately (via the item record), returned here for the caller to pass in.
async function buildObject(plaintext: Uint8Array, contentId: string, chunkSize: number): Promise<{ object: Uint8Array; wrappedDek: Uint8Array }> {
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
  return { object: concat([header, ...chunks]), wrappedDek };
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
    const { object, wrappedDek } = await buildObject(plaintext, contentId, 4);
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(object) })));

    const { sink, writes, state } = fakeSink();
    await downloadFileStreaming('i1', meta(contentId), wrappedDek, kek, sink);

    expect(Array.from(concat(writes))).toEqual(Array.from(plaintext));
    expect(state.closed).toBe(true);
    expect(state.aborted).toBe(false);
  });

  it('aborts the sink and throws an integrity error on a tampered chunk', async () => {
    const plaintext = new Uint8Array(20);
    const contentId = crypto.randomUUID();
    const { object, wrappedDek } = await buildObject(plaintext, contentId, 4);
    object[object.length - 1] ^= 0xff; // flip a byte in the final tag
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(object) })));

    const { sink, state } = fakeSink();
    await expect(downloadFileStreaming('i1', meta(contentId), wrappedDek, kek, sink))
      .rejects.toThrow(/integrity/i);
    expect(state.aborted).toBe(true);
    expect(state.closed).toBe(false);
  });

  it('throws when the DEK cannot be unwrapped (wrong contentId binding)', async () => {
    const { object, wrappedDek } = await buildObject(new Uint8Array(4), crypto.randomUUID(), 4);
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(object) })));
    const { sink } = fakeSink();
    await expect(downloadFileStreaming('i1', meta('wrong-content-id'), wrappedDek, kek, sink)).rejects.toThrow();
  });
});

describe('pickSink capability detection', () => {
  it('uses the File System Access API when available, streaming write→close', async () => {
    const written: Uint8Array[] = [];
    const writable = { write: vi.fn((b: Uint8Array) => { written.push(b); }), close: vi.fn(), abort: vi.fn() };
    const handle = { createWritable: vi.fn(async () => writable) };
    const showSaveFilePicker = vi.fn(async () => handle);
    vi.stubGlobal('showSaveFilePicker', showSaveFilePicker);

    const sink = await pickSink('photo.jpg', 'image/jpeg');
    expect(showSaveFilePicker).toHaveBeenCalledWith({ suggestedName: 'photo.jpg' });
    await sink.write(new Uint8Array([1, 2]));
    await sink.close();
    expect(written).toEqual([new Uint8Array([1, 2])]);
    expect(writable.close).toHaveBeenCalled();
  });

  it('falls back to an in-memory blob when the API is absent', async () => {
    vi.stubGlobal('showSaveFilePicker', undefined);
    const createObjectURL = vi.fn(() => 'blob:x');
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL: vi.fn() });

    const sink = await pickSink('a.bin', 'application/octet-stream');
    sink.write(new Uint8Array([9]));
    await sink.close(); // blob sink triggers an <a download> via an object URL
    expect(createObjectURL).toHaveBeenCalled();
  });
});
