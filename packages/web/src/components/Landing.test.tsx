import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const navigate = vi.hoisted(() => vi.fn());
vi.mock('react-router-dom', async (o) => ({
  ...(await o<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import Landing from './Landing';

beforeEach(() => vi.clearAllMocks());

describe('Landing', () => {
  it('shows the hero headline and both calls to action', () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/a vault for your memories/i);
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
  });

  it('navigates with the fromLanding flag so the next card slides in', async () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(navigate).toHaveBeenCalledWith('/signup', { state: { fromLanding: true } });
    await userEvent.click(screen.getByRole('button', { name: /log in/i }));
    expect(navigate).toHaveBeenCalledWith('/login', { state: { fromLanding: true } });
  });
});
