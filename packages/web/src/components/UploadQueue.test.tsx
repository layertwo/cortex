import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent, within, createEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
  uploadFileStreaming: vi.fn(async (..._args: unknown[]) => {}),
  makeThumbnail: vi.fn(async () => 'data:image/jpeg;base64,AAAA'),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../items/streamingUpload', () => ({ uploadFileStreaming: h.uploadFileStreaming }));
vi.mock('../items/thumbnail', () => ({ makeThumbnail: h.makeThumbnail }));

import UploadQueue, { MAX_FILE_SIZE_BYTES } from './UploadQueue';

function pick(name: string, bytes: number, type = 'image/png') {
  const file = new File([new Uint8Array(Math.min(bytes, 4))], name, { type });
  Object.defineProperty(file, 'size', { value: bytes });
  return file;
}
const input = (c: HTMLElement) => c.querySelector('input[type=file]') as HTMLInputElement;

describe('UploadQueue', () => {
  it('uploads a picked file with its thumbnail and tags, then reports back', async () => {
    const onUploaded = vi.fn();
    const { container } = render(<UploadQueue onUploaded={onUploaded} />);
    await userEvent.type(screen.getByLabelText(/tags/i), 'Trip, beach ,');
    await userEvent.upload(input(container), pick('a.png', 3));
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
    expect(h.uploadFileStreaming).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'a.png' }),
      expect.objectContaining({ vaultId: 'v1' }),
      expect.any(Function),
      { tags: ['Trip', 'beach'], thumb: 'data:image/jpeg;base64,AAAA' },
    );
  });

  it('uploads several files one after another', async () => {
    const onUploaded = vi.fn();
    const { container } = render(<UploadQueue onUploaded={onUploaded} />);
    await userEvent.upload(input(container), [pick('a.png', 3), pick('b.png', 3)]);
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(2));
    expect(h.uploadFileStreaming.mock.calls.map((c) => (c[0] as File).name)).toEqual(['a.png', 'b.png']);
  });

  it('accepts files dropped anywhere on the window', async () => {
    const onUploaded = vi.fn();
    render(<UploadQueue onUploaded={onUploaded} />);
    fireEvent.drop(window, { dataTransfer: { files: [pick('c.png', 3)], types: ['Files'] } });
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
  });

  it('ignores a window drop that carries no files (e.g. dragging selected text)', async () => {
    const onUploaded = vi.fn();
    render(<UploadQueue onUploaded={onUploaded} />);
    const ev = createEvent.drop(window, { dataTransfer: { types: ['text/plain'], files: [] } });
    fireEvent(window, ev);
    expect(ev.defaultPrevented).toBe(false);
    expect(h.uploadFileStreaming).not.toHaveBeenCalled();
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it('rejects files over the 5 GB cap without uploading', async () => {
    const { container } = render(<UploadQueue onUploaded={vi.fn()} />);
    await userEvent.upload(input(container), pick('big.bin', MAX_FILE_SIZE_BYTES + 1, 'application/octet-stream'));
    expect(await within(container).findByRole('alert')).toHaveTextContent(/5 ?GB/i);
    expect(h.uploadFileStreaming).not.toHaveBeenCalled();
  });

  it('surfaces a failed upload and keeps going', async () => {
    h.uploadFileStreaming.mockRejectedValueOnce(new Error('integrity check failed'));
    const onUploaded = vi.fn();
    const { container } = render(<UploadQueue onUploaded={onUploaded} />);
    await userEvent.upload(input(container), [pick('a.png', 3), pick('b.png', 3)]);
    expect(await within(container).findByRole('alert')).toHaveTextContent(/a\.png.*integrity check failed/i);
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
  });
});
