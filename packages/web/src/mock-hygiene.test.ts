import { describe, it, expect, vi } from 'vitest';

// Proves `test.mockReset`, `restoreMocks`, `unstubGlobals` and `unstubEnvs` (vite.config.ts)
// actually reset state between tests. Test 1 installs overrides, calls each mock once and
// leaves a Once value queued, spies console.debug, stubs a global and an env var; test 2 sets
// nothing and must see each mock's own default, no leftover Once value, no call history, the
// spy gone, the global gone, and the env var gone. If any flag is removed, test 2 fails.
const d = vi.fn(() => 'default');
const b = vi.fn();

describe('mock hygiene', () => {
  it('installs overrides and calls each mock once', () => {
    d.mockReturnValue('override');
    b.mockReturnValue('override');
    d();
    b();
    d.mockReturnValueOnce('once'); // left unconsumed: the reset must drain it too
    vi.spyOn(console, 'debug').mockImplementation(() => {});
    vi.stubGlobal('__cortexProbe', 1);
    vi.stubEnv('CORTEX_PROBE', 'x');
  });

  it('the next test sees each mock reset to its own default, with no leaked call history', () => {
    expect(d).not.toHaveBeenCalled();
    expect(d()).toBe('default');
    expect(b()).toBeUndefined();
    expect(vi.isMockFunction(console.debug)).toBe(false);
    expect('__cortexProbe' in globalThis).toBe(false);
    expect(import.meta.env.CORTEX_PROBE).toBeUndefined();
  });
});
