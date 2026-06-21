/**
 * Streaming chunked AEAD for large files.
 *
 * A file is split into fixed-size chunks, each sealed with ChaCha20-Poly1305
 * under a per-chunk nonce (noncePrefix ‖ counter) and AAD that binds the file
 * (contentId), the position (index), and stream finality (isFinal). This makes
 * reorder, truncation, and cross-file splice fail on decrypt — the server is
 * untrusted in the zero-knowledge model.
 *
 * On-disk layout: [wrappedDek(97)][header(13)][chunk0][chunk1]...[chunkN]
 * Header: [version(1)][chunkSize uint32_be(4)][noncePrefix(8)]
 */
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { NONCE_SIZE, TAG_SIZE, KEY_SIZE } from './encryption';

export const STREAM_VERSION = 0x01;
export const NONCE_PREFIX_SIZE = 8;
export const STREAM_HEADER_SIZE = 1 + 4 + NONCE_PREFIX_SIZE; // 13
export const DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024;

const getRandomBytes = async (size: number): Promise<Uint8Array> => {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    return crypto.getRandomValues(new Uint8Array(size));
  }
  try {
    const { randomBytes } = await import('node:crypto');
    return new Uint8Array(randomBytes(size));
  } catch {
    throw new Error('No secure random number generator available');
  }
};

const dv = (a: Uint8Array) => new DataView(a.buffer, a.byteOffset, a.byteLength);

export function buildStreamHeader(chunkSize: number, noncePrefix: Uint8Array): Uint8Array {
  if (noncePrefix.length !== NONCE_PREFIX_SIZE) {
    throw new Error(`Invalid nonce prefix size: expected ${NONCE_PREFIX_SIZE}, got ${noncePrefix.length}`);
  }
  if (!Number.isInteger(chunkSize) || chunkSize <= 0 || chunkSize > 0xffffffff) {
    throw new Error(`Invalid chunk size: ${chunkSize}`);
  }
  const header = new Uint8Array(STREAM_HEADER_SIZE);
  header[0] = STREAM_VERSION;
  dv(header).setUint32(1, chunkSize, false);
  header.set(noncePrefix, 5);
  return header;
}

export function parseStreamHeader(
  header: Uint8Array,
): { version: number; chunkSize: number; noncePrefix: Uint8Array } {
  if (header.length < STREAM_HEADER_SIZE) {
    throw new Error(`Stream header too short: expected ${STREAM_HEADER_SIZE}, got ${header.length}`);
  }
  const version = header[0];
  if (version !== STREAM_VERSION) {
    throw new Error(`Unsupported stream version: ${version}`);
  }
  const chunkSize = dv(header).getUint32(1, false);
  const noncePrefix = header.slice(5, 5 + NONCE_PREFIX_SIZE);
  return { version, chunkSize, noncePrefix };
}

export async function generateNoncePrefix(): Promise<Uint8Array> {
  return getRandomBytes(NONCE_PREFIX_SIZE);
}

export function deriveChunkNonce(noncePrefix: Uint8Array, index: number): Uint8Array {
  if (noncePrefix.length !== NONCE_PREFIX_SIZE) {
    throw new Error(`Invalid nonce prefix size: expected ${NONCE_PREFIX_SIZE}, got ${noncePrefix.length}`);
  }
  if (!Number.isInteger(index) || index < 0 || index > 0xffffffff) {
    throw new Error(`Chunk index out of range: ${index}`);
  }
  const nonce = new Uint8Array(NONCE_SIZE); // 12
  nonce.set(noncePrefix, 0);
  dv(nonce).setUint32(NONCE_PREFIX_SIZE, index, false);
  return nonce;
}

export function buildChunkAad(
  contentId: string,
  index: number,
  isFinal: boolean,
  header: Uint8Array,
): Uint8Array {
  const idBytes = new TextEncoder().encode(contentId);
  const prefix = index === 0 ? header : new Uint8Array(0);
  const aad = new Uint8Array(prefix.length + idBytes.length + 4 + 1);
  let o = 0;
  aad.set(prefix, o);
  o += prefix.length;
  aad.set(idBytes, o);
  o += idBytes.length;
  dv(aad).setUint32(o, index, false);
  o += 4;
  aad[o] = isFinal ? 0x01 : 0x00;
  return aad;
}
