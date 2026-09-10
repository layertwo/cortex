import { describe, it, expect } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAsyncAction } from './useAsyncAction';

describe('useAsyncAction', () => {
  it('is pending while the action runs and clear afterwards', async () => {
    const { result } = renderHook(() => useAsyncAction());
    let finish!: () => void;
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    let running!: Promise<void>;
    act(() => {
      running = result.current.run(() => gate, 'Failed');
    });
    expect(result.current.pending).toBe(true);
    await act(async () => {
      finish();
      await running;
    });
    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBe('');
  });

  it('surfaces the thrown message, or the fallback for non-Error rejections', async () => {
    const { result } = renderHook(() => useAsyncAction());
    await act(() =>
      result.current.run(async () => {
        throw new Error('boom');
      }, 'Failed'),
    );
    expect(result.current.error).toBe('boom');
    await act(() =>
      result.current.run(async () => {
        throw 'nope';
      }, 'Failed'),
    );
    expect(result.current.error).toBe('Failed');
    expect(result.current.pending).toBe(false);
  });
});
