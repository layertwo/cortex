import { getCurrentUser } from 'aws-amplify/auth';

// The Cognito subject of the signed-in user, resolved once after sign-in and kept in
// localStorage so the synchronous registry readers (guards, keyAccess) can namespace
// their keys without an async hop. Cleared on logout.
export const ACCOUNT_KEY = 'cortex_account';

export function getAccountId(): string | null {
  return localStorage.getItem(ACCOUNT_KEY);
}

export async function resolveAccount(): Promise<string> {
  const { userId } = await getCurrentUser();
  localStorage.setItem(ACCOUNT_KEY, userId);
  return userId;
}

export function clearAccount(): void {
  localStorage.removeItem(ACCOUNT_KEY);
}
