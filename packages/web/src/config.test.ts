import { describe, it, expect, vi } from 'vitest';
import { getConfig } from './config';

describe('getConfig', () => {
  it('defaults the API base to the same origin', () => {
    vi.stubEnv('VITE_API_BASE_URL', '');
    vi.stubEnv('VITE_OIDC_ISSUER', '');
    vi.stubEnv('VITE_OIDC_CLIENT_ID', '');
    expect(getConfig()).toEqual({ apiBaseUrl: '', oidcIssuer: '', oidcClientId: '' });
  });

  it('uses the configured API origin and OIDC client', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    vi.stubEnv('VITE_OIDC_ISSUER', 'https://idp.example.com');
    vi.stubEnv('VITE_OIDC_CLIENT_ID', 'cortex');
    expect(getConfig()).toEqual({
      apiBaseUrl: 'https://api.example.com',
      oidcIssuer: 'https://idp.example.com',
      oidcClientId: 'cortex',
    });
  });
});
