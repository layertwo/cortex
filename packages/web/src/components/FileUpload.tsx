import { useRef, useState } from 'react';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { ProgressBar } from '@astryxdesign/core/ProgressBar';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import { getVaultKeys } from '../vault/keyAccess';
import { uploadFileStreaming } from '../items/streamingUpload';
import { useAsyncAction } from './common/useAsyncAction';

// Soft ceiling ~5 GB. S3 multipart's hard cap at 8 MiB parts is ~80 GB; we guard
// well below that and show a clear message instead of letting a huge file hang.
export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024;

export default function FileUpload({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState(0);
  const [tags, setTags] = useState('');
  const { pending: busy, error, setError, run } = useAsyncAction();

  function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file
    if (!file) return;
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError('Files over 5 GB aren’t supported.');
      return;
    }
    setProgress(0);
    void run(async () => {
      const keys = await getVaultKeys();
      await uploadFileStreaming(file, keys, setProgress, {
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      });
      setTags('');
      onUploaded();
    }, 'Upload failed');
  }

  return (
    <VStack gap={2}>
      <HStack gap={2} vAlign="end">
        <TextInput
          label="Tags"
          placeholder="comma separated"
          size="sm"
          width={220}
          value={tags}
          onChange={setTags}
          isDisabled={busy}
        />
        <Button
          label="Upload file"
          variant="primary"
          size="sm"
          isDisabled={busy}
          onClick={() => inputRef.current?.click()}
        />
        {/* The real picker. Hidden, so assistive tech sees only the Button; the test
            harness still targets the labelled input directly. */}
        <input
          ref={inputRef}
          type="file"
          hidden
          aria-label="Upload file"
          onChange={onChange}
          disabled={busy}
        />
      </HStack>
      {busy && (
        <ProgressBar label="Encrypting and uploading" value={progress} max={1} hasValueLabel />
      )}
      {error && <Banner status="error" title={error} />}
    </VStack>
  );
}
