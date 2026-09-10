import { useState, useEffect, useCallback, useRef } from 'react';
import {
  deriveShareKeys,
  verifyShareHmac,
  decodeShareBlob,
  unwrapDek,
  DekUnwrapError,
} from '@cortex/encryption';
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Spinner } from '@astryxdesign/core/Spinner';
import { VStack } from '@astryxdesign/core/VStack';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';

const NONCE_SIZE = 12;
const MAX_FAILURES_BEFORE_BACKOFF = 3;
const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

interface ShareAccessProps {
  apiBaseUrl: string;
}

interface ShareMetadata {
  itemId: string;
  wrappedDek: string; // base64
  fileName: string;
  contentType: string;
  expiresAt: number | null;
  downloadUrl: string;
}

type AccessState =
  | { step: 'loading' }
  | { step: 'error'; message: string }
  | { step: 'password' }
  | { step: 'decrypting' }
  | { step: 'done'; fileName: string };

export function ShareAccess({ apiBaseUrl }: ShareAccessProps) {
  const [state, setState] = useState<AccessState>({ step: 'loading' });
  const [password, setPassword] = useState('');
  const [failureCount, setFailureCount] = useState(0);
  const [backoffUntil, setBackoffUntil] = useState<number | null>(null);
  const shareIdRef = useRef('');
  const blobRef = useRef('');

  // Extract shareId from pathname and blob from fragment on mount
  useEffect(() => {
    const pathname = window.location.pathname;
    const match = pathname.match(/^\/s\/([^/]+)/);
    if (!match) {
      setState({
        step: 'error',
        message: 'Invalid share URL: could not extract share ID.',
      });
      return;
    }

    const shareId = match[1];
    const fragment = window.location.hash.slice(1); // remove leading #
    if (!fragment) {
      setState({
        step: 'error',
        message:
          'Invalid share URL: missing key material in URL fragment. Was the URL truncated or processed by a URL shortener?',
      });
      return;
    }

    shareIdRef.current = shareId;
    blobRef.current = fragment;
    setState({ step: 'password' });
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!password) return;

      // Client-side rate limiting
      if (backoffUntil && Date.now() < backoffUntil) {
        const remainingSec = Math.ceil((backoffUntil - Date.now()) / 1000);
        setState({
          step: 'error',
          message: `Too many failed attempts. Please wait ${remainingSec} seconds.`,
        });
        return;
      }

      setState({ step: 'decrypting' });

      const shareId = shareIdRef.current;
      const blobString = blobRef.current;

      try {
        // 1. Decode the blob from the URL fragment
        const blob = decodeShareBlob(blobString);

        // 2. Fetch share metadata from API
        const metaResponse = await fetch(
          `${apiBaseUrl}/v1/shares/${encodeURIComponent(shareId)}`
        );

        if (metaResponse.status === 410) {
          setState({
            step: 'error',
            message: 'This share link has expired or been revoked.',
          });
          return;
        }

        if (metaResponse.status === 429) {
          setState({
            step: 'error',
            message: 'Too many requests. Please try again later.',
          });
          return;
        }

        if (!metaResponse.ok) {
          throw new Error(
            `Failed to fetch share metadata: ${metaResponse.status}`
          );
        }

        const metadata: ShareMetadata = await metaResponse.json();

        // 3. Derive share keys from password + salt (from blob)
        const shareKeys = await deriveShareKeys(password, blob.salt);

        // 4. Verify HMAC
        const hmacValid = verifyShareHmac(
          shareKeys.hmacKey,
          shareId,
          metadata.expiresAt ?? undefined,
          blob.hmac
        );

        if (!hmacValid) {
          handleFailure('Incorrect password or tampered share link.');
          shareKeys.encryptionKey.fill(0);
          shareKeys.hmacKey.fill(0);
          return;
        }

        // 5. Unwrap the DEK using the share encryption key
        const shareWrappedDek = base64ToUint8(metadata.wrappedDek);
        let dek: Uint8Array;
        try {
          dek = unwrapDek(shareWrappedDek, shareKeys.encryptionKey);
        } catch (err) {
          shareKeys.encryptionKey.fill(0);
          shareKeys.hmacKey.fill(0);
          if (err instanceof DekUnwrapError) {
            handleFailure('Incorrect password or corrupted share data.');
            return;
          }
          throw err;
        }

        // Zero share keys
        shareKeys.encryptionKey.fill(0);
        shareKeys.hmacKey.fill(0);

        // 6. Download encrypted file
        const fileResponse = await fetch(metadata.downloadUrl);
        if (!fileResponse.ok) {
          dek.fill(0);
          throw new Error(
            `Failed to download encrypted file: ${fileResponse.status}`
          );
        }
        const encryptedContent = new Uint8Array(
          await fileResponse.arrayBuffer()
        );

        // 7. Decrypt with chacha20poly1305
        //    Format: [nonce(12)][ciphertext + authTag]
        if (encryptedContent.length < NONCE_SIZE + 16) {
          dek.fill(0);
          throw new Error('Encrypted file is too small to be valid.');
        }

        const nonce = encryptedContent.slice(0, NONCE_SIZE);
        const ciphertext = encryptedContent.slice(NONCE_SIZE);

        let plaintext: Uint8Array;
        try {
          const cipher = chacha20poly1305(dek, nonce);
          plaintext = cipher.decrypt(ciphertext);
        } catch {
          dek.fill(0);
          handleFailure('Decryption failed. The file may be corrupted.');
          return;
        } finally {
          dek.fill(0);
        }

        // 8. Trigger browser download
        const downloadBlob = new Blob([new Uint8Array(plaintext) as BlobPart], {
          type: metadata.contentType || 'application/octet-stream',
        });
        const url = URL.createObjectURL(downloadBlob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = metadata.fileName || 'download';
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);

        // Reset failure count on success
        setFailureCount(0);
        setBackoffUntil(null);

        setState({ step: 'done', fileName: metadata.fileName || 'download' });
      } catch (err) {
        if (
          (state as { step: string }).step !== 'error'
        ) {
          setState({
            step: 'error',
            message:
              err instanceof Error ? err.message : 'An unexpected error occurred.',
          });
        }
      }
    },
    [password, apiBaseUrl, backoffUntil, state]
  );

  const handleFailure = useCallback(
    (message: string) => {
      const newCount = failureCount + 1;
      setFailureCount(newCount);

      if (newCount >= MAX_FAILURES_BEFORE_BACKOFF) {
        const backoffMs = Math.min(
          BASE_BACKOFF_MS * Math.pow(2, newCount - MAX_FAILURES_BEFORE_BACKOFF),
          MAX_BACKOFF_MS
        );
        setBackoffUntil(Date.now() + backoffMs);
      }

      setState({ step: 'error', message });
    },
    [failureCount]
  );

  const handleRetry = useCallback(() => {
    setPassword('');
    setState({ step: 'password' });
  }, []);

  // --- Render ---

  if (state.step === 'loading') {
    return (
      <AuthFrame title="Shared file">
        <Spinner label="Loading share" />
      </AuthFrame>
    );
  }

  if (state.step === 'done') {
    return (
      <AuthFrame title="Download complete">
        <Banner
          status="success"
          title="File decrypted and downloaded"
          description={state.fileName}
        />
      </AuthFrame>
    );
  }

  if (state.step === 'error') {
    return (
      <AuthFrame title="Shared file access">
        <Banner status="error" title="Could not open this share" description={state.message} />
        {shareIdRef.current && (
          <Button label="Try again" variant="primary" width="100%" onClick={handleRetry} />
        )}
      </AuthFrame>
    );
  }

  if (state.step === 'decrypting') {
    return (
      <AuthFrame
        title="Decrypting…"
        description="Deriving keys and decrypting file. This may take a moment."
      >
        <Spinner label="Decrypting" />
      </AuthFrame>
    );
  }

  // step === 'password'
  return (
    <AuthFrame
      title="Shared file access"
      description="Enter the password to decrypt and download this shared file."
    >
      <form onSubmit={handleSubmit}>
        <VStack gap={3}>
          <TextInput
            label="Password"
            type="password"
            hasAutoFocus
            value={password}
            onChange={setPassword}
          />
          {backoffUntil && Date.now() < backoffUntil && (
            <Banner
              status="warning"
              title="Rate limited"
              description="Please wait before trying again."
            />
          )}
          <SubmitButton label="Decrypt & Download" isDisabled={!password} />
        </VStack>
      </form>
    </AuthFrame>
  );
}

/** Convert base64 string to Uint8Array */
function base64ToUint8(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
