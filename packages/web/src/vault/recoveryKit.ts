import { DEFAULT_VAULT_NAME } from './registry';

// The recovery kit is a plain-text file: the 24 words plus the vault's name and ID. The ID
// is not secret, but it is what a brand-new device needs to find the vault, because the
// backend cannot list vaults yet (design follow-up 1).
export function buildRecoveryKit(args: { name: string; vaultId: string; phrase: string; createdAt: Date }): string {
  const words = args.phrase.trim().split(/\s+/);
  const rows = Array.from({ length: Math.ceil(words.length / 3) }, (_, r) =>
    words
      .slice(r * 3, r * 3 + 3)
      .map((w, c) => `${String(r * 3 + c + 1).padStart(2, ' ')} ${w.padEnd(9)}`)
      .join(' '),
  );
  return [
    'CORTEX RECOVERY KIT',
    `Vault:    ${args.name}`,
    `Vault ID: ${args.vaultId}`,
    `Created:  ${args.createdAt.toISOString().slice(0, 10)}`,
    '',
    'Recovery phrase (24 words, in order):',
    ...rows,
    '',
    'Anyone with these words can open this vault. Keep this file offline:',
    'a printout or an encrypted drive, never email.',
    '',
    'To recover: open Cortex, log in, choose "Forgot your vault password?",',
    'then "Use a recovery kit file".',
    '',
  ].join('\n');
}

export function parseRecoveryKit(text: string): { vaultId: string; name: string; words: string[] } {
  if (!/CORTEX RECOVERY KIT/i.test(text)) throw new Error('Not a Cortex recovery kit');
  const vaultId = /^Vault ID:\s*(\S+)/im.exec(text)?.[1];
  const name = /^Vault:\s*(.+?)\s*$/im.exec(text)?.[1] ?? DEFAULT_VAULT_NAME;
  const afterHeading = text.split(/Recovery phrase[^\n]*\n/i)[1] ?? '';
  const body = afterHeading.split(/\n\s*\n/)[0] ?? '';
  const words = body
    .split(/\s+/)
    .filter((t) => t && !/^\d+[.)]?$/.test(t))
    .map((t) => t.toLowerCase());
  if (!vaultId || words.length !== 24) throw new Error('Not a Cortex recovery kit');
  return { vaultId, name, words };
}

export function downloadRecoveryKit(kit: string, name: string): void {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'vault';
  const url = URL.createObjectURL(new Blob([kit], { type: 'text/plain' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `cortex-recovery-kit-${slug}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Deferred: revoking synchronously has cancelled the download in some engines.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
