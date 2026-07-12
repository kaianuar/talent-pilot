import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/test-utils';
import ScreeningPanel from './ScreeningPanel';
import type {
  StartScreeningResponse,
  SubmitAnswerResponse,
  GetScreeningResultResponse,
} from '../generated/screening';

// Mutable mock implementations
const mockStartScreening = vi.fn();
const mockSubmitAnswer = vi.fn();
const mockGetScreeningResult = vi.fn();
let submitApplicationError: Error | null = null;
let submitApplicationPending = false;

vi.mock('../api/grpcClient', () => ({
  startScreening: (...args: unknown[]) => mockStartScreening(...args),
  submitAnswer: (...args: unknown[]) => mockSubmitAnswer(...args),
  getScreeningResult: (...args: unknown[]) => mockGetScreeningResult(...args),
}));

vi.mock('../api/useScreeningProgress', () => ({
  useScreeningProgress: () => ({ progress: null }),
}));

vi.mock('../api/hooks', () => ({
  useSubmitApplication: () => {
    const impl = async (vars: unknown) => {
      if (submitApplicationError) throw submitApplicationError;
      return { status: 'sent', message_id: 'm1', vars };
    };
    return { mutateAsync: impl, isPending: submitApplicationPending, isError: !!submitApplicationError };
  },
}));

const successStartResponse: StartScreeningResponse = {
  screeningId: 'screen-1',
  success: true,
  errorMessage: '',
  firstQuestion: {
    id: 'q1',
    text: 'Tell me about your experience with React.',
    type: 'TECHNICAL_DEPTH',
    focusArea: 'frontend',
    expectedEvidence: ['hooks', 'components'],
    priority: 'REQUIRED',
  },
};

const failStartResponse: StartScreeningResponse = {
  screeningId: '',
  success: false,
  errorMessage: 'Candidate not found',
  firstQuestion: undefined,
};

const submitAnswerNextResponse: SubmitAnswerResponse = {
  assessment: {
    questionId: 'q1',
    quality: 'good',
    confidence: 0.8,
    keyPointsIdentified: ['state management'],
    gapsIdentified: [],
    decision: 'proceed_to_next',
    reasoning: 'Solid answer with relevant examples',
  },
  nextQuestion: {
    id: 'q2',
    text: 'How do you handle state management?',
    type: 'TECHNICAL_DEPTH',
    focusArea: 'frontend',
    expectedEvidence: ['redux', 'context'],
    priority: 'REQUIRED',
  },
  isComplete: false,
  emailDraft: undefined,
};

const submitAnswerCompleteResponse: SubmitAnswerResponse = {
  assessment: {
    questionId: 'q1',
    quality: 'excellent',
    confidence: 0.95,
    keyPointsIdentified: ['leadership', 'technical depth'],
    gapsIdentified: [],
    decision: 'skip_to_email',
    reasoning: 'Outstanding candidate',
  },
  nextQuestion: undefined,
  isComplete: true,
  emailDraft: {
    to: 'recruiter@acme.com',
    subject: 'Screening Complete - Jane Smith',
    body: 'The candidate performed well.',
    cc: '',
    bcc: '',
  },
};

const finalResult: GetScreeningResultResponse = {
  success: true,
  errorMessage: '',
  qaHistory: [],
  summary: {
    screeningId: 'screen-1',
    candidateId: 'c1',
    jobId: 'j1',
    status: 'COMPLETE',
    totalQuestionsAsked: 3,
    averageAnswerQuality: 0.85,
    finalAssessment: 'Strong candidate for the role',
    sufficientEvidence: true,
    terminationReason: '',
    createdAt: '2024-01-01T00:00:00Z',
    completedAt: '2024-01-01T00:10:00Z',
  },
  emailDraft: {
    to: 'recruiter@acme.com',
    subject: 'Screening Complete - Jane Smith',
    body: 'The candidate demonstrated strong technical skills.',
    cc: '',
    bcc: '',
  },
};

const defaultProps = {
  candidateId: 'c1',
  jobId: 'j1',
  jobTitle: 'Frontend Developer',
  matchTier: 'STRONG_MATCH',
  matchScore: 0.85,
  onComplete: vi.fn(),
  onCancel: vi.fn(),
};

/** Helper to fill answer and click submit */
async function fillAndSubmitAnswer(user: ReturnType<typeof userEvent.setup>, answerText: string) {
  const textarea = screen.getByPlaceholderText('Type your answer...');
  await user.type(textarea, answerText);
  // The submit button is an icon-only button (no text) next to the textarea
  const allButtons = screen.getAllByRole('button');
  const submitBtn = allButtons.find(
    (b) => b.querySelector('[data-testid="SendIcon"]') !== null
  );
  if (!submitBtn) throw new Error('Could not find submit button with SendIcon');
  await user.click(submitBtn);
}

