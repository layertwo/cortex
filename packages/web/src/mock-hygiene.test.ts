import { describe, it, expect, vi } from 'vitest';

// Proves `test.mockReset: true` (vite.config.ts) actually resets vi.fn state between tests.
// Test 1 installs overrides, calls each mock once and leaves a Once value queued; test 2 sets
// nothing and must see each mock's own default (the vi.fn(impl) argument, or undefined for a
// bare vi.fn()), no leftover Once value, and no call history. If mockReset is removed, test 2 fails.
const d = vi.fn(() => 'default');
const b = vi.fn();

describe('mock hygiene', () => {
  it('installs overrides and calls each mock once', () => {
    d.mockReturnValue('override');
    b.mockReturnValue('override');
    d();
    b();
    d.mockReturnValueOnce('once'); // left unconsumed: the reset must drain it too
  });

  it('the next test sees each mock reset to its own default, with no leaked call history', () => {
    expect(d).not.toHaveBeenCalled();
    expect(d()).toBe('default');
    expect(b()).toBeUndefined();
  });
});
