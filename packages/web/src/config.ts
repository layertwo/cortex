export interface AppConfig {
  userPoolId: string;
  userPoolClientId: string;
  apiBaseUrl: string;
}

export function getConfig(): AppConfig {
  // Static member access only — Vite replaces `import.meta.env.VITE_*` literals at
  // build time; bracket/dynamic access is NOT replaced and breaks in production.
  // Region is intentionally omitted: Amplify v6 infers it from the userPoolId prefix.
  const userPoolId = import.meta.env.VITE_USER_POOL_ID;
  const userPoolClientId = import.meta.env.VITE_USER_POOL_CLIENT_ID;
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

  const missing = Object.entries({
    VITE_USER_POOL_ID: userPoolId,
    VITE_USER_POOL_CLIENT_ID: userPoolClientId,
    VITE_API_BASE_URL: apiBaseUrl,
  })
    .filter(([, v]) => !v)
    .map(([k]) => k);
  if (missing.length) throw new Error(`Missing required env var: ${missing.join(', ')}`);

  return { userPoolId, userPoolClientId, apiBaseUrl };
}
