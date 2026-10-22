import { describe, it, expect, vi, beforeEach } from 'vitest';

// Runtime config is module-cached, so each test loads a fresh module.
let loadConfig: typeof import('./config').loadConfig;
let getConfig: typeof import('./config').getConfig;

beforeEach(async () => {
  vi.resetModules();
  ({ loadConfig, getConfig } = await import('./config'));
  vi.stubEnv('VITE_API_BASE_URL', '');
});

function respond(body: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok, status, json: async () => body })),
  );
}

describe('runtime config', () => {
  it('fetches the OIDC settings once and exposes them synchronously afterwards', async () => {
    respond({ oidcIssuer: 'https://idp.example.com', oidcClientId: 'cortex' });

    await expect(loadConfig()).resolves.toEqual({
      apiBaseUrl: '',
      oidcIssuer: 'https://idp.example.com',
      oidcClientId: 'cortex',
    });
    expect(fetch).toHaveBeenCalledWith('/v1/config', { credentials: 'same-origin' });
    expect(getConfig().oidcClientId).toBe('cortex');
  });

  it('uses the API origin when one is configured', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    respond({ oidcIssuer: 'https://idp.example.com', oidcClientId: 'cortex' });

    await loadConfig();

    expect(fetch).toHaveBeenCalledWith('https://api.example.com/v1/config', {
      credentials: 'same-origin',
    });
  });

  it('throws before the config has loaded', () => {
    expect(() => getConfig()).toThrow('Configuration not loaded');
  });

  it('throws when the API cannot serve settings', async () => {
    respond({}, false, 503);
    await expect(loadConfig()).rejects.toThrow('Configuration unavailable (503)');
  });

  it('throws when the settings are incomplete', async () => {
    respond({ oidcIssuer: 'https://idp.example.com' });
    await expect(loadConfig()).rejects.toThrow('Configuration is incomplete');
  });
});
