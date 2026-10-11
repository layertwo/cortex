import { useState, useEffect, useCallback, useRef } from 'react';
import {
  deriveShareKeys,
  verifyShareHmac,
  decodeShareBlob,
  unwrapDek,
  base64ToBytes,
  DekUnwrapError,
} from '@cortex/encryption';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Spinner } from '@astryxdesign/core/Spinner';
import { VStack } from '@astryxdesign/core/VStack';
import AuthFrame from './common/AuthFrame';
import SubmitButton from './common/SubmitButton';
import { getPublicShare, ShareFetchError } from '../api/shares';
import { decryptMetadata } from '../items/metadata';
import { blobSink, decryptStreamToSink } from '../items/streamingDownload';

const MAX_FAILURES_BEFORE_BACKOFF = 3;
const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

interface ShareAccessProps {
  apiBaseUrl: string;
}

type AccessState =
  | { step: 'loading' }
  | { step: 'error'; message: string }
  | { step: 'password' }
  | { step: 'decrypting' }
  | { step: 'done'; fileName: string };

/**
 * Anonymous share access: the password derives the share key, which unwraps the DEK
 * carried in the URL fragment and decrypts the file metadata stored on the server.
 */
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
        // 1. Decode the key material from the URL fragment
        const blob = decodeShareBlob(blobString);

        // 2. Fetch share metadata (anonymous)
        const metadata = await getPublicShare(apiBaseUrl, shareId);

        // 3. Derive share keys from password + salt (from the fragment)
        const shareKeys = await deriveShareKeys(password, blob.salt);

        // 4. Verify the fragment HMAC against the server-reported expiry
        const hmacValid = verifyShareHmac(
          shareKeys.hmacKey,
          shareId,
          metadata.expiresAt ?? undefined,
          blob.hmac
        );
        if (!hmacValid) {
          shareKeys.encryptionKey.fill(0);
          shareKeys.hmacKey.fill(0);
          handleFailure('Incorrect password or tampered share link.');
          return;
        }

        // 5. Decrypt the file metadata (name/type/size/contentId) with the share key
        let meta;
        try {
          meta = decryptMetadata(base64ToBytes(metadata.encryptedMetadata), shareKeys.encryptionKey);
        } catch {
          shareKeys.encryptionKey.fill(0);
          shareKeys.hmacKey.fill(0);
          handleFailure('Incorrect password or corrupted share data.');
          return;
        }

        // 6. Unwrap the DEK carried in the fragment
        let dek: Uint8Array;
        try {
          dek = unwrapDek(blob.wrappedDek, shareKeys.encryptionKey);
        } catch (err) {
          shareKeys.encryptionKey.fill(0);
          shareKeys.hmacKey.fill(0);
          if (err instanceof DekUnwrapError) {
            handleFailure('Incorrect password or corrupted share data.');
            return;
          }
          throw err;
        }
        shareKeys.encryptionKey.fill(0);
        shareKeys.hmacKey.fill(0);

        // 7. Stream-decrypt the file straight into a download (zeroes the DEK).
        await decryptStreamToSink(
          metadata.downloadUrl,
          meta,
          dek,
          blobSink(meta.name, meta.contentType),
        );

        setFailureCount(0);
        setBackoffUntil(null);
        setState({ step: 'done', fileName: meta.name });
      } catch (err) {
        if (err instanceof ShareFetchError) {
          setState({
            step: 'error',
            message:
              err.status === 410
                ? 'This share link has expired or been revoked.'
                : err.status === 429
                  ? 'Too many requests. Please try again later.'
                  : 'This share link could not be opened.',
          });
          return;
        }
        setState({
          step: 'error',
          message: err instanceof Error ? err.message : 'An unexpected error occurred.',
        });
      }
    },
    [password, apiBaseUrl, backoffUntil, handleFailure]
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
