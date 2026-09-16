import { describe, it, expect, vi, beforeEach } from 'vitest';

const { getCurrentUser } = vi.hoisted(() => ({ getCurrentUser: vi.fn() }));
vi.mock('aws-amplify/auth', () => ({ getCurrentUser }));

import { ACCOUNT_KEY, getAccountId, resolveAccount, clearAccount } from './account';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('account gate', () => {
  it('has no account until one is resolved', () => {
    expect(ACCOUNT_KEY).toBe('cortex_account');
    expect(getAccountId()).toBeNull();
  });

  it('resolves the Cognito sub from getCurrentUser().userId and stores it', async () => {
    getCurrentUser.mockResolvedValueOnce({ userId: 'sub-1', username: 'a@b.c' });
    await expect(resolveAccount()).resolves.toBe('sub-1');
    expect(localStorage.getItem('cortex_account')).toBe('sub-1');
    expect(getAccountId()).toBe('sub-1');
  });

  it('propagates an Amplify failure and stores nothing', async () => {
    getCurrentUser.mockRejectedValueOnce(new Error('not signed in'));
    await expect(resolveAccount()).rejects.toThrow('not signed in');
    expect(getAccountId()).toBeNull();
  });

  it('clearAccount removes the stored subject', async () => {
    getCurrentUser.mockResolvedValueOnce({ userId: 'sub-1' });
    await resolveAccount();
    clearAccount();
    expect(getAccountId()).toBeNull();
    expect(localStorage.getItem('cortex_account')).toBeNull();
  });
});
