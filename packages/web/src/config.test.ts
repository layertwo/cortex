import { describe, it, expect, afterEach, vi } from 'vitest';
import { getConfig } from './config';

describe('getConfig', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('returns the configured values when env vars are set', () => {
    vi.stubEnv('VITE_USER_POOL_ID', 'us-east-1_abc');
    vi.stubEnv('VITE_USER_POOL_CLIENT_ID', 'client123');
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    expect(getConfig()).toEqual({
      userPoolId: 'us-east-1_abc',
      userPoolClientId: 'client123',
      apiBaseUrl: 'https://api.example.com',
    });
  });

  it('throws naming the missing var', () => {
    vi.stubEnv('VITE_USER_POOL_ID', '');
    vi.stubEnv('VITE_USER_POOL_CLIENT_ID', 'client123');
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    expect(() => getConfig()).toThrow('VITE_USER_POOL_ID');
  });
});
