// Small badge with the file's extension for rows without a preview. Decorative: the name
// column carries the real information.
export default function FileTypeGlyph({ name, contentType }: { name?: string; contentType?: string }) {
  const label = (name?.match(/\.([^.]{1,4})$/)?.[1] ?? contentType?.split('/')[1] ?? 'FILE').slice(0, 4).toUpperCase();
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-flex',
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 'var(--radius-element)',
        background: 'var(--color-background-muted)',
        color: 'var(--color-text-accent)',
        fontSize: 'var(--font-size-xs)',
        fontWeight: 'var(--font-weight-bold)',
        letterSpacing: '0.04em',
      }}
    >
      {label}
    </span>
  );
}
