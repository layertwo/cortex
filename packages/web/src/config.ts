export interface AppConfig {
  // Origin of the API. Empty means same origin: the ingress proxy splits /v1 to the API.
  apiBaseUrl: string;
  // Generic OIDC provider (Pocket ID in the homelab, Cognito's hosted UI on AWS).
  oidcIssuer: string;
  oidcClientId: string;
}

let cached: AppConfig | null = null;

// Runtime settings come from the API so one image works in every deployment. The issuer
// and client id are public by design: they appear in every authorization request.
export async function loadConfig(): Promise<AppConfig> {
  // Optional build-time override for an API on another origin; empty = same origin.
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '';
  const response = await fetch(`${apiBaseUrl}/v1/config`, { credentials: 'same-origin' });
  if (!response.ok) throw new Error(`Configuration unavailable (${response.status})`);
  const body = (await response.json()) as { oidcIssuer?: string; oidcClientId?: string };
  if (!body.oidcIssuer || !body.oidcClientId) throw new Error('Configuration is incomplete');
  cached = { apiBaseUrl, oidcIssuer: body.oidcIssuer, oidcClientId: body.oidcClientId };
  return cached;
}

export function getConfig(): AppConfig {
  if (!cached) throw new Error('Configuration not loaded');
  return cached;
}
