import { useState, useCallback } from 'react';
import {
  deriveShareKeys,
  computeShareHmac,
  encodeShareBlob,
  unwrapDek,
  wrapDek,
} from '@cortex/encryption';

/** Expiration option for share links */
interface ExpirationOption {
  label: string;
  value: number | null; // seconds from now, or null for never
}

const EXPIRATION_OPTIONS: ExpirationOption[] = [
  { label: 'Never', value: null },
  { label: '1 hour', value: 3600 },
  { label: '1 day', value: 86400 },
  { label: '7 days', value: 604800 },
  { label: '30 days', value: 2592000 },
];

const MIN_PASSWORD_LENGTH = 16;
const MIN_ENTROPY_BITS = 80;
const SALT_SIZE = 16;
const BLOB_VERSION = 0x01;

/**
 * Estimate Shannon entropy of a password in bits.
 * Counts unique character classes and uses charset size * length.
 */
function estimatePasswordEntropy(password: string): number {
  let charsetSize = 0;
  if (/[a-z]/.test(password)) charsetSize += 26;
  if (/[A-Z]/.test(password)) charsetSize += 26;
  if (/[0-9]/.test(password)) charsetSize += 10;
  if (/[^a-zA-Z0-9]/.test(password)) charsetSize += 32;
  if (charsetSize === 0) return 0;
  return Math.floor(password.length * Math.log2(charsetSize));
}

interface ShareCreateProps {
  itemId: string;
  wrappedDek: Uint8Array;
  vaultKek: Uint8Array;
  apiBaseUrl: string;
}

interface ShareResult {
  shareUrl: string;
  shareId: string;
}

export function ShareCreate({
  itemId,
  wrappedDek,
  vaultKek,
  apiBaseUrl,
}: ShareCreateProps) {
  const [password, setPassword] = useState('');
  const [expirationIndex, setExpirationIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ShareResult | null>(null);
  const [copied, setCopied] = useState(false);

  const passwordEntropy = estimatePasswordEntropy(password);
  const isPasswordValid = password.length >= MIN_PASSWORD_LENGTH && passwordEntropy >= MIN_ENTROPY_BITS;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!isPasswordValid || isSubmitting) return;

      setIsSubmitting(true);
      setError(null);
      setResult(null);

      try {
        // 1. Generate random salt
        const salt = crypto.getRandomValues(new Uint8Array(SALT_SIZE));

        // 2. Derive share encryption + HMAC keys from password + salt
        const shareKeys = await deriveShareKeys(password, salt);

        // 3. Unwrap the file DEK using vault KEK
        const dek = unwrapDek(wrappedDek, vaultKek);

        // 4. Re-wrap the DEK with the share encryption key
        const shareWrappedDek = await wrapDek(dek, shareKeys.encryptionKey);

        // Zero the plaintext DEK
        dek.fill(0);

        // 5. Compute expiration
        const selectedExpiration = EXPIRATION_OPTIONS[expirationIndex];
        const expiresAt = selectedExpiration.value
          ? Math.floor(Date.now() / 1000) + selectedExpiration.value
          : undefined;

        // 6. POST /v1/shares to create the share record
        const response = await fetch(`${apiBaseUrl}/v1/shares`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            item_id: itemId,
            expires_at: expiresAt ?? null,
          }),
        });

        if (!response.ok) {
          const body = await response.text();
          throw new Error(`Failed to create share: ${response.status} ${body}`);
        }

        const { share_id: shareId } = (await response.json()) as { share_id: string };

        // 7. Compute HMAC over shareId (and optional expiry)
        const hmacValue = computeShareHmac(
          shareKeys.hmacKey,
          shareId,
          expiresAt
        );

        // 8. Encode the share blob
        const blob = encodeShareBlob(
          BLOB_VERSION,
          salt,
          shareWrappedDek,
          hmacValue
        );

        // 9. Construct share URL with blob in fragment
        const origin = window.location.origin;
        const shareUrl = `${origin}/s/${shareId}#${blob}`;

        // Zero keys
        shareKeys.encryptionKey.fill(0);
        shareKeys.hmacKey.fill(0);

        setResult({ shareUrl, shareId });
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'An unexpected error occurred'
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [password, isPasswordValid, isSubmitting, expirationIndex, itemId, wrappedDek, vaultKek, apiBaseUrl]
  );

  const handleCopy = useCallback(async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select the text in the input
      const input = document.querySelector<HTMLInputElement>(
        '[data-testid="share-url-input"]'
      );
      if (input) {
        input.select();
      }
    }
  }, [result]);

  // --- Result view ---
  if (result) {
    return (
      <div style={{ padding: '1rem' }}>
        <h3>Share Link Created</h3>

        <div style={{ marginBottom: '0.5rem' }}>
          <label htmlFor="share-url">Share URL</label>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            <input
              id="share-url"
              data-testid="share-url-input"
              type="text"
              readOnly
              value={result.shareUrl}
              style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.85rem' }}
              onClick={(e) => (e.target as HTMLInputElement).select()}
            />
            <button type="button" onClick={handleCopy}>
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        </div>

        <p style={{ fontSize: '0.85rem', color: '#666' }}>
          Share ID: <code>{result.shareId}</code>
        </p>

        <p style={{ fontSize: '0.8rem', color: '#996600' }}>
          Warning: Do not use URL shorteners -- the fragment (after #) contains
          encrypted key material and may be stripped by some services.
        </p>
      </div>
    );
  }

  // --- Form view ---
  return (
    <form onSubmit={handleSubmit} style={{ padding: '1rem' }}>
      <h3>Create Share Link</h3>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="share-password">
          Password (minimum {MIN_PASSWORD_LENGTH} characters)
        </label>
        <input
          id="share-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={MIN_PASSWORD_LENGTH}
          required
          style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
          disabled={isSubmitting}
        />
        {password.length > 0 && !isPasswordValid && (
          <p style={{ color: 'red', fontSize: '0.85rem', margin: '0.25rem 0 0' }}>
            {password.length < MIN_PASSWORD_LENGTH
              ? `Password must be at least ${MIN_PASSWORD_LENGTH} characters (${password.length}/${MIN_PASSWORD_LENGTH})`
              : `Password too weak — use a mix of upper/lowercase, numbers, and symbols (${passwordEntropy}/${MIN_ENTROPY_BITS} bits)`}
          </p>
        )}
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="share-expiration">Expiration</label>
        <select
          id="share-expiration"
          value={expirationIndex}
          onChange={(e) => setExpirationIndex(Number(e.target.value))}
          style={{ display: 'block', marginTop: '0.25rem' }}
          disabled={isSubmitting}
        >
          {EXPIRATION_OPTIONS.map((opt, i) => (
            <option key={i} value={i}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p style={{ color: 'red', marginBottom: '1rem' }}>{error}</p>
      )}

      <button type="submit" disabled={!isPasswordValid || isSubmitting}>
        {isSubmitting ? 'Creating...' : 'Create Share Link'}
      </button>
    </form>
  );
}
