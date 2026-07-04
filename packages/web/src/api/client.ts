import {
  CortexClient,
  CreateVaultCommand,
  GetVaultSaltCommand,
  GetVaultCommand,
  UpdateVaultRotationCommand,
} from '@cortex/client';
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

export interface VaultRecord {
  vaultId: string;
  vaultSalt: Uint8Array;
  kekVersion: number;
  rotationState: 'IDLE' | 'IN_PROGRESS' | 'PAUSED' | 'FAILED';
  rotationLockedAt: number | null;
}

export async function getVault(vaultId: string): Promise<VaultRecord> {
  const out = await makeClient().send(new GetVaultCommand({ vaultId }));
  if (!out.vaultId || !out.vaultSalt) throw new Error('getVault: incomplete response');
  return {
    vaultId: out.vaultId,
    vaultSalt: out.vaultSalt,
    kekVersion: out.kekVersion ?? 1,
    rotationState: (out.rotationState as VaultRecord['rotationState']) ?? 'IDLE',
    rotationLockedAt: out.rotationLockedAt ?? null,
  };
}

export async function updateVaultRotation(args: {
  vaultId: string;
  action: 'ACQUIRE' | 'RELEASE';
  expectedState: 'IDLE' | 'IN_PROGRESS' | 'PAUSED' | 'FAILED';
  kekVersion?: number;
  newVerifier?: Uint8Array;
}): Promise<{ rotationState: string; rotationLockedAt: number | null }> {
  const out = await makeClient().send(new UpdateVaultRotationCommand(args));
  return {
    rotationState: out.rotationState ?? 'IDLE',
    rotationLockedAt: out.rotationLockedAt ?? null,
  };
}
