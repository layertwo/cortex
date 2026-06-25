import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../auth/SessionContext', () => ({ useSession: () => ({ logout: vi.fn() }) }));
vi.mock('./FileUpload', () => ({ default: () => <div>file-upload</div>, MAX_FILE_SIZE_BYTES: 1 }));
vi.mock('./FileList', () => ({ default: ({ refreshKey }: { refreshKey: number }) => <div>file-list:{refreshKey}</div> }));
vi.mock('./CollectionSidebar', () => ({ default: () => <div>sidebar</div> }));
vi.mock('./TagSearch', () => ({ default: () => <div>tag-search</div> }));

import Dashboard from './Dashboard';

describe('Dashboard', () => {
  it('shows the sidebar, upload control, tag search, and file list', () => {
    render(<Dashboard />);
    expect(screen.getByText('sidebar')).toBeInTheDocument();
    expect(screen.getByText('file-upload')).toBeInTheDocument();
    expect(screen.getByText('tag-search')).toBeInTheDocument();
    expect(screen.getByText(/file-list:/)).toBeInTheDocument();
  });
});
