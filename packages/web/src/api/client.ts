import {
  CortexClient,
  CreateVaultCommand,
  GetVaultCommand,
  UpdateVaultPasswordCommand,
  UpdateVaultRotationCommand,
  ListVaultsCommand,
  UpdateVaultCommand,
  DeleteVaultCommand,
  type RotationState,
  type VaultSummary,
} from '@cortex/client';
import { getUserManager } from '../auth/oidc';
import { getConfig } from '../config';

/**
 * Build the Smithy-generated Cortex SDK client.
 *
 * The generated client sends the bearer token from the configured provider; we hand it
 * the OIDC ID token from the generic OIDC login (Pocket ID locally, Cognito hosted UI on
 * AWS). The API validates it against the provider's JWKS.
 *
 * Exported so sibling API modules (e.g. ./items) send their own commands through
 * the same endpoint + auth configuration.
 */
export function makeClient(): CortexClient {
  const { apiBaseUrl } = getConfig();
  return new CortexClient({
    endpoint: apiBaseUrl,
    token: async () => {
      let user = await getUserManager().getUser();
      // Renew with the refresh token when the provider issued one; otherwise the caller
      // sees "Not signed in" and the sign-in screen comes back.
      if (user?.expired && user.refresh_token) {
        user = await getUserManager().signinSilent();
      }
      if (!user?.id_token) throw new Error('Not signed in');
      return { token: user.id_token };
    },
  });
}

export async function createVault(): Promise<{ vaultId: string; vaultSalt: Uint8Array }> {
  const out = await makeClient().send(new CreateVaultCommand({}));
  if (!out.vaultId || !out.vaultSalt) throw new Error('createVault: incomplete response');
  return { vaultId: out.vaultId, vaultSalt: out.vaultSalt };
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

export async function updateVault(vaultId: string, fields: { encryptedName?: Uint8Array }): Promise<void> {
  if (!fields.encryptedName) throw new Error('updateVault: nothing to update');
  await makeClient().send(new UpdateVaultCommand({ vaultId, encryptedName: fields.encryptedName }));
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

// One VMK generation, wrapped under the vault key derived from a given vault password.
export interface VmkEnvelopeRecord {
  vmkVersion: number;
  wrappedVmk: Uint8Array;
  createdAt: Date;
}

export interface VaultRecord {
  vaultId: string;
  vaultSalt: Uint8Array;
  encryptedName: Uint8Array | null;
  currentVmkVersion: number;
  envelopeVersion: number;
  vmkEnvelopes: VmkEnvelopeRecord[];
  rotationState: RotationState;
  rotationLockedAt: number | null;
}

export async function getVault(vaultId: string): Promise<VaultRecord> {
  const out = await makeClient().send(new GetVaultCommand({ vaultId }));
  if (!out.vaultId || !out.vaultSalt) throw new Error('getVault: incomplete response');
  return {
    vaultId: out.vaultId,
    vaultSalt: out.vaultSalt,
    encryptedName: out.encryptedName ?? null,
    currentVmkVersion: out.currentVmkVersion ?? 0,
    envelopeVersion: out.envelopeVersion ?? 0,
    vmkEnvelopes: (out.vmkEnvelopes ?? []).flatMap((e) =>
      e.vmkVersion == null || !e.wrappedVmk
        ? []
        : [{ vmkVersion: e.vmkVersion, wrappedVmk: e.wrappedVmk, createdAt: e.createdAt ?? new Date(0) }],
    ),
    rotationState: out.rotationState ?? 'IDLE',
    rotationLockedAt: out.rotationLockedAt ?? null,
  };
}

// Replace the whole envelope list under an optimistic guard on envelopeVersion. Setup bootstraps
// with expectedEnvelopeVersion 0 and a single envelope at vmkVersion 1.
export async function updateVaultPassword(
  vaultId: string,
  expectedEnvelopeVersion: number,
  vmkEnvelopes: VmkEnvelopeRecord[],
): Promise<{ envelopeVersion: number }> {
  const out = await makeClient().send(new UpdateVaultPasswordCommand({ vaultId, expectedEnvelopeVersion, vmkEnvelopes }));
  if (out.envelopeVersion == null) throw new Error('updateVaultPassword: incomplete response');
  return { envelopeVersion: out.envelopeVersion };
}

export async function updateVaultRotation(args: {
  vaultId: string;
  action: 'ACQUIRE' | 'RELEASE';
  expectedState?: RotationState; // RELEASE only; ACQUIRE derives its guard from the lock state
  expectedEnvelopeVersion?: number;
  newVmkVersion?: number;
  wrappedNewVmk?: Uint8Array;
  newEncryptedName?: Uint8Array;
}): Promise<{
  rotationState: RotationState;
  rotationLockedAt: number | null;
  currentVmkVersion: number;
  envelopeVersion: number;
}> {
  const out = await makeClient().send(new UpdateVaultRotationCommand(args));
  return {
    rotationState: out.rotationState ?? 'IDLE',
    rotationLockedAt: out.rotationLockedAt ?? null,
    currentVmkVersion: out.currentVmkVersion ?? 0,
    envelopeVersion: out.envelopeVersion ?? 0,
  };
}
