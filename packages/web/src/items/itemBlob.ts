// ponytail: fixed 97-byte prefix assumes HMAC binding is always on. If an unbound
// (65-byte) path is ever added, switch to a length-prefixed format instead.
export const WRAPPED_DEK_SIZE = 97;

export function encodeItemBlob(wrappedDek: Uint8Array, ciphertext: Uint8Array): Uint8Array {
  if (wrappedDek.length !== WRAPPED_DEK_SIZE) {
    throw new Error(`Invalid wrapped DEK size: expected ${WRAPPED_DEK_SIZE}, got ${wrappedDek.length}`);
  }
  const blob = new Uint8Array(WRAPPED_DEK_SIZE + ciphertext.length);
  blob.set(wrappedDek, 0);
  blob.set(ciphertext, WRAPPED_DEK_SIZE);
  return blob;
}

export function decodeItemBlob(blob: Uint8Array): { wrappedDek: Uint8Array; ciphertext: Uint8Array } {
  if (blob.length < WRAPPED_DEK_SIZE) {
    throw new Error(`Item blob too short: ${blob.length} < ${WRAPPED_DEK_SIZE}`);
  }
  return {
    wrappedDek: blob.slice(0, WRAPPED_DEK_SIZE),
    ciphertext: blob.slice(WRAPPED_DEK_SIZE),
  };
}
