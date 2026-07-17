import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-helpers';
import CandidateProfile from './CandidateProfile';
import type { Candidate } from '../api/client';

// Mock hooks with controllable return values
let candidateReturn: Record<string, unknown> = {
  data: undefined,
  isLoading: false,
  isError: false,
};

vi.mock('../api/hooks', () => ({
  useCandidate: () => candidateReturn,
}));

const fullCandidate: Candidate = {
  id: 'c1',
  name: 'Jane Smith',
  email: 'jane@example.com',
  phone: '+1-555-0100',
  location: 'San Francisco, CA',
  years_experience: 8,
  skills: [
    { name: 'React', level: 'expert', years: 5 },
    { name: 'TypeScript', level: 'advanced', years: 4 },
    { name: 'Node.js', level: 'intermediate', years: 3 },
    { name: 'Python', level: 'advanced', years: 6 },
  ],
  experience: [
    {
      title: 'Senior Frontend Engineer',
      company: 'Tech Corp',
      location: 'San Francisco',
      start_date: '2020-01',
      end_date: '2024-06',
      description: 'Led frontend architecture',
    },
    {
      title: 'Frontend Developer',
      company: 'StartupCo',
      location: 'Remote',
      start_date: '2017-03',
      end_date: '2019-12',
      description: 'Built React applications',
    },
    {
      title: 'Junior Developer',
      company: 'WebAgency',
      start_date: '2016-06',
      end_date: '2017-02',
    },
  ],
  education: [
    {
      degree: 'M.S.',
      field: 'Computer Science',
      institution: 'Stanford University',
      graduation_date: '2016',
    },
    {
      degree: 'B.S.',
      field: 'Mathematics',
      institution: 'UC Berkeley',
      graduation_date: '2014',
    },
  ],
  certifications: [],
};

describe('CandidateProfile', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    candidateReturn = { data: undefined, isLoading: false, isError: false };
  });

  it('shows upload prompt when no candidateId', () => {
    renderWithProviders(<CandidateProfile />);

    expect(screen.getByText('Your Profile')).toBeInTheDocument();
    expect(
      screen.getByText(/Upload your CV to see your profile details/i)
    ).toBeInTheDocument();
  });

  it('shows loading skeletons when isLoading', () => {
    candidateReturn = { data: undefined, isLoading: true, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Your Profile')).toBeInTheDocument();
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
  });

  it('shows error state when isError', () => {
    candidateReturn = { data: undefined, isLoading: false, isError: true };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Your Profile')).toBeInTheDocument();
    expect(
      screen.getByText(/Failed to load candidate profile/i)
    ).toBeInTheDocument();
  });

  it('shows error state when candidate data is null', () => {
    candidateReturn = { data: null, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(
      screen.getByText(/Failed to load candidate profile/i)
    ).toBeInTheDocument();
  });

  it('renders profile header with name', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
  });

  it('renders avatar with initials', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('JS')).toBeInTheDocument();
  });

  it('renders years of experience', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('8 years experience')).toBeInTheDocument();
  });

  it('renders contact info - email', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
  });

  it('renders contact info - phone', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('+1-555-0100')).toBeInTheDocument();
  });

  it('renders contact info - location', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('San Francisco, CA')).toBeInTheDocument();
  });

  it('renders skills section with chips', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Skills')).toBeInTheDocument();
    expect(screen.getByText('React')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText('Node.js')).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
  });

  it('renders skills count chip', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('renders experience section with entries', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Experience')).toBeInTheDocument();
    expect(screen.getByText('Senior Frontend Engineer')).toBeInTheDocument();
    expect(screen.getByText(/Tech Corp/)).toBeInTheDocument();
    expect(screen.getByText('Frontend Developer')).toBeInTheDocument();
    expect(screen.getByText(/StartupCo/)).toBeInTheDocument();
  });

  it('renders experience dates', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('2020-01 – 2024-06')).toBeInTheDocument();
    expect(screen.getByText('2017-03 – 2019-12')).toBeInTheDocument();
  });

  it('renders education section with entries', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Education')).toBeInTheDocument();
    expect(screen.getByText('M.S. in Computer Science')).toBeInTheDocument();
    expect(screen.getByText('Stanford University')).toBeInTheDocument();
    expect(screen.getByText('B.S. in Mathematics')).toBeInTheDocument();
    expect(screen.getByText('UC Berkeley')).toBeInTheDocument();
  });

  it('renders graduation dates', () => {
    candidateReturn = { data: fullCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Graduated: 2016')).toBeInTheDocument();
    expect(screen.getByText('Graduated: 2014')).toBeInTheDocument();
  });

  it('handles candidate with no email/phone/location', () => {
    const minimalCandidate: Candidate = {
      ...fullCandidate,
      email: undefined,
      phone: undefined,
      location: undefined,
    };
    candidateReturn = { data: minimalCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.queryByText('jane@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('+1-555-0100')).not.toBeInTheDocument();
    expect(screen.queryByText('San Francisco, CA')).not.toBeInTheDocument();
  });

  it('handles candidate with no experience', () => {
    const noExpCandidate: Candidate = {
      ...fullCandidate,
      experience: [],
    };
    candidateReturn = { data: noExpCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.queryByText('Experience')).not.toBeInTheDocument();
  });

  it('handles candidate with no education', () => {
    const noEduCandidate: Candidate = {
      ...fullCandidate,
      education: [],
    };
    candidateReturn = { data: noEduCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.queryByText('Education')).not.toBeInTheDocument();
  });

  it('shows "Present" for experience with no end_date', () => {
    const currentExpCandidate: Candidate = {
      ...fullCandidate,
      experience: [
        {
          title: 'Lead Engineer',
          company: 'CurrentCo',
          start_date: '2024-01',
        },
      ],
    };
    candidateReturn = { data: currentExpCandidate, isLoading: false, isError: false };

    renderWithProviders(<CandidateProfile candidateId="c1" />);

    expect(screen.getByText('2024-01 – Present')).toBeInTheDocument();
  });
});
