import { describe, it, expect } from 'vitest';
import { makeThumbnail } from './thumbnail';

describe('makeThumbnail', () => {
  it('returns undefined for non-media files without touching the DOM', async () => {
    expect(await makeThumbnail(new File(['x'], 'a.pdf', { type: 'application/pdf' }))).toBeUndefined();
    expect(await makeThumbnail(new File(['x'], 'noext', { type: '' }))).toBeUndefined();
  });

  it('gives up quietly when the browser cannot decode (jsdom never fires onload)', async () => {
    const img = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' });
    expect(await makeThumbnail(img, { timeoutMs: 20 })).toBeUndefined();
    const vid = new File([new Uint8Array([1, 2, 3])], 'a.mp4', { type: 'video/mp4' });
    expect(await makeThumbnail(vid, { timeoutMs: 20 })).toBeUndefined();
  });
});
