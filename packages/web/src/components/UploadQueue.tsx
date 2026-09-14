import { useEffect, useRef, useState } from 'react';
import { FileInput } from '@astryxdesign/core/FileInput';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Banner } from '@astryxdesign/core/Banner';
import { ProgressBar } from '@astryxdesign/core/ProgressBar';
import { VStack } from '@astryxdesign/core/VStack';
import { getVaultKeys } from '../vault/keyAccess';
import { uploadFileStreaming } from '../items/streamingUpload';
import { makeThumbnail } from '../items/thumbnail';

// Soft ceiling ~5 GB. S3 multipart's hard cap at 8 MiB parts is ~80 GB; we guard
// well below that and show a clear message instead of letting a huge file hang.
export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024;

type State = 'queued' | 'preview' | 'uploading' | 'failed';
type Item = { id: number; file: File; tags: string[]; state: State; progress: number; error?: string };

const STATE_LABEL: Record<State, string> = {
  queued: 'Waiting',
  preview: 'Making preview',
  uploading: 'Encrypting and uploading',
  failed: 'Failed',
};

let nextId = 1;

// Drop zone plus a sequential upload queue. Files can be picked, dropped on the strip, or
// dropped anywhere on the window. Each file gets a preview (when it's media), then the
// existing streaming upload; one file at a time keeps memory at O(chunk).
export default function UploadQueue({ onUploaded }: { onUploaded: () => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [tags, setTags] = useState('');
  const [dragging, setDragging] = useState(false);
  const busy = useRef(false);

  function enqueue(files: File[]) {
    const tagList = tags.split(',').map((t) => t.trim()).filter(Boolean);
    setItems((cur) => [
      ...cur,
      ...files.map<Item>((file) => ({
        id: nextId++,
        file,
        tags: tagList,
        state: file.size > MAX_FILE_SIZE_BYTES ? 'failed' : 'queued',
        progress: 0,
        error: file.size > MAX_FILE_SIZE_BYTES ? 'Files over 5 GB aren’t supported.' : undefined,
      })),
    ]);
  }

  // Drops anywhere on the page count. The FileInput strip handles its own drops and stops
  // propagation, so the two paths never double-enqueue.
  useEffect(() => {
    const over = (e: DragEvent) => {
      if (e.dataTransfer?.types?.includes('Files')) {
        e.preventDefault();
        setDragging(true);
      }
    };
    const leave = (e: DragEvent) => {
      if (!e.relatedTarget) setDragging(false);
    };
    const drop = (e: DragEvent) => {
      if (!e.dataTransfer?.types?.includes('Files')) return;
      e.preventDefault();
      setDragging(false);
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length) enqueue(files);
    };
    window.addEventListener('dragover', over);
    window.addEventListener('dragleave', leave);
    window.addEventListener('drop', drop);
    return () => {
      window.removeEventListener('dragover', over);
      window.removeEventListener('dragleave', leave);
      window.removeEventListener('drop', drop);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tags]);

  // Process the queue one item at a time.
  useEffect(() => {
    if (busy.current) return;
    const next = items.find((i) => i.state === 'queued');
    if (!next) return;
    busy.current = true;
    const patch = (p: Partial<Item>) => setItems((cur) => cur.map((i) => (i.id === next.id ? { ...i, ...p } : i)));
    void (async () => {
      try {
        patch({ state: 'preview' });
        const thumb = await makeThumbnail(next.file);
        patch({ state: 'uploading' });
        const keys = await getVaultKeys();
        await uploadFileStreaming(next.file, keys, (f) => patch({ progress: f }), { tags: next.tags, thumb });
        setItems((cur) => cur.filter((i) => i.id !== next.id));
        onUploaded();
      } catch (err) {
        patch({ state: 'failed', error: err instanceof Error ? err.message : 'Upload failed' });
      } finally {
        busy.current = false;
      }
    })();
  }, [items, onUploaded]);

  return (
    <VStack gap={2}>
      <div className={dragging ? 'drop-active' : undefined}>
        <FileInput
          label="Upload files"
          isLabelHidden
          mode="dropzone"
          isMultiple
          placeholder="Drop files anywhere to encrypt and upload, or click to choose"
          value={null}
          onChange={(files) => {
            if (files) enqueue(Array.isArray(files) ? files : [files]);
          }}
        />
      </div>
      <TextInput
        label="Tags"
        description="Comma separated, applied to files you add next"
        size="sm"
        width={320}
        value={tags}
        onChange={setTags}
      />
      {items.map((i) =>
        i.state === 'failed' ? (
          <Banner
            key={i.id}
            status="error"
            title={`${i.file.name}: ${i.error}`}
            isDismissable
            onDismiss={() => setItems((cur) => cur.filter((x) => x.id !== i.id))}
          />
        ) : (
          <ProgressBar
            key={i.id}
            label={`${i.file.name} · ${STATE_LABEL[i.state]}`}
            value={i.progress}
            max={1}
            isIndeterminate={i.state !== 'uploading'}
            hasValueLabel
          />
        ),
      )}
    </VStack>
  );
}
