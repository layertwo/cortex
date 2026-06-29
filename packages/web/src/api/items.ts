import {
  InitiateItemUploadCommand,
  CompleteItemUploadCommand,
  CreateUploadPartUrlsCommand,
  AbortItemUploadCommand,
  ListItemsCommand,
  GetItemDownloadUrlCommand,
  DeleteItemCommand,
  SearchByTagCommand,
  UpdateItemCommand,
} from '@cortex/client';
import type { ItemData } from '@cortex/client';
import { makeClient } from './client';

export type UploadedPart = { partNumber: number; eTag: string };

export async function initiateUpload(args: {
  vaultId: string;
  encryptedMetadata: Uint8Array;
  sizeBytes: number;
  wrappedDek: Uint8Array;
  dekVersion: number;
  encryptedTags?: Uint8Array[];
}): Promise<{ itemId: string; uploadUrl: string; uploadId?: string }> {
  const out = await makeClient().send(new InitiateItemUploadCommand(args));
  if (!out.itemId || !out.uploadUrl) throw new Error('initiateUpload: incomplete response');
  // uploadId is present only when the server chose multipart (sizeBytes > threshold).
  return { itemId: out.itemId, uploadUrl: out.uploadUrl, uploadId: out.uploadId };
}

export async function putToS3(uploadUrl: string, blob: Uint8Array): Promise<string> {
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
  // Multipart completion needs each part's ETag. The browser can only read it if
  // the bucket CORS lists ETag under ExposeHeaders — otherwise this is null.
  const eTag = res.headers.get('ETag') ?? res.headers.get('etag');
  if (!eTag) throw new Error('S3 upload: missing ETag (bucket CORS must expose ETag)');
  return eTag;
}

export async function createUploadPartUrls(
  itemId: string,
  uploadId: string,
  partNumbers: number[],
): Promise<{ partNumber: number; url: string }[]> {
  const out = await makeClient().send(
    new CreateUploadPartUrlsCommand({ itemId, uploadId, partNumbers }),
  );
  return (out.urls ?? []).map((u) => {
    if (u.partNumber == null || !u.url) throw new Error('createUploadPartUrls: incomplete URL');
    return { partNumber: u.partNumber, url: u.url };
  });
}

export async function completeUpload(
  itemId: string,
  opts?: { uploadId: string; parts: UploadedPart[] },
): Promise<void> {
  await makeClient().send(new CompleteItemUploadCommand({ itemId, ...opts }));
}

export async function abortUpload(itemId: string, uploadId: string): Promise<void> {
  await makeClient().send(new AbortItemUploadCommand({ itemId, uploadId }));
}

export async function listItems(vaultId: string): Promise<ItemData[]> {
  const out = await makeClient().send(new ListItemsCommand({ vaultId }));
  return out.items ?? [];
}

export async function searchByTag(vaultId: string, encryptedTag: string): Promise<ItemData[]> {
  const out = await makeClient().send(new SearchByTagCommand({ vaultId, encryptedTag }));
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

// Re-encrypt an existing item's tags: metadata holds the readable tags (FileMetadata),
// encryptedTags are the one-way HMAC search index. Both are rewritten together so the
// search index never drifts from what the user sees.
export async function updateItemTags(
  itemId: string,
  encryptedMetadata: Uint8Array,
  encryptedTags: Uint8Array[],
): Promise<void> {
  await makeClient().send(new UpdateItemCommand({ itemId, encryptedMetadata, encryptedTags }));
}
