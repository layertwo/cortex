import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, within, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const h = vi.hoisted(() => ({
  getVaultKeys: vi.fn(async () => ({ vaultId: 'v1', kek: new Uint8Array(32), metadataKey: new Uint8Array(32), kekVersion: 1 })),
  listAllCollections: vi.fn(async () => [
    { collectionId: 'c1', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), itemCount: 2, createdAt: new Date(0), updatedAt: new Date(0) },
  ]),
  createCollection: vi.fn(async () => 'c2'),
  deleteCollection: vi.fn(async () => {}),
  encryptCollectionName: vi.fn(async () => new Uint8Array([9])),
  decryptCollectionName: vi.fn(() => 'Trip 2026'),
}));
vi.mock('../vault/keyAccess', () => ({ getVaultKeys: h.getVaultKeys }));
vi.mock('../api/collections', () => ({
  listAllCollections: h.listAllCollections,
  createCollection: h.createCollection,
  deleteCollection: h.deleteCollection,
  updateCollection: vi.fn(),
}));
vi.mock('../items/collectionMetadata', () => ({
  encryptCollectionName: h.encryptCollectionName,
  decryptCollectionName: h.decryptCollectionName,
}));

import CollectionSidebar from './CollectionSidebar';

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

  it('creating a collection opens a dialog, encrypts the name and calls the API', async () => {
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} />);
    await userEvent.click(await screen.findByRole('button', { name: /new collection/i }));
    await userEvent.type(screen.getByLabelText(/collection name/i), 'Receipts');
    await userEvent.click(screen.getByRole('button', { name: /^create$/i }));
    await waitFor(() => expect(h.createCollection).toHaveBeenCalledWith('v1', expect.any(Uint8Array), 1));
    expect(h.encryptCollectionName).toHaveBeenCalledWith('Receipts', expect.any(Uint8Array));
  });

  it('deleting a collection asks for confirmation first', async () => {
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} />);
    await userEvent.click(await screen.findByRole('button', { name: /delete trip 2026/i }));
    expect(h.deleteCollection).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: /delete collection/i }));
    await waitFor(() => expect(h.deleteCollection).toHaveBeenCalledWith('c1', 'v1'));
  });

  it('shows a create failure inside the dialog and keeps it open', async () => {
    h.createCollection.mockRejectedValueOnce(new Error('quota exceeded'));
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} />);
    await userEvent.click(await screen.findByRole('button', { name: /new collection/i }));
    await userEvent.type(screen.getByLabelText(/collection name/i), 'Receipts');
    await userEvent.click(screen.getByRole('button', { name: /^create$/i }));
    // The alert must be INSIDE the still-open dialog; a sidebar-level banner would be
    // hidden behind the modal backdrop (jsdom cannot see stacking, so scope the query).
    const dialog = screen.getByRole('dialog', { name: /new collection/i });
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/quota exceeded/i);
  });

  it('closes the confirmation and shows the error when delete fails', async () => {
    h.deleteCollection.mockRejectedValueOnce(new Error('server down'));
    render(<CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} />);
    await userEvent.click(await screen.findByRole('button', { name: /delete trip 2026/i }));
    await userEvent.click(screen.getByRole('button', { name: /delete collection/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/server down/i);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('a new onLoaded identity does not refetch', async () => {
    const { rerender } = render(
      <CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} onLoaded={() => {}} />,
    );
    await waitFor(() => expect(h.listAllCollections).toHaveBeenCalledTimes(1));

    // Same refreshKey, brand-new inline callback instance — must NOT trigger a refetch.
    rerender(
      <CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={0} onLoaded={() => {}} />,
    );
    await act(async () => {});
    expect(h.listAllCollections).toHaveBeenCalledTimes(1);

    // A real refreshKey bump still refetches, and the CURRENT callback is the one invoked.
    h.listAllCollections.mockResolvedValueOnce([
      { collectionId: 'c1', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), itemCount: 2, createdAt: new Date(0), updatedAt: new Date(0) },
      { collectionId: 'c2', vaultId: 'v1', encryptedMetadata: new Uint8Array([1]), itemCount: 0, createdAt: new Date(0), updatedAt: new Date(0) },
    ]);
    const onLoaded = vi.fn();
    rerender(
      <CollectionSidebar selected={{ kind: 'all' }} onSelect={vi.fn()} refreshKey={1} onLoaded={onLoaded} />,
    );
    await waitFor(() => expect(h.listAllCollections).toHaveBeenCalledTimes(2));
    expect(onLoaded).toHaveBeenCalledWith(2);
  });
});
