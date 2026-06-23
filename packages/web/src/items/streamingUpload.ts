import {
  generateDek,
  wrapDek,
  generateNoncePrefix,
  buildStreamHeader,
  encryptChunk,
  DEFAULT_CHUNK_SIZE,
  STREAM_HEADER_SIZE,
  STREAM_VERSION,
} from '@cortex/encryption';
import { WRAPPED_DEK_SIZE } from './itemBlob';
import { encryptMetadata, type FileMetadata } from './metadata';
import {
  initiateUpload,
  putToS3,
  createUploadPartUrls,
  completeUpload,
  abortUpload,
  type UploadedPart,
} from '../api/items';

const TAG_SIZE = 16;
const PART_URL_BATCH = 10;
const PART_RETRIES = 3;

export interface VaultKeys {
  vaultId: string;
  kek: Uint8Array;
  metadataKey: Uint8Array;
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

async function withRetry<T>(fn: () => Promise<T>, retries = PART_RETRIES): Promise<T> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (attempt < retries) await new Promise((r) => setTimeout(r, 200 * 2 ** attempt));
    }
  }
  throw lastErr;
}

/**
 * Encrypt a file as a chunked stream and upload it.
 *
 * The on-disk format is always the 2.5a chunked layout
 * `[wrappedDek(97)][header(13)][chunk0…chunkN]`. Transport branches on whether
 * the server returned a multipart `uploadId`: absent → one presigned PUT;
 * present → one S3 part per chunk (1-based) with batched part URLs and per-part
 * retry, aborting on fatal failure. Multipart memory stays O(chunkSize).
 */
export async function uploadFileStreaming(
  file: File,
  keys: VaultKeys,
  onProgress?: (fraction: number) => void,
  opts?: { chunkSize?: number }, // ponytail: chunkSize is in the header anyway; override is test-only
): Promise<void> {
  const chunkSize = opts?.chunkSize ?? DEFAULT_CHUNK_SIZE;
  const plaintextSize = file.size;
  const partCount = Math.max(1, Math.ceil(plaintextSize / chunkSize));
  const sizeBytes = WRAPPED_DEK_SIZE + STREAM_HEADER_SIZE + plaintextSize + TAG_SIZE * partCount;

  const contentId = crypto.randomUUID();
  const dek = await generateDek();
  try {
    const wrappedDek = await wrapDek(dek, keys.kek, contentId);
    const noncePrefix = await generateNoncePrefix();
    const header = buildStreamHeader(chunkSize, noncePrefix);

    const metadata: FileMetadata = {
      name: file.name,
      contentType: file.type || 'application/octet-stream',
      size: plaintextSize,
      contentId,
      streamVersion: STREAM_VERSION,
    };
    const encryptedMetadata = await encryptMetadata(metadata, keys.metadataKey);

    const { itemId, uploadUrl, uploadId } = await initiateUpload({
      vaultId: keys.vaultId,
      encryptedMetadata,
      sizeBytes,
    });

    // Read + encrypt one chunk lazily; part 1 prepends wrappedDek + header.
    const encryptPart = async (index: number): Promise<Uint8Array> => {
      const start = index * chunkSize;
      const end = Math.min(start + chunkSize, plaintextSize);
      const plain = new Uint8Array(await file.slice(start, end).arrayBuffer());
      const ct = encryptChunk(plain, {
        dek,
        noncePrefix,
        index,
        isFinal: index === partCount - 1,
        contentId,
        header,
      });
      return index === 0 ? concat([wrappedDek, header, ct]) : ct;
    };

    let uploaded = 0;
    const bump = (n: number) => {
      uploaded += n;
      onProgress?.(uploaded / sizeBytes);
    };

    if (!uploadId) {
      // Single-PUT: assemble the whole object (≤ threshold) and PUT once.
      const blobs: Uint8Array[] = [];
      for (let i = 0; i < partCount; i++) blobs.push(await encryptPart(i));
      const blob = concat(blobs);
      await putToS3(uploadUrl, blob);
      bump(blob.length);
      await completeUpload(itemId);
      return;
    }

    // Multipart: one S3 part per chunk (1-based), batched part URLs, per-part retry.
    try {
      const parts: UploadedPart[] = [];
      for (let base = 1; base <= partCount; base += PART_URL_BATCH) {
        const nums: number[] = [];
        for (let n = base; n < base + PART_URL_BATCH && n <= partCount; n++) nums.push(n);
        const urls = await createUploadPartUrls(itemId, uploadId, nums);
        const urlByPart = new Map(urls.map((u) => [u.partNumber, u.url]));
        for (const partNumber of nums) {
          const body = await encryptPart(partNumber - 1);
          const url = urlByPart.get(partNumber);
          if (!url) throw new Error(`Missing part URL for part ${partNumber}`);
          const eTag = await withRetry(() => putToS3(url, body));
          parts.push({ partNumber, eTag });
          bump(body.length);
        }
      }
      await completeUpload(itemId, { uploadId, parts });
    } catch (err) {
      await abortUpload(itemId, uploadId).catch(() => {}); // best-effort cleanup
      throw err;
    }
  } finally {
    dek.fill(0);
  }
}
