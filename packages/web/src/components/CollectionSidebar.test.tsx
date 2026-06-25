import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32) })),
  listCollections: vi.fn(async () => [
    { collectionId: 'c1', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), itemCount: 2, createdAt: new Date(0), updatedAt: new Date(0) },
  ]),
  createCollection: vi.fn(async () => 'c2'),
  deleteCollection: vi.fn(async () => {}),
  encryptCollectionName: vi.fn(async () => new Uint8Array([9])),
  decryptCollectionName: vi.fn(() => 'Trip 2026'),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../api/collections', () => ({
  listCollections: h.listCollections,
  createCollection: h.createCollection,
  deleteCollection: h.deleteCollection,
  updateCollection: vi.fn(),
}));
vi.mock('../items/collectionMetadata', () => ({
  encryptCollectionName: h.encryptCollectionName,
  decryptCollectionName: h.decryptCollectionName,
}));

import CollectionSidebar from './CollectionSidebar';

beforeEach(() => vi.clearAllMocks());

describe('CollectionSidebar', () => {
  it('lists decrypted collection names with an All files entry', async () => {
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} />);
    expect(await screen.findByText('Trip 2026')).toBeInTheDocument();
    expect(screen.getByText(/all files/i)).toBeInTheDocument();
  });

  it('selecting a collection calls onSelect with its id+name', async () => {
    const onSelect = vi.fn();
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={onSelect} refreshKey={0} />);
    await userEvent.click(await screen.findByText('Trip 2026'));
    expect(onSelect).toHaveBeenCalledWith({ kind: 'collection', id: 'c1', name: 'Trip 2026' });
  });

  it('creating a collection encrypts the name and calls the API', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('Receipts');
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} />);
    await userEvent.click(await screen.findByRole('button', { name: /new collection/i }));
    await waitFor(() => expect(h.createCollection).toHaveBeenCalledWith('v1', expect.any(Uint8Array)));
    expect(h.encryptCollectionName).toHaveBeenCalledWith('Receipts', expect.any(Uint8Array));
  });
});
