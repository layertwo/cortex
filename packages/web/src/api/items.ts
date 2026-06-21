import {
  InitiateItemUploadCommand,
  CompleteItemUploadCommand,
  ListItemsCommand,
  GetItemDownloadUrlCommand,
  DeleteItemCommand,
} from '@cortex/client';
import type { ItemData } from '@cortex/client';
import { makeClient } from './client';

export async function initiateUpload(args: {
  vaultId: string;
  encryptedMetadata: Uint8Array;
  sizeBytes: number;
}): Promise<{ itemId: string; uploadUrl: string }> {
  const out = await makeClient().send(new InitiateItemUploadCommand(args));
  if (!out.itemId || !out.uploadUrl) throw new Error('initiateUpload: incomplete response');
  return { itemId: out.itemId, uploadUrl: out.uploadUrl };
}

export async function putToS3(uploadUrl: string, blob: Uint8Array): Promise<void> {
  // Raw PUT to the presigned URL — not a Smithy op, so no Authorization header
  // (the URL carries auth). The body is opaque ciphertext → octet-stream; the
  // real MIME lives only in the encrypted metadata.
  const res = await fetch(uploadUrl, {
    method: 'PUT',
    // ponytail: cast needed because lib.dom's BodyInit rejects Uint8Array<ArrayBufferLike>
    // (it wants an ArrayBuffer-backed view). Runtime body is still the exact blob.
    body: blob as BodyInit,
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  if (!res.ok) throw new Error(`S3 upload failed: ${res.status}`);
}

export async function completeUpload(itemId: string): Promise<void> {
  await makeClient().send(new CompleteItemUploadCommand({ itemId }));
}

export async function listItems(vaultId: string): Promise<ItemData[]> {
  const out = await makeClient().send(new ListItemsCommand({ vaultId }));
  return out.items ?? [];
}

export async function getDownloadUrl(itemId: string): Promise<string> {
  const out = await makeClient().send(new GetItemDownloadUrlCommand({ itemId }));
  if (!out.downloadUrl) throw new Error('getDownloadUrl: missing download URL');
  return out.downloadUrl;
}

export async function deleteItem(itemId: string): Promise<void> {
  await makeClient().send(new DeleteItemCommand({ itemId }));
}
