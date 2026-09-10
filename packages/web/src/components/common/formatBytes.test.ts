import { describe, it, expect } from 'vitest';
import { formatBytes } from './formatBytes';

describe('formatBytes', () => {
  it('formats bytes, kilobytes, megabytes and gigabytes', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1023)).toBe('1023 B');
    expect(formatBytes(1234)).toBe('1.2 KB');
    expect(formatBytes(123456789)).toBe('118 MB');
    expect(formatBytes(5 * 1024 * 1024 * 1024)).toBe('5.0 GB');
  });

  it('rolls over to the next unit when rounding would print 1024', () => {
    expect(formatBytes(1048575)).toBe('1.0 MB');
    expect(formatBytes(1024 * 1024 * 1024 - 1)).toBe('1.0 GB');
  });
});
