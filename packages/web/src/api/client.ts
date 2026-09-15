import {
  CortexClient,
  CreateVaultCommand,
  GetVaultSaltCommand,
  GetVaultCommand,
  UpdateVaultRotationCommand,
  ListVaultsCommand,
  UpdateVaultCommand,
  DeleteVaultCommand,
  type RotationState,
  type VaultSummary,
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
      if (!jwt) throw new Error('No Cognito session, sign in first');
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

export async function listVaults(
  pageSize = 50,
  nextToken?: string,
): Promise<{ vaults: VaultSummary[]; nextToken?: string }> {
  const out = await makeClient().send(new ListVaultsCommand({ pageSize, nextToken }));
  return { vaults: out.vaults ?? [], nextToken: out.nextToken };
}

// A page may be empty while nextToken is present (the server filters deleting
// vaults after the page limit), so page until the token is gone, not until a
// page comes back empty.
export async function listAllVaults(): Promise<VaultSummary[]> {
  const all: VaultSummary[] = [];
  let nextToken: string | undefined;
  do {
    const page = await listVaults(50, nextToken);
    all.push(...page.vaults);
    nextToken = page.nextToken;
  } while (nextToken);
  return all;
}

export async function updateVault(
  vaultId: string,
  fields: { encryptedName?: Uint8Array; verifier?: Uint8Array },
): Promise<void> {
  if (!fields.encryptedName && !fields.verifier) throw new Error('updateVault: nothing to update');
  await makeClient().send(
    new UpdateVaultCommand({ vaultId, encryptedName: fields.encryptedName, verifier: fields.verifier }),
  );
}

export async function deleteVault(vaultId: string): Promise<{
  deletionState: 'DELETING' | 'DELETED';
  deletedItems: number;
  deletedCollections: number;
  deletedShares: number;
}> {
  const out = await makeClient().send(new DeleteVaultCommand({ vaultId }));
  if (!out.deletionState) throw new Error('deleteVault: incomplete response');
  return {
    deletionState: out.deletionState,
    deletedItems: out.deletedItems ?? 0,
    deletedCollections: out.deletedCollections ?? 0,
    deletedShares: out.deletedShares ?? 0,
  };
}

export interface VaultRecord {
  vaultId: string;
  vaultSalt: Uint8Array;
  kekVersion: number;
  rotationState: RotationState;
  rotationLockedAt: number | null;
  encryptedName: Uint8Array | null;
  verifier: Uint8Array | null;
  pendingVaultSalt: Uint8Array | null;
  pendingVerifier: Uint8Array | null;
}

export async function getVault(vaultId: string): Promise<VaultRecord> {
  const out = await makeClient().send(new GetVaultCommand({ vaultId }));
  if (!out.vaultId || !out.vaultSalt) throw new Error('getVault: incomplete response');
  return {
    vaultId: out.vaultId,
    vaultSalt: out.vaultSalt,
    kekVersion: out.kekVersion ?? 1,
    rotationState: out.rotationState ?? 'IDLE',
    rotationLockedAt: out.rotationLockedAt ?? null,
    encryptedName: out.encryptedName ?? null,
    verifier: out.verifier ?? null,
    pendingVaultSalt: out.pendingVaultSalt ?? null,
    pendingVerifier: out.pendingVerifier ?? null,
  };
}

export type RotationActionName = 'ACQUIRE' | 'PAUSE' | 'RELEASE' | 'ABANDON';

export async function updateVaultRotation(args: {
  vaultId: string;
  action: RotationActionName;
  expectedState: RotationState;
  kekVersion?: number;
  newVerifier?: Uint8Array;
  newVaultSalt?: Uint8Array;
  newEncryptedName?: Uint8Array;
}): Promise<{
  rotationState: RotationState;
  rotationLockedAt: number | null;
  pendingVaultSalt: Uint8Array | null;
  pendingVerifier: Uint8Array | null;
}> {
  const out = await makeClient().send(new UpdateVaultRotationCommand(args));
  return {
    rotationState: out.rotationState ?? 'IDLE',
    rotationLockedAt: out.rotationLockedAt ?? null,
    pendingVaultSalt: out.pendingVaultSalt ?? null,
    pendingVerifier: out.pendingVerifier ?? null,
  };
}
