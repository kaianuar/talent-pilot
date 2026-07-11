import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/test-utils';
import JobMatches from './JobMatches';

// Mock store with controllable state
const mockStore: Record<string, unknown> = {
  selectedJobId: null,
  selectedJobTitle: null,
  setSelectedJob: vi.fn(),
};

vi.mock('../store', () => ({
  useAppStore: Object.assign(
    (selector?: (s: Record<string, unknown>) => unknown) =>
      selector ? selector(mockStore) : mockStore,
    {
      getState: () => mockStore,
    }
  ),
}));

// Mock hooks with controllable return values
const mockMutateAsync = vi.fn();
let matchesReturn: Record<string, unknown> = {
  data: undefined,
  isLoading: false,
  isError: false,
};

vi.mock('../api/hooks', () => ({
  useMatches: () => matchesReturn,
  useMatchJobs: () => ({
    mutateAsync: mockMutateAsync,
    mutate: mockMutateAsync,
    isPending: false,
  }),
}));

const sampleMatch = {
  job_id: 'j1',
  job_title: 'Frontend Developer',
  company: 'Acme Corp',
  match_score: 0.85,
  tier: 'STRONG_MATCH' as const,
  required_match_ratio: 0.9,
  adjacent_bonus: 0.1,
  experience_score: 0.8,
  llm_reasoning_score: 0.7,
  reasoning_explanation: 'Strong frontend skills match',
};

const partialMatch = {
  job_id: 'j2',
  job_title: 'Backend Developer',
  company: 'Tech Inc',
  match_score: 0.55,
  tier: 'PARTIAL_MATCH' as const,
  required_match_ratio: 0.6,
  adjacent_bonus: 0,
  experience_score: 0.5,
  llm_reasoning_score: 0.4,
  reasoning_explanation: 'Some backend experience',
};

const poorMatch = {
  job_id: 'j3',
  job_title: 'Data Scientist',
  company: 'DataCo',
  match_score: 0.25,
  tier: 'POOR_MATCH' as const,
  required_match_ratio: 0.3,
  adjacent_bonus: 0,
  experience_score: 0.2,
  llm_reasoning_score: 0.1,
  reasoning_explanation: 'Limited data science background',
};

describe('JobMatches', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    matchesReturn = { data: undefined, isLoading: false, isError: false };
  });

  it('shows upload prompt when no candidateId', () => {
    renderWithProviders(<JobMatches />);

    expect(screen.getByText('Job Matches')).toBeInTheDocument();
    expect(screen.getByText(/Upload your CV to see job matches/i)).toBeInTheDocument();
  });

  it('shows matches section title with candidateId', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('Job Matches')).toBeInTheDocument();
  });

  it('shows loading skeletons when isLoading', () => {
    matchesReturn = { data: undefined, isLoading: true, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('Job Matches')).toBeInTheDocument();
    // Skeleton components render as divs with role="progressbar" or just visual
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });

  it('shows error state with retry button', () => {
    matchesReturn = { data: undefined, isLoading: false, isError: true };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('Job Matches')).toBeInTheDocument();
    expect(screen.getByText(/Failed to load job matches/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
  });

  it('shows empty state when no matches', () => {
    matchesReturn = { data: [], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText(/No job matches found/i)).toBeInTheDocument();
  });

  it('renders match card with job title and company', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('Frontend Developer')).toBeInTheDocument();
    expect(screen.getByText(/Strong Match/i)).toBeInTheDocument();
  });

  it('renders match score percentage', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('renders skills match chip', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('90% skills match')).toBeInTheDocument();
  });

  it('renders adjacent bonus chip when bonus > 0', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('+10% adjacent skills')).toBeInTheDocument();
  });

  it('renders Start Screening button', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByRole('button', { name: /Start Screening/i })).toBeInTheDocument();
  });

  it('sets selected job when Start Screening is clicked', async () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    await user.click(screen.getByRole('button', { name: /Start Screening/i }));

    expect(mockStore.setSelectedJob).toHaveBeenCalledWith('j1', 'Frontend Developer');
  });

  it('renders multiple match cards with different tiers (above threshold)', () => {
    matchesReturn = {
      data: [sampleMatch, partialMatch, poorMatch],
      isLoading: false,
      isError: false,
    };

    renderWithProviders(<JobMatches candidateId="c1" />);

    // sampleMatch (0.85) and partialMatch (0.55) are above 0.50 threshold
    expect(screen.getByText('Frontend Developer')).toBeInTheDocument();
    expect(screen.getByText('Backend Developer')).toBeInTheDocument();
    expect(screen.getByText('Strong Match')).toBeInTheDocument();
    expect(screen.getByText('Partial Match')).toBeInTheDocument();

    // poorMatch (0.25) is filtered out — below 0.50 threshold
    expect(screen.queryByText('Data Scientist')).not.toBeInTheDocument();
    expect(screen.queryByText('Poor Match')).not.toBeInTheDocument();
  });

  it('displays match count badge', () => {
    matchesReturn = {
      data: [sampleMatch, partialMatch],
      isLoading: false,
      isError: false,
    };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('matches')).toBeInTheDocument();
  });

  it('renders "Roles ranked by fit" subtitle', () => {
    matchesReturn = { data: [sampleMatch], isLoading: false, isError: false };

    renderWithProviders(<JobMatches candidateId="c1" />);

    expect(screen.getByText('Roles ranked by fit for this candidate')).toBeInTheDocument();
  });
});
