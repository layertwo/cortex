import { describe, it, expect, vi, afterEach } from 'vitest';
import { makeThumbnail } from './thumbnail';

describe('makeThumbnail', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('returns undefined for non-media files without touching the DOM', async () => {
    expect(await makeThumbnail(new File(['x'], 'a.pdf', { type: 'application/pdf' }))).toBeUndefined();
    expect(await makeThumbnail(new File(['x'], 'noext', { type: '' }))).toBeUndefined();
  });

  it('gives up quietly when the browser cannot decode (jsdom never fires onload)', async () => {
    const img = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' });
    expect(await makeThumbnail(img, { timeoutMs: 20 })).toBeUndefined();
  });

  it('clears the img src on timeout so the browser stops decoding a discarded file', async () => {
    class FakeImage {
      src = '';
      decode() {
        return new Promise<void>(() => {}); // never resolves — always races the timeout
      }
      removeAttribute(name: string) {
        if (name === 'src') this.src = '';
      }
    }
    const created: FakeImage[] = [];
    vi.stubGlobal(
      'Image',
      class extends FakeImage {
        constructor() {
          super();
          created.push(this);
        }
      },
    );
    const file = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' });
    expect(await makeThumbnail(file, { timeoutMs: 5 })).toBeUndefined();
    expect(created).toHaveLength(1);
    expect(created[0].src).toBe('');
  });

  it('clears and reloads the video element on timeout', async () => {
    const created: {
      src: string;
      load: ReturnType<typeof vi.fn>;
      muted: boolean;
      playsInline: boolean;
      preload: string;
      removeAttribute: (name: string) => void;
    }[] = [];
    const realCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag !== 'video') return realCreateElement(tag);
      const fake = {
        src: '',
        load: vi.fn(),
        muted: false,
        playsInline: false,
        preload: '',
        removeAttribute(name: string) {
          if (name === 'src') fake.src = '';
        },
      };
      created.push(fake);
      return fake as unknown as HTMLVideoElement;
    });
    const file = new File([new Uint8Array([1, 2, 3])], 'a.mp4', { type: 'video/mp4' });
    expect(await makeThumbnail(file, { timeoutMs: 5 })).toBeUndefined();
    expect(created).toHaveLength(1);
    expect(created[0].src).toBe('');
    expect(created[0].load).toHaveBeenCalled();
  });
});
