import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import ScreeningPanel from './ScreeningPanel';

// Mock gRPC client and screening progress
vi.mock('../api/grpcClient', () => ({
  startScreening: vi.fn(),
  submitAnswer: vi.fn(),
  getScreeningResult: vi.fn(),
}));

vi.mock('../api/useScreeningProgress', () => ({
  useScreeningProgress: () => ({ progress: null }),
}));

describe('ScreeningPanel', () => {
  const defaultProps = {
    candidateId: 'c1',
    jobId: 'j1',
    jobTitle: 'Frontend Developer',
    matchTier: 'STRONG_MATCH',
    onComplete: vi.fn(),
    onCancel: vi.fn(),
  };

  it('shows loading state when starting', () => {
    // startScreening is mocked so useEffect triggers "starting" phase immediately
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    // The component enters "starting" phase and shows a CircularProgress + text
    expect(screen.getByText(/Starting screening for/i)).toBeInTheDocument();
    expect(screen.getByText(/Frontend Developer/)).toBeInTheDocument();
  });
});
