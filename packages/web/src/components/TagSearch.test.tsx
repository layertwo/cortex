import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));

import TagSearch from './TagSearch';

beforeEach(() => vi.clearAllMocks());

describe('TagSearch', () => {
  it('encrypts the query and emits a tag view', async () => {
    const onSearch = vi.fn();
    render(<TagSearch onSearch={onSearch} onClear={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/search tag/i), 'Beach');
    await userEvent.click(screen.getByRole('button', { name: /search/i }));
    await waitFor(() => expect(onSearch).toHaveBeenCalled());
    const view = onSearch.mock.calls[0][0];
    expect(view.kind).toBe('tag');
    expect(view.label).toBe('Beach');
    expect(typeof view.encryptedTag).toBe('string'); // base64
  });

  it('clear resets and emits onClear', async () => {
    const onClear = vi.fn();
    render(<TagSearch onSearch={vi.fn()} onClear={onClear} />);
    await userEvent.click(screen.getByRole('button', { name: /clear/i }));
    expect(onClear).toHaveBeenCalled();
  });
});
