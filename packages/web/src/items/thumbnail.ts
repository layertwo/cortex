const MAX_EDGE = 160;
const MAX_BYTES = 24 * 1024;
const DEFAULT_TIMEOUT_MS = 3000;

// Best-effort preview: images via <img>, videos via a seeked <video>, both drawn to a canvas
// and encoded as JPEG. Any failure or slowness yields undefined and the upload proceeds
// without a preview. In jsdom decoding never completes, so callers see undefined there.
export async function makeThumbnail(file: File, opts?: { timeoutMs?: number }): Promise<string | undefined> {
  const kind = file.type.startsWith('image/') ? 'image' : file.type.startsWith('video/') ? 'video' : null;
  if (!kind || typeof document === 'undefined') return undefined;
  const timeoutMs = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const url = URL.createObjectURL(file);
  const el: HTMLImageElement | HTMLVideoElement = kind === 'image' ? new Image() : document.createElement('video');
  let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
  try {
    const source = await Promise.race([
      kind === 'image' ? loadImage(el as HTMLImageElement, url) : loadVideoFrame(el as HTMLVideoElement, url),
      new Promise<never>((_, reject) => {
        timeoutHandle = setTimeout(() => reject(new Error('thumbnail timeout')), timeoutMs);
      }),
    ]);
    return encode(source);
  } catch {
    el.removeAttribute('src');
    if (kind === 'video') (el as HTMLVideoElement).load();
    return undefined;
  } finally {
    clearTimeout(timeoutHandle);
    URL.revokeObjectURL(url);
  }
}

async function loadImage(img: HTMLImageElement, url: string): Promise<HTMLImageElement> {
  img.src = url;
  await img.decode();
  return img;
}

function loadVideoFrame(v: HTMLVideoElement, url: string): Promise<HTMLVideoElement> {
  return new Promise((resolve, reject) => {
    v.muted = true;
    v.playsInline = true;
    v.preload = 'auto';
    v.onloadeddata = () => {
      v.currentTime = Math.min(0.5, (v.duration || 1) / 10);
    };
    v.onseeked = () => resolve(v);
    v.onerror = () => reject(new Error('video decode failed'));
    v.src = url;
  });
}

function encode(src: HTMLImageElement | HTMLVideoElement): string | undefined {
  const w = src instanceof HTMLVideoElement ? src.videoWidth : src.naturalWidth;
  const h = src instanceof HTMLVideoElement ? src.videoHeight : src.naturalHeight;
  if (!w || !h) return undefined;
  const scale = Math.min(1, MAX_EDGE / Math.max(w, h));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(w * scale));
  canvas.height = Math.max(1, Math.round(h * scale));
  const ctx = canvas.getContext('2d');
  if (!ctx) return undefined;
  ctx.drawImage(src, 0, 0, canvas.width, canvas.height);
  for (const quality of [0.72, 0.5]) {
    const out = canvas.toDataURL('image/jpeg', quality);
    if (out && out.length <= MAX_BYTES) return out;
  }
  return undefined;
}
