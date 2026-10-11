import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  generateDek,
  generateNoncePrefix,
  buildStreamHeader,
  encryptChunk,
  deriveShareKeys,
  computeShareHmac,
  encodeShareBlob,
  wrapDek,
  bytesToBase64,
} from '@cortex/encryption';
import { encryptMetadata } from '../items/metadata';
import { ShareAccess } from './ShareAccess';

const SHARE_ID = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
const PASSWORD = 'Correct-Horse-Battery-9';

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

// ReadableStream that hands out a few bytes per pull.
function streamOf(bytes: Uint8Array, readSize = 7): ReadableStream<Uint8Array> {
  let pos = 0;
  return new ReadableStream({
    pull(c) {
      if (pos >= bytes.length) {
        c.close();
        return;
      }
      c.enqueue(bytes.slice(pos, pos + readSize));
      pos += readSize;
    },
  });
}

describe('ShareAccess', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:x'),
      revokeObjectURL: vi.fn(),
    });
  });

  it('shows an error banner when the URL fragment is missing', () => {
    window.history.pushState({}, '', '/s/abc');
    render(<ShareAccess apiBaseUrl="https://api" />);
    expect(screen.getByRole('alert')).toHaveTextContent(/missing key material/i);
    expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument();
  });

  it('asks for the share password when the URL is complete', async () => {
    window.history.pushState({}, '', '/s/abc#blob');
    render(<ShareAccess apiBaseUrl="https://api" />);
    expect(await screen.findByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /decrypt/i })).toBeDisabled();
  });

  it('unwraps the fragment DEK, decrypts the stored metadata, and downloads', async () => {
    // Build a real share exactly as ShareCreate would.
    const contentId = crypto.randomUUID();
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const shareKeys = await deriveShareKeys(PASSWORD, salt);
    const dek = await generateDek();
    const shareWrappedDek = await wrapDek(dek, shareKeys.encryptionKey);
    const encryptedMetadata = await encryptMetadata(
      { name: 'secret.bin', contentType: 'application/octet-stream', size: 4, contentId, streamVersion: 1 },
      shareKeys.encryptionKey,
    );
    const hmac = computeShareHmac(shareKeys.hmacKey, SHARE_ID, undefined);
    const blob = encodeShareBlob(1, salt, shareWrappedDek, hmac);

    // And the matching chunked-stream object.
    const noncePrefix = await generateNoncePrefix();
    const header = buildStreamHeader(4, noncePrefix);
    const chunk = encryptChunk(new Uint8Array([1, 2, 3, 4]), {
      dek,
      noncePrefix,
      index: 0,
      isFinal: true,
      contentId,
      header,
    });
    const object = concat([header, chunk]);

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (String(url).includes('/v1/shares/')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              itemId: 'i1',
              downloadUrl: 'https://s3/get',
              encryptedMetadata: bytesToBase64(encryptedMetadata),
              expiresAt: null,
            }),
          };
        }
        return { ok: true, body: streamOf(object) };
      }),
    );

    window.history.pushState({}, '', `/s/${SHARE_ID}#${blob}`);
    render(<ShareAccess apiBaseUrl="https://api" />);

    await userEvent.type(await screen.findByLabelText(/password/i), PASSWORD);
    await userEvent.click(screen.getByRole('button', { name: /decrypt/i }));

    expect(await screen.findByText(/decrypted and downloaded/i)).toBeInTheDocument();
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled());
  });

  it('rejects a wrong password without downloading', async () => {
    const contentId = crypto.randomUUID();
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const shareKeys = await deriveShareKeys(PASSWORD, salt);
    const dek = await generateDek();
    const shareWrappedDek = await wrapDek(dek, shareKeys.encryptionKey);
    const encryptedMetadata = await encryptMetadata(
      { name: 'secret.bin', contentType: 'application/octet-stream', size: 4, contentId },
      shareKeys.encryptionKey,
    );
    const hmac = computeShareHmac(shareKeys.hmacKey, SHARE_ID, undefined);
    const blob = encodeShareBlob(1, salt, shareWrappedDek, hmac);

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          itemId: 'i1',
          downloadUrl: 'https://s3/get',
          encryptedMetadata: bytesToBase64(encryptedMetadata),
          expiresAt: null,
        }),
      })),
    );

    window.history.pushState({}, '', `/s/${SHARE_ID}#${blob}`);
    render(<ShareAccess apiBaseUrl="https://api" />);

    await userEvent.type(await screen.findByLabelText(/password/i), 'Wrong-Password-1234');
    await userEvent.click(screen.getByRole('button', { name: /decrypt/i }));

    expect(await screen.findByText(/incorrect password/i)).toBeInTheDocument();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
