import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import CandidateProfile from './CandidateProfile';

// Mock the hooks module
vi.mock('../api/hooks', () => ({
  useCandidate: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
}));

describe('CandidateProfile', () => {
  it('shows upload prompt when no candidateId', () => {
    renderWithProviders(<CandidateProfile />);

    expect(screen.getByText('Your Profile')).toBeInTheDocument();
    expect(screen.getByText(/Upload your CV to see your profile details/i)).toBeInTheDocument();
  });
});
