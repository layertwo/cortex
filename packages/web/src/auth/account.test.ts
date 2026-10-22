import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ACCOUNT_KEY, getAccountId, resolveAccount, clearAccount } from './account';

const { getUser } = vi.hoisted(() => ({ getUser: vi.fn() }));
vi.mock('./oidc', () => ({ getUserManager: () => ({ getUser }) }));

beforeEach(() => {
  localStorage.clear();
});

describe('account gate', () => {
  it('has no account until one is resolved', () => {
    expect(ACCOUNT_KEY).toBe('cortex_account');
    expect(getAccountId()).toBeNull();
  });

  it('stores the OIDC subject and returns it', async () => {
    getUser.mockResolvedValueOnce({ expired: false, profile: { sub: 'u1' } });
    await expect(resolveAccount()).resolves.toBe('u1');
    expect(localStorage.getItem('cortex_account')).toBe('u1');
    expect(getAccountId()).toBe('u1');
  });

  it('rejects without a user and stores nothing', async () => {
    getUser.mockResolvedValueOnce(null);
    await expect(resolveAccount()).rejects.toThrow('Not authenticated');
    expect(getAccountId()).toBeNull();
  });

  it('rejects an expired user', async () => {
    getUser.mockResolvedValueOnce({ expired: true, profile: { sub: 'u1' } });
    await expect(resolveAccount()).rejects.toThrow('Not authenticated');
    expect(getAccountId()).toBeNull();
  });

  it('clearAccount removes the stored subject', async () => {
    getUser.mockResolvedValueOnce({ expired: false, profile: { sub: 'u1' } });
    await resolveAccount();
    clearAccount();
    expect(getAccountId()).toBeNull();
    expect(localStorage.getItem('cortex_account')).toBeNull();
  });
});
