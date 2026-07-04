import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const { mockSession } = vi.hoisted(() => ({
  mockSession: { logout: vi.fn(), rotationInterrupted: false },
}));
vi.mock('../auth/SessionContext', () => ({ useSession: () => mockSession }));
vi.mock('./FileUpload', () => ({ default: () => <div>file-upload</div>, MAX_FILE_SIZE_BYTES: 1 }));
vi.mock('./FileList', () => ({ default: ({ refreshKey }: { refreshKey: number }) => <div>file-list:{refreshKey}</div> }));
vi.mock('./CollectionSidebar', () => ({ default: () => <div>sidebar</div> }));
vi.mock('./TagSearch', () => ({ default: () => <div>tag-search</div> }));
vi.mock('./ChangeVaultPassword', () => ({ default: () => <div>change-vault-password</div> }));

import Dashboard from './Dashboard';

beforeEach(() => {
  mockSession.rotationInterrupted = false;
});

describe('Dashboard', () => {
  it('shows the sidebar, upload control, tag search, and file list', () => {
    render(<Dashboard />);
    expect(screen.getByText('sidebar')).toBeInTheDocument();
    expect(screen.getByText('file-upload')).toBeInTheDocument();
    expect(screen.getByText('tag-search')).toBeInTheDocument();
    expect(screen.getByText(/file-list:/)).toBeInTheDocument();
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
});
