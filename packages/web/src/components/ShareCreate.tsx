import { useCallback, useState } from 'react';
import {
  deriveShareKeys,
  computeShareHmac,
  encodeShareBlob,
  unwrapDek,
  wrapDek,
} from '@cortex/encryption';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Selector } from '@astryxdesign/core/Selector';
import { Banner } from '@astryxdesign/core/Banner';
import { Button } from '@astryxdesign/core/Button';
import { HStack } from '@astryxdesign/core/HStack';
import { VStack } from '@astryxdesign/core/VStack';
import { createShare } from '../api/shares';
import { encryptMetadata, type FileMetadata } from '../items/metadata';
import { useAsyncAction } from './common/useAsyncAction';

const MIN_PASSWORD_LENGTH = 16;
const MIN_ENTROPY_BITS = 80;
const SALT_SIZE = 16;
const BLOB_VERSION = 0x01;

// Expiration choices: label + seconds from now ('0' = never).
const EXPIRATIONS = [
  { value: '0', label: 'Never' },
  { value: '3600', label: '1 hour' },
  { value: '86400', label: '1 day' },
  { value: '604800', label: '7 days' },
  { value: '2592000', label: '30 days' },
];

/** Rough Shannon entropy estimate (charset size × length) in bits. */
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
  /** Decrypted file metadata (carries the contentId that binds the DEK). */
  meta: FileMetadata;
  /** The item's vault-wrapped DEK. */
  wrappedDek: Uint8Array;
  vaultKek: Uint8Array;
  onClose: () => void;
}

/**
 * Create a password-protected share link.
 *
 * The share-wrapped DEK, salt, and HMAC travel in the URL fragment; the server only
 * stores the share-key-encrypted metadata. Requires a vault-unlocked session (the
 * caller supplies the KEK) but the recipient needs only the password.
 */
export function ShareCreate({ itemId, meta, wrappedDek, vaultKek, onClose }: ShareCreateProps) {
  const [password, setPassword] = useState('');
  const [expiration, setExpiration] = useState('0');
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const { pending, error, run } = useAsyncAction();

  const entropy = estimatePasswordEntropy(password);
  const isPasswordValid = password.length >= MIN_PASSWORD_LENGTH && entropy >= MIN_ENTROPY_BITS;

  function submit() {
    void run(async () => {
      const salt = crypto.getRandomValues(new Uint8Array(SALT_SIZE));
      const shareKeys = await deriveShareKeys(password, salt);
      try {
        // Unwrap the item DEK (HMAC-bound to contentId), then re-wrap it under the
        // share key. encodeShareBlob requires the unbound 65-byte form.
        const dek = unwrapDek(wrappedDek, vaultKek, meta.contentId);
        const shareWrappedDek = await wrapDek(dek, shareKeys.encryptionKey);
        dek.fill(0);

        const seconds = Number(expiration);
        const expiresAt = seconds > 0 ? Math.floor(Date.now() / 1000) + seconds : undefined;
        // The recipient needs the filename, type, size, and the contentId that binds
        // the stream — all opaque to the server.
        const encryptedMetadata = await encryptMetadata(
          {
            name: meta.name,
            contentType: meta.contentType,
            size: meta.size,
            contentId: meta.contentId,
            ...(meta.streamVersion ? { streamVersion: meta.streamVersion } : {}),
          },
          shareKeys.encryptionKey,
        );

        const { shareId } = await createShare({ itemId, encryptedMetadata, expiresAt });

        const hmac = computeShareHmac(shareKeys.hmacKey, shareId, expiresAt);
        const blob = encodeShareBlob(BLOB_VERSION, salt, shareWrappedDek, hmac);
        setShareUrl(`${window.location.origin}/s/${shareId}#${blob}`);
      } finally {
        shareKeys.encryptionKey.fill(0);
        shareKeys.hmacKey.fill(0);
      }
    }, 'Could not create the share');
  }

  const copy = useCallback(async () => {
    if (shareUrl) await navigator.clipboard.writeText(shareUrl);
  }, [shareUrl]);

  return (
    <Dialog
      isOpen
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      purpose="form"
    >
      <Layout
        height="auto"
        header={<DialogHeader title="Create share link" onOpenChange={() => onClose()} />}
        content={
          <LayoutContent>
            <VStack gap={3}>
              {shareUrl ? (
                <>
                  <TextInput
                    label="Share URL"
                    value={shareUrl}
                    isReadOnly
                    description="Send this link and the password separately."
                    onChange={() => {}}
                  />
                  <Banner
                    status="warning"
                    title="Do not use URL shorteners"
                    description="The fragment after # holds the encrypted key material and some services strip it."
                  />
                </>
              ) : (
                <>
                  <TextInput
                    label="Password"
                    type="password"
                    value={password}
                    onChange={setPassword}
                    description={`At least ${MIN_PASSWORD_LENGTH} characters with a mix of character types.`}
                    status={
                      password.length > 0 && !isPasswordValid
                        ? {
                            type: 'error',
                            message:
                              password.length < MIN_PASSWORD_LENGTH
                                ? `Must be at least ${MIN_PASSWORD_LENGTH} characters (${password.length}/${MIN_PASSWORD_LENGTH}).`
                                : `Too weak — mix upper/lowercase, numbers, and symbols (${entropy}/${MIN_ENTROPY_BITS} bits).`,
                          }
                        : undefined
                    }
                  />
                  <Selector
                    label="Expiration"
                    options={EXPIRATIONS}
                    value={expiration}
                    onChange={setExpiration}
                  />
                  {error && <Banner role="alert" status="error" title={error} />}
                </>
              )}
            </VStack>
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              {shareUrl ? (
                <>
                  <Button label="Copy link" variant="primary" onClick={() => void copy()} />
                  <Button label="Done" variant="ghost" onClick={onClose} />
                </>
              ) : (
                <>
                  <Button label="Cancel" variant="ghost" onClick={onClose} />
                  <Button
                    label="Create link"
                    variant="primary"
                    isLoading={pending}
                    isDisabled={!isPasswordValid}
                    onClick={submit}
                  />
                </>
              )}
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}
