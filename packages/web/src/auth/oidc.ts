import { UserManager, WebStorageStateStore } from 'oidc-client-ts';
import { getConfig } from '../config';

let manager: UserManager | null = null;

// One UserManager for the app: authorization code + PKCE against any OIDC provider.
// Created lazily so importing this module never needs OIDC config (share links, tests).
// Tokens live in sessionStorage: they die with the tab instead of outliving it in localStorage.
export function getUserManager(): UserManager {
  if (manager) return manager;
  const { oidcIssuer, oidcClientId } = getConfig();
  if (!oidcIssuer || !oidcClientId) throw new Error('OIDC is not configured');
  manager = new UserManager({
    authority: oidcIssuer.replace(/\/$/, ''),
    client_id: oidcClientId,
    redirect_uri: `${window.location.origin}/auth/callback`,
    response_type: 'code',
    // offline_access asks for a refresh token, so a long session can renew without a redirect.
    scope: 'openid profile email offline_access',
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: false,
  });
  return manager;
}
