import { describe, it, expect, vi } from 'vitest';
import { buildRecoveryKit, parseRecoveryKit, downloadRecoveryKit } from './recoveryKit';

const WORDS = Array.from({ length: 24 }, (_, i) => `w${i + 1}`);
const PHRASE = WORDS.join(' ');

describe('recovery kit', () => {
  it('round-trips name, vault id and the 24 words', () => {
    const kit = buildRecoveryKit({ name: 'Family archive', vaultId: 'abc-123', phrase: PHRASE, createdAt: new Date('2026-09-11T00:00:00Z') });
    expect(kit).toContain('CORTEX RECOVERY KIT');
    expect(kit).toContain('Vault ID: abc-123');
    expect(kit).toContain('Created:  2026-09-11');
    expect(parseRecoveryKit(kit)).toEqual({ vaultId: 'abc-123', name: 'Family archive', words: WORDS });
  });

  it('tolerates re-flowed whitespace and numbering', () => {
    const messy = `CORTEX RECOVERY KIT\nVault: Personal\nVault ID: v1\n\nRecovery phrase (24 words, in order):\n${WORDS.map((w, i) => `${i + 1}. ${w}`).join('   ')}\n`;
    expect(parseRecoveryKit(messy).words).toEqual(WORDS);
  });

  it('rejects text that is not a kit', () => {
    expect(() => parseRecoveryKit('hello world')).toThrow(/not a cortex recovery kit/i);
    expect(() => parseRecoveryKit('CORTEX RECOVERY KIT\nVault ID: v1\nRecovery phrase (24 words, in order):\n one two')).toThrow();
  });

  it('downloads through a temporary anchor', () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:kit'), revokeObjectURL: vi.fn() });
    downloadRecoveryKit('KIT', 'Family archive');
    expect(click).toHaveBeenCalled();
    const a = click.mock.instances[0] as HTMLAnchorElement;
    expect(a.download).toBe('cortex-recovery-kit-family-archive.txt');
    click.mockRestore();
    vi.unstubAllGlobals();
  });
});
