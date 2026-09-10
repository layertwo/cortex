const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

// Binary units, one decimal below 10 so "1.2 KB" and "118 MB" both read naturally.
// The loop tests the *rounded* value so 1,048,575 bytes rolls over to "1.0 MB"
// instead of printing "1024 KB".
export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (unit < UNITS.length - 1 && Math.round(value) >= 1024) {
    value /= 1024;
    unit++;
  }
  const digits = unit === 0 ? 0 : value < 10 ? 1 : 0;
  return `${value.toFixed(digits)} ${UNITS[unit]}`;
}
