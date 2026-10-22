export interface AppConfig {
  // Origin of the API. Empty means same origin: the ingress proxy splits /v1 to the API.
  apiBaseUrl: string;
  // Generic OIDC provider (Pocket ID in the homelab, Cognito's hosted UI on AWS).
  oidcIssuer: string;
  oidcClientId: string;
}

export function getConfig(): AppConfig {
  // Static member access only — Vite replaces `import.meta.env.VITE_*` literals at
  // build time; bracket/dynamic access is NOT replaced and breaks in production.
  return {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? '',
    oidcIssuer: import.meta.env.VITE_OIDC_ISSUER ?? '',
    oidcClientId: import.meta.env.VITE_OIDC_CLIENT_ID ?? '',
  };
}
