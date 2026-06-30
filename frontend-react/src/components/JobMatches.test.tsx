import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import JobMatches from './JobMatches';

// Mock the hooks that fetch data
vi.mock('../api/hooks', () => ({
  useMatches: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
  useMatchJobs: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

describe('JobMatches', () => {
  it('shows upload prompt when no candidateId', () => {
    renderWithProviders(<JobMatches />);

    expect(screen.getByText('Job Matches')).toBeInTheDocument();
    expect(screen.getByText(/Upload your CV to see job matches/i)).toBeInTheDocument();
  });

  it('shows matches section title with candidateId', async () => {
    const { useMatches } = await import('../api/hooks');
    vi.mocked(useMatches).mockReturnValue({
      data: [
        {
          job_id: 'j1',
          job_title: 'Frontend Developer',
          company: 'Acme',
          match_score: 85,
          tier: 'STRONG_MATCH' as const,
          required_met: true,
          preferred_met: 2,
        },
      ],
      isLoading: false,
      isError: false,
    } as any);

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('Job Matches')).toBeInTheDocument();
  });
});
