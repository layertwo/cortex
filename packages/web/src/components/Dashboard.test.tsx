import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect } from 'react';
import type { VaultEntry } from '../vault/registry';
import type { View } from './CollectionSidebar';

const { mockSession, fileListCounts } = vi.hoisted(() => ({
  mockSession: {
    logout: vi.fn(),
    rotationInterrupted: false,
    activeVault: { vaultId: 'v1', name: 'Personal' } as VaultEntry,
    vaultVersion: 0,
    vaults: [{ vaultId: 'v1', name: 'Personal' }],
    switchVault: vi.fn(),
  },
  // Overridable per-test so a test can start from a hasFiles: false state (default 3
  // matches every pre-existing test's expectation that the all-files view already has files).
  fileListCounts: { all: 3 },
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => mockSession }));
vi.mock('./UploadQueue', () => ({
  default: ({ onUploaded }: { onUploaded?: () => void }) => (
    <div>
      <span>upload-queue</span>
      <button onClick={() => onUploaded?.()}>Simulate upload</button>
    </div>
  ),
  MAX_FILE_SIZE_BYTES: 1,
}));
vi.mock('./FileList', () => ({
  default: ({ view, refreshKey, onLoaded }: { view: View; refreshKey: number; onLoaded?: (n: number) => void }) => {
    useEffect(() => {
      onLoaded?.(view.kind === 'all' ? fileListCounts.all : 0);
    }, [view]);
    return <div>file-list:{refreshKey}</div>;
  },
}));
vi.mock('./CollectionSidebar', () => ({
  default: ({ onSelect }: { onSelect: (v: View) => void }) => (
    <div>
      <span>sidebar</span>
      <button onClick={() => onSelect({ kind: 'collection', id: 'c1', name: 'Trip' })}>Select collection</button>
    </div>
  ),
}));
vi.mock('./TagSearch', () => ({ default: () => <div>tag-search</div> }));
vi.mock('./ChangeVaultPassword', () => ({ default: () => <div>change-vault-password</div> }));
vi.mock('./VaultSwitcher', () => ({ default: () => <div>vault-switcher</div> }));
vi.mock('./WelcomeCard', () => ({
  default: ({ hasFiles }: { hasFiles: boolean }) => <div data-has-files={String(hasFiles)}>welcome-card</div>,
}));

import Dashboard from './Dashboard';

beforeEach(() => {
  mockSession.rotationInterrupted = false;
  mockSession.activeVault = { vaultId: 'v1', name: 'Personal' };
  fileListCounts.all = 3;
});

describe('Dashboard', () => {
  it('shows the sidebar, upload control, tag search, and file list', () => {
    render(<Dashboard />);
    expect(screen.getByText('sidebar')).toBeInTheDocument();
    expect(screen.getByText('upload-queue')).toBeInTheDocument();
    expect(screen.getByText('tag-search')).toBeInTheDocument();
    expect(screen.getByText(/file-list:/)).toBeInTheDocument();
    expect(screen.getByText('welcome-card')).toBeInTheDocument();
  });

  it('does not bump refreshKey on initial mount', () => {
    render(<Dashboard />);
    expect(screen.getByText('file-list:0')).toBeInTheDocument();
  });

  it('shows "Change vault password" button when unlocked', () => {
    render(<Dashboard />);
    expect(screen.getByRole('button', { name: /change vault password/i })).toBeInTheDocument();
  });

  it('shows resume banner when rotationInterrupted is true', () => {
    mockSession.rotationInterrupted = true;
    render(<Dashboard />);
    expect(screen.getByText(/password change was interrupted/i)).toBeInTheDocument();
  });

  it('shows the resume banner when the server says the active vault is mid-rotation', () => {
    mockSession.activeVault = { vaultId: 'v1', name: 'Personal', rotationState: 'PAUSED' };
    render(<Dashboard />);
    expect(screen.getByText(/password change was interrupted/i)).toBeInTheDocument();
  });

  it('shows no banner for an IDLE vault when nothing was interrupted locally', () => {
    mockSession.activeVault = { vaultId: 'v1', name: 'Personal', rotationState: 'IDLE' };
    render(<Dashboard />);
    expect(screen.queryByText(/password change was interrupted/i)).toBeNull();
  });

  it('shows the active vault name beside the title', () => {
    render(<Dashboard />);
    expect(screen.getByText('Personal')).toBeInTheDocument();
  });

  it('keeps the welcome checklist file count from the all-files view only (spec §2.2)', async () => {
    render(<Dashboard />);
    await screen.findByText('welcome-card');
    expect(screen.getByText('welcome-card')).toHaveAttribute('data-has-files', 'true');
    await userEvent.click(screen.getByText('Select collection'));
    expect(screen.getByText('welcome-card')).toHaveAttribute('data-has-files', 'true');
  });

  it('bumps the welcome checklist file count on a successful upload even while browsing a non-all view (spec §2.2)', async () => {
    fileListCounts.all = 0;
    render(<Dashboard />);
    await screen.findByText('welcome-card');
    expect(screen.getByText('welcome-card')).toHaveAttribute('data-has-files', 'false');
    await userEvent.click(screen.getByText('Select collection'));
    expect(screen.getByText('welcome-card')).toHaveAttribute('data-has-files', 'false');
    await userEvent.click(screen.getByText('Simulate upload'));
    expect(screen.getByText('welcome-card')).toHaveAttribute('data-has-files', 'true');
  });
});
