import { getUserManager } from './oidc';

// The authenticated subject, resolved once after OIDC sign-in and kept in localStorage
// so the synchronous registry readers (guards, keyAccess) can namespace their keys
// without an async hop. Cleared on logout.
export const ACCOUNT_KEY = 'cortex_account';

export function getAccountId(): string | null {
  return localStorage.getItem(ACCOUNT_KEY);
}

// The OIDC ID token's subject is stable per account and namespaces the vault registry.
export async function resolveAccount(): Promise<string> {
  const user = await getUserManager().getUser();
  const sub = user && !user.expired ? user.profile.sub : undefined;
  if (!sub) throw new Error('Not authenticated');
  localStorage.setItem(ACCOUNT_KEY, sub);
  return sub;
}

export function clearAccount(): void {
  localStorage.removeItem(ACCOUNT_KEY);
}
