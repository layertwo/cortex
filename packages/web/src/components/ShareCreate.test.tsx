import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { generateDek, wrapDek } from '@cortex/encryption';
import type { FileMetadata } from '../items/metadata';

const h = vi.hoisted(() => ({
  createShare: vi.fn(async () => ({ shareId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' })),
}));
// Mock the API seam so the component never pulls in the Cognito client.
vi.mock('../api/shares', () => ({
  createShare: h.createShare,
  getPublicShare: vi.fn(),
  ShareFetchError: class extends Error {},
}));

import { ShareCreate } from './ShareCreate';

const contentId = 'content-1';
const kek = new Uint8Array(32).fill(3);
const meta: FileMetadata = {
  name: 'cat.png',
  contentType: 'image/png',
  size: 3,
  contentId,
  streamVersion: 1,
};

async function makeWrappedDek(): Promise<Uint8Array> {
  const dek = await generateDek();
  return wrapDek(dek, kek, contentId);
}

function renderForm(wrappedDek: Uint8Array) {
  return render(
    <ShareCreate
      itemId="i1"
      meta={meta}
      wrappedDek={wrappedDek}
      vaultKek={kek}
      onClose={() => {}}
    />,
  );
}

describe('ShareCreate', () => {
  it('creates a share link carrying the encrypted metadata and a fragment blob', async () => {
    renderForm(await makeWrappedDek());

    await userEvent.type(screen.getByLabelText(/password/i), 'Correct-Horse-Battery-9');
    await userEvent.click(screen.getByRole('button', { name: /create link/i }));

    const url = (await screen.findByLabelText(/share url/i)) as HTMLInputElement;
    expect(url.value).toMatch(/\/s\/a1b2c3d4-e5f6-7890-abcd-ef1234567890#.+/);
    expect(h.createShare).toHaveBeenCalledWith(
      expect.objectContaining({ itemId: 'i1', encryptedMetadata: expect.any(Uint8Array) }),
    );
  });

  it('keeps Create disabled until the password meets the minimum strength', async () => {
    renderForm(await makeWrappedDek());

    const create = screen.getByRole('button', { name: /create link/i });
    expect(create).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/password/i), 'short');
    expect(create).toBeDisabled();
  });
});
