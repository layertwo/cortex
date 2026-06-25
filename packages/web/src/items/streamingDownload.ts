import {
  unwrapDek,
  parseStreamHeader,
  decryptChunk,
  STREAM_HEADER_SIZE,
  TAG_SIZE,
} from '@cortex/encryption';
import { WRAPPED_DEK_SIZE } from './itemBlob';
import { type FileMetadata } from './metadata';
import { getDownloadUrl } from '../api/items';

const PREFIX_SIZE = WRAPPED_DEK_SIZE + STREAM_HEADER_SIZE; // 97 + 13 = 110

export interface DownloadSink {
  write(bytes: Uint8Array): void | Promise<void>;
  close(): void | Promise<void>;
  abort(): void | Promise<void>;
}

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

// --- tier 3: in-memory blob (works everywhere; not for multi-GB files) ---
export function blobSink(name: string, contentType: string): DownloadSink {
  const parts: Uint8Array[] = [];
  return {
    write(b) {
      parts.push(b);
    },
    close() {
      const url = URL.createObjectURL(new Blob(parts as BlobPart[], { type: contentType }));
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    },
    abort() {
      parts.length = 0;
    },
  };
}

// --- tier 1: File System Access API — streams straight to the user's chosen file ---
type SaveHandle = {
  createWritable: () => Promise<{
    write: (b: Uint8Array) => void | Promise<void>;
    close: () => void | Promise<void>;
    abort: () => void | Promise<void>;
  }>;
};
type WithPicker = { showSaveFilePicker: (o: { suggestedName: string }) => Promise<SaveHandle> };

async function fsAccessSink(name: string): Promise<DownloadSink> {
  // Must be reached within the user gesture; the caller awaits pickSink first.
  const handle = await (globalThis as unknown as WithPicker).showSaveFilePicker({ suggestedName: name });
  const writable = await handle.createWritable();
  return {
    write: (b) => writable.write(b),
    close: () => writable.close(),
    abort: () => writable.abort(),
  };
}

// Caller picks the sink BEFORE any other await (user-activation for showSaveFilePicker).
export async function pickSink(name: string, contentType: string): Promise<DownloadSink> {
  // Tier 1: File System Access (true streaming to disk, Chromium desktop).
  if (typeof (globalThis as { showSaveFilePicker?: unknown }).showSaveFilePicker === 'function') {
    return fsAccessSink(name);
  }
  // Tier 3: in-memory blob fallback. (Tier 2 OPFS-in-Worker deferred — see plan.)
  return blobSink(name, contentType);
}

async function readExactly(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  n: number,
): Promise<{ head: Uint8Array; rest: Uint8Array }> {
  const bufs: Uint8Array[] = [];
  let have = 0;
  while (have < n) {
    const { value, done } = await reader.read();
    if (done) throw new Error('Stream ended before the stream header was read');
    bufs.push(value);
    have += value.length;
  }
  const all = concat(bufs);
  return { head: all.slice(0, n), rest: all.slice(n) };
}

/**
 * Stream-decrypt a chunked object straight to a sink.
 *
 * Reads the `wrappedDek(97)+header(13)` prefix off the response stream, unwraps
 * the DEK, then frames the rest into `chunkSize+16` blocks. A block is emitted
 * non-final only while strictly more than one block is buffered; whatever remains
 * at EOF is decrypted with `isFinal=true` — so a dropped tail makes a non-final
 * chunk read as final and fail authentication. Any decrypt failure discards the
 * partial sink. Memory stays O(chunkSize).
 */
export async function downloadFileStreaming(
  itemId: string,
  meta: FileMetadata,
  kek: Uint8Array,
  sink: DownloadSink,
): Promise<void> {
  const url = await getDownloadUrl(itemId);
  const res = await fetch(url);
  if (!res.ok || !res.body) throw new Error(`Download failed: ${(res as Response).status ?? 'no body'}`);
  const reader = res.body.getReader();

  // Prefix: wrappedDek(97) + header(13). `rest` is the start of chunk 0.
  const { head, rest } = await readExactly(reader, PREFIX_SIZE);
  const wrappedDek = head.slice(0, WRAPPED_DEK_SIZE);
  const header = head.slice(WRAPPED_DEK_SIZE);
  const { chunkSize, noncePrefix } = parseStreamHeader(header);
  const dek = unwrapDek(wrappedDek, kek, meta.contentId); // throws DekUnwrapError on wrong key/tamper

  const blockSize = chunkSize + TAG_SIZE;
  let buf = rest;
  let index = 0;
  // ponytail: one broad catch maps loop failures to the integrity message. The
  // dominant failure here is a decryptChunk auth failure; a rare sink.write error
  // (e.g. disk full) is mislabeled "integrity". Split the try if that matters.
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (value && value.length) buf = concat([buf, value]);
      // Emit every block we KNOW is non-final: strictly more than one block buffered.
      while (buf.length > blockSize) {
        const block = buf.slice(0, blockSize);
        buf = buf.slice(blockSize);
        await sink.write(decryptChunk(block, {
          dek, noncePrefix, index, isFinal: false, contentId: meta.contentId, header,
        }));
        index += 1;
      }
      if (done) break;
    }
    // Whatever remains is the final block (truncation makes a non-final chunk land here → reject).
    await sink.write(decryptChunk(buf, {
      dek, noncePrefix, index, isFinal: true, contentId: meta.contentId, header,
    }));
    await sink.close();
  } catch {
    await Promise.resolve(sink.abort()).catch(() => {});
    throw new Error('File failed integrity check');
  } finally {
    dek.fill(0);
  }
}