describe('ScreeningPanel', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    mockStartScreening.mockResolvedValue(successStartResponse);
    mockSubmitAnswer.mockResolvedValue(submitAnswerNextResponse);
    mockGetScreeningResult.mockResolvedValue(finalResult);
    submitApplicationError = null;
    submitApplicationPending = false;
  });

  it('shows loading state when starting', async () => {
    mockStartScreening.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    expect(screen.getByText(/Starting screening for/i)).toBeInTheDocument();
    expect(screen.getByText(/Frontend Developer/)).toBeInTheDocument();
  });

  it('shows error state when startScreening fails', async () => {
    mockStartScreening.mockResolvedValue(failStartResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Candidate not found')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Go Back/i })).toBeInTheDocument();
  });

  it('shows error state when startScreening throws', async () => {
    mockStartScreening.mockRejectedValue(new Error('Connection refused'));

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Connection refused')).toBeInTheDocument();
    });
  });

  it('displays first question after successful start', async () => {
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText('Tell me about your experience with React.')
      ).toBeInTheDocument();
    });
  });

  it('shows question progress indicator', async () => {
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Question 1 of 3')).toBeInTheDocument();
    });
  });

  it('renders answer input field', async () => {
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });
  });

  it('submit button is disabled when answer is empty', async () => {
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    // Submit button (icon-only) should be disabled when answer is empty
    const sendIcon = screen.getByTestId('SendIcon');
    const submitBtn = sendIcon.closest('button');
    expect(submitBtn).toBeDisabled();
  });

  it('submits answer and shows next question', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'I have 5 years of React experience with hooks and context.');

    await waitFor(() => {
      expect(mockSubmitAnswer).toHaveBeenCalledWith(
        'screen-1',
        'c1',
        'q1',
        'I have 5 years of React experience with hooks and context.',
      );
    });

    // Wait for assessment + next question (1.5s delay)
    await waitFor(() => {
      expect(
        screen.getByText('How do you handle state management?')
      ).toBeInTheDocument();
    }, { timeout: 3000 });
    vi.useRealTimers();
  });

  it('displays assessment feedback after submitting answer', async () => {
    mockSubmitAnswer.mockResolvedValue({
      ...submitAnswerNextResponse,
      nextQuestion: undefined,
      assessment: {
        quality: 'good',
        confidence: 0.8,
        decision: 'proceed_to_next',
        reasoning: 'Good technical depth',
      },
    });

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'I use React hooks extensively.');

    await waitFor(() => {
      expect(screen.getByText(/Good technical depth/i)).toBeInTheDocument();
    });
  });

  it('shows error when submitAnswer fails', async () => {
    mockSubmitAnswer.mockRejectedValue(new Error('Network timeout'));

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'My answer');

    await waitFor(() => {
      expect(screen.getByText('Network timeout')).toBeInTheDocument();
    });
  });

  it('renders completion state with email draft', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Strong answer demonstrating expertise.');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    expect(screen.getByText('Email Draft')).toBeInTheDocument();
    expect(screen.getByText(/recruiter@acme\.com/)).toBeInTheDocument();
    expect(screen.getByText(/Screening Complete - Jane Smith/)).toBeInTheDocument();
    expect(
      screen.getByText(/The candidate demonstrated strong technical skills/i)
    ).toBeInTheDocument();
  });

  it('renders completion summary chips', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    expect(screen.getByText('3 questions answered')).toBeInTheDocument();
    expect(screen.getByText(/Status: COMPLETE/)).toBeInTheDocument();
    expect(screen.getByText(/Strong candidate for the role/i)).toBeInTheDocument();
  });

  it('shows Send to Recruiter and Apply for a Different Position buttons on completion', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /Send to Recruiter/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Apply for a Different Position/i })).toBeInTheDocument();
  });

  it('does NOT auto-fire onComplete when screening finishes (regression)', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    // Result screen must be visible AND onComplete must not have been called yet.
    // Auto-firing onComplete here would unmount the panel before the user reads the result.
    expect(defaultProps.onComplete).not.toHaveBeenCalled();
    expect(screen.getByText('Email Draft')).toBeInTheDocument();
  });

  it('calls onCancel when Apply for a Different Position is clicked', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Apply for a Different Position/i }));

    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it('shows Sending state while submitApplication is in flight, then fires onComplete', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    const sendBtn = screen.getByRole('button', { name: /Send to Recruiter/i });
    await user.click(sendBtn);

    // onComplete fires only after the mutation resolves.
    await waitFor(() => {
      expect(defaultProps.onComplete).toHaveBeenCalledWith(finalResult);
    });
  });

  it('surfaces an inline error and keeps the panel mounted when send fails', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);
    submitApplicationError = new Error('Email service unavailable');

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Send to Recruiter/i }));

    // Error is surfaced; the panel does not unmount.
    await waitFor(() => {
      expect(screen.getByText('Email service unavailable')).toBeInTheDocument();
    });
    expect(defaultProps.onComplete).not.toHaveBeenCalled();

    // Button relabels to Try Again and is enabled.
    const retryBtn = screen.getByRole('button', { name: /Try Again/i });
    expect(retryBtn).toBeEnabled();
  });

  it('recovers from a failed send and fires onComplete on retry', async () => {
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);
    submitApplicationError = new Error('Network timeout');

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Send to Recruiter/i }));

    await waitFor(() => {
      expect(screen.getByText('Network timeout')).toBeInTheDocument();
    });

    // Clear the error and retry — should now succeed.
    submitApplicationError = null;
    await user.click(screen.getByRole('button', { name: /Try Again/i }));

    await waitFor(() => {
      expect(defaultProps.onComplete).toHaveBeenCalledWith(finalResult);
    });
  });

  it('calls onCancel when Cancel Screening is clicked', async () => {
    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Cancel Screening')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Cancel Screening'));

    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it('calls onCancel when Go Back is clicked in error state', async () => {
    mockStartScreening.mockResolvedValue(failStartResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Candidate not found')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Go Back/i }));

    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it('increments both counter and total on probe (no "Question 4 of 3")', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    // First answer → probe_for_clarity (additional question needed)
    mockSubmitAnswer.mockResolvedValueOnce({
      assessment: {
        questionId: 'q1',
        quality: 'vague',
        confidence: 0.6,
        keyPointsIdentified: [],
        gapsIdentified: ['no specific example'],
        decision: 'probe_for_clarity',
        reasoning: 'Answer is too vague — probing for specifics.',
      },
      nextQuestion: {
        id: 'q1-probe',
        text: 'Can you walk me through a specific project where you used OAuth?',
        type: 'GAP_PROBE',
        focusArea: 'oauth',
        expectedEvidence: ['specific project', 'token storage'],
        priority: 'REQUIRED',
      },
      isComplete: false,
      emailDraft: undefined,
    });

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Question 1 of 3')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'I have used OAuth.');

    // After probe: counter 1→2, total 3→4 → "Question 2 of 4"
    await waitFor(() => {
      expect(screen.getByText('Question 2 of 4')).toBeInTheDocument();
    }, { timeout: 3000 });

    expect(
      screen.getByText('Can you walk me through a specific project where you used OAuth?')
    ).toBeInTheDocument();

    vi.useRealTimers();
  });

  it('counter never exceeds total across multiple probes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    // Q1 answer → probe, Q1-probe answer → probe again
    mockSubmitAnswer.mockResolvedValueOnce({
      assessment: {
        questionId: 'q1',
        quality: 'vague',
        confidence: 0.5,
        keyPointsIdentified: [],
        gapsIdentified: ['no specifics'],
        decision: 'probe_for_clarity',
        reasoning: 'Too vague.',
      },
      nextQuestion: {
        id: 'q1-probe-1',
        text: 'Give me a specific example.',
        type: 'GAP_PROBE',
        focusArea: 'frontend',
        expectedEvidence: ['example'],
        priority: 'REQUIRED',
      },
      isComplete: false,
      emailDraft: undefined,
    });
    mockSubmitAnswer.mockResolvedValueOnce({
      assessment: {
        questionId: 'q1-probe-1',
        quality: 'vague',
        confidence: 0.5,
        keyPointsIdentified: [],
        gapsIdentified: ['still vague'],
        decision: 'probe_for_clarity',
        reasoning: 'Still too vague.',
      },
      nextQuestion: {
        id: 'q1-probe-2',
        text: 'What project did you work on?',
        type: 'GAP_PROBE',
        focusArea: 'frontend',
        expectedEvidence: ['project name'],
        priority: 'REQUIRED',
      },
      isComplete: false,
      emailDraft: undefined,
    });

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    // First probe: 1→2, total 3→4
    await fillAndSubmitAnswer(user, 'I use React.');
    await waitFor(() => {
      expect(screen.getByText('Question 2 of 4')).toBeInTheDocument();
    }, { timeout: 3000 });

    // Second probe: 2→3, total 4→5
    await fillAndSubmitAnswer(user, 'I built a web app.');
    await waitFor(() => {
      expect(screen.getByText('Question 3 of 5')).toBeInTheDocument();
    }, { timeout: 3000 });

    vi.useRealTimers();
  });

  it('hides Send to Recruiter and shows Back to Chat on rejection', async () => {
    const rejectedResult: GetScreeningResultResponse = {
      ...finalResult,
      summary: {
        ...finalResult.summary!,
        status: 'REJECTED',
        sufficientEvidence: false,
        finalAssessment: 'Unfortunately, your experience does not align with this role.',
      },
      emailDraft: undefined,
    };
    mockGetScreeningResult.mockResolvedValue(rejectedResult);
    mockSubmitAnswer.mockResolvedValue(submitAnswerCompleteResponse);

    renderWithProviders(<ScreeningPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type your answer...')).toBeInTheDocument();
    });

    await fillAndSubmitAnswer(user, 'Answer');

    await waitFor(() => {
      expect(screen.getByText('Screening Complete')).toBeInTheDocument();
    });

    // "Send to Recruiter" should NOT appear for rejected candidates
    expect(screen.queryByRole('button', { name: /Send to Recruiter/i })).not.toBeInTheDocument();
    // Should show "Back to Chat" instead of "Close"
    expect(screen.getByRole('button', { name: /Back to Chat/i })).toBeInTheDocument();
    // Rejection feedback should be visible
    expect(screen.getByText(/does not align/)).toBeInTheDocument();
  });
});
