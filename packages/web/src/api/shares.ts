import { CreateShareCommand } from '@cortex/client';
import { makeClient } from './client';

export async function createShare(args: {
  itemId: string;
  /** File metadata encrypted under the share key (opaque to the server). */
  encryptedMetadata: Uint8Array;
  /** Unix seconds, or omit for a share that never expires. */
  expiresAt?: number;
}): Promise<{ shareId: string; expiresAt?: number }> {
  const out = await makeClient().send(
    new CreateShareCommand({
      itemId: args.itemId,
      encryptedMetadata: args.encryptedMetadata,
      // The wire is epoch seconds; the SDK serializes a Date.
      ...(args.expiresAt != null ? { expiresAt: new Date(args.expiresAt * 1000) } : {}),
    }),
  );
  if (!out.shareId) throw new Error('createShare: missing shareId');
  return {
    shareId: out.shareId,
    expiresAt: out.expiresAt ? out.expiresAt.getTime() / 1000 : undefined,
  };
}

export class ShareFetchError extends Error {
  constructor(public readonly status: number) {
    super(`Failed to fetch share metadata: ${status}`);
    this.name = 'ShareFetchError';
  }
}

export interface PublicShareMetadata {
  itemId: string;
  downloadUrl: string;
  /** Base64 of the share-key-encrypted file metadata. */
  encryptedMetadata: string;
  /** Unix seconds, or null when the share never expires. */
  expiresAt: number | null;
}

// Anonymous share lookup — no Cognito session, so this is a bare fetch, not the SDK.
export async function getPublicShare(
  apiBaseUrl: string,
  shareId: string,
): Promise<PublicShareMetadata> {
  const res = await fetch(`${apiBaseUrl}/v1/shares/${encodeURIComponent(shareId)}`);
  if (!res.ok) throw new ShareFetchError(res.status);
  const body = (await res.json()) as PublicShareMetadata;
  return {
    itemId: body.itemId,
    downloadUrl: body.downloadUrl,
    encryptedMetadata: body.encryptedMetadata,
    expiresAt: body.expiresAt ?? null,
  };
}
