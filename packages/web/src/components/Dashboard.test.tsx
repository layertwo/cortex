import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { VaultEntry } from '../vault/registry';

const { mockSession } = vi.hoisted(() => ({
  mockSession: {
    logout: vi.fn(),
    rotationInterrupted: false,
    activeVault: { vaultId: 'v1', name: 'Personal' } as VaultEntry,
    vaultVersion: 0,
    vaults: [{ vaultId: 'v1', name: 'Personal' }],
    switchVault: vi.fn(),
  },
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => mockSession }));
vi.mock('./UploadQueue', () => ({ default: () => <div>upload-queue</div>, MAX_FILE_SIZE_BYTES: 1 }));
vi.mock('./FileList', () => ({ default: ({ refreshKey }: { refreshKey: number }) => <div>file-list:{refreshKey}</div> }));
vi.mock('./CollectionSidebar', () => ({ default: () => <div>sidebar</div> }));
vi.mock('./TagSearch', () => ({ default: () => <div>tag-search</div> }));
vi.mock('./ChangeVaultPassword', () => ({ default: () => <div>change-vault-password</div> }));
vi.mock('./VaultSwitcher', () => ({ default: () => <div>vault-switcher</div> }));
vi.mock('./WelcomeCard', () => ({ default: () => <div>welcome-card</div> }));

import Dashboard from './Dashboard';

beforeEach(() => {
  mockSession.rotationInterrupted = false;
  mockSession.activeVault = { vaultId: 'v1', name: 'Personal' };
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
});
