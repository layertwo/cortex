import { fetchAuthSession } from 'aws-amplify/auth';
import { base64ToBytes } from '@cortex/encryption';
import { getConfig } from '../config';

export async function authHeader(): Promise<{ Authorization: string }> {
  const session = await fetchAuthSession();
  const jwt = session.tokens?.idToken?.toString();
  if (!jwt) throw new Error('No Cognito session — sign in first');
  return { Authorization: `Bearer ${jwt}` };
}

async function request(path: string, init: RequestInit = {}): Promise<any> {
  const { apiBaseUrl } = getConfig();
  const headers = {
    'Content-Type': 'application/json',
    ...(await authHeader()),
    ...(init.headers ?? {}),
  };
  const res = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

export async function createVault(): Promise<{ vaultId: string; vaultSalt: Uint8Array }> {
  const body = await request('/v1/vaults', { method: 'POST', body: JSON.stringify({}) });
  return { vaultId: body.vaultId, vaultSalt: base64ToBytes(body.vaultSalt) };
}

export async function getVaultSalt(vaultId: string): Promise<Uint8Array> {
  const body = await request(`/v1/vaults/${encodeURIComponent(vaultId)}/salt`, { method: 'GET' });
  return base64ToBytes(body.vaultSalt);
}
