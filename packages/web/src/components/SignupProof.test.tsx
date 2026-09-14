import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SignupProof from './SignupProof';

describe('SignupProof', () => {
  it('renders the proof grid with its four headline cards', () => {
    render(<SignupProof />);
    // Astryx's Grid renders a plain <div> (display:grid via stylex, no explicit
    // role="grid"), so its implicit ARIA role is "generic" and getByRole('grid')
    // finds nothing — checked against the Grid source in
    // @astryxdesign/core/src/Grid/Grid.tsx. The aria-label passes through as the
    // accessible name instead, so getByLabelText is the query that actually works.
    expect(screen.getByLabelText('Why Cortex')).toBeInTheDocument();
    expect(screen.getByText('0 bytes')).toBeInTheDocument();
    expect(screen.getByText('24 words')).toBeInTheDocument();
    expect(screen.getByText('Any file')).toBeInTheDocument();
    expect(screen.getByText('Your key')).toBeInTheDocument();
  });
});
