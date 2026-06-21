import { CortexClient, CreateVaultCommand, GetVaultSaltCommand } from '@cortex/client';
import { fetchAuthSession } from 'aws-amplify/auth';
import { getConfig } from '../config';

/**
 * Build the Smithy-generated Cortex SDK client.
 *
 * Auth is the Cognito idToken supplied as an HTTP bearer token (the contract is
 * @httpBearerAuth). The generated restJson1 serde honors the camelCase contract
 * and marshals Blob fields as Uint8Array<->base64, so callers work in raw bytes
 * — no manual casing or base64 handling here.
 *
 * Exported so sibling API modules (e.g. ./items) send their own commands through
 * the same endpoint + Cognito-bearer configuration.
 */
export function makeClient(): CortexClient {
  const { apiBaseUrl } = getConfig();
  return new CortexClient({
    endpoint: apiBaseUrl,
    token: async () => {
      const session = await fetchAuthSession();
      const jwt = session.tokens?.idToken?.toString();
      if (!jwt) throw new Error('No Cognito session — sign in first');
      return { token: jwt };
    },
  });
}

export async function createVault(): Promise<{ vaultId: string; vaultSalt: Uint8Array }> {
  const out = await makeClient().send(new CreateVaultCommand({}));
  if (!out.vaultId || !out.vaultSalt) throw new Error('createVault: incomplete response');
  return { vaultId: out.vaultId, vaultSalt: out.vaultSalt };
}

export async function getVaultSalt(vaultId: string): Promise<Uint8Array> {
  const out = await makeClient().send(new GetVaultSaltCommand({ vaultId }));
  if (!out.vaultSalt) throw new Error('getVaultSalt: missing salt');
  return out.vaultSalt;
}
