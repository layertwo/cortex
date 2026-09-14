// The "hex fold" mark: a hexagon (the vault) with one brain-fold wave inside.
// Decorative everywhere it appears; the wordmark or surrounding heading carries the name.
export default function Mark({ size = 24 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      fill="none"
      style={{ stroke: 'var(--color-accent)' }}
      strokeWidth={4.5}
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M24 4.5 41 14v20L24 43.5 7 34V14z" />
      <path d="M13.5 27.5c4.5-10 8 7 12.5-1s6.5-6.5 8.5-2" />
    </svg>
  );
}
