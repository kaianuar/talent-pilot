import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/test-utils';
import ChatInterface from './ChatInterface';

// Mutable mock state so individual tests can override
const mockChatMutateAsync = vi.fn();
const mockUploadMutateAsync = vi.fn();
const mockSubmitMutateAsync = vi.fn();

let chatPending = false;
let chatError = false;
let uploadError = false;
let submitPending = false;

vi.mock('../api/hooks', () => ({
  useChat: () => ({
    mutateAsync: mockChatMutateAsync,
    isPending: chatPending,
    isError: chatError,
  }),
  useUploadResume: () => ({
    mutateAsync: mockUploadMutateAsync,
    isPending: false,
    isError: uploadError,
  }),
  useSubmitApplication: () => ({
    mutateAsync: mockSubmitMutateAsync,
    isPending: submitPending,
    isError: false,
  }),
}));

// Mock store with controllable state
const mockStore: Record<string, unknown> = {
  candidateId: null,
  selectedJobId: null,
  selectedJobTitle: null,
  matches: [],
  chatHistory: [],
  addMessage: vi.fn(),
  clearChat: vi.fn(),
  setCandidate: vi.fn(),
  lastSentApplication: null,
  clearAnnouncedApplication: vi.fn(),
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

describe('ChatInterface', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    chatPending = false;
    chatError = false;
    uploadError = false;
    submitPending = false;
    mockStore.selectedJobId = null;
    mockStore.selectedJobTitle = null;
    mockStore.matches = [];
    mockStore.lastSentApplication = null;
  });

  it('renders the welcome message', () => {
    renderWithProviders(<ChatInterface />);

    expect(
      screen.getByText(/I'm TalentPilot, your AI recruiting assistant/i)
    ).toBeInTheDocument();
  });

  it('renders the text input with placeholder', () => {
    renderWithProviders(<ChatInterface />);

    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
  });

  it('renders helper chips', () => {
    renderWithProviders(<ChatInterface />);

    expect(screen.getByText('Show my matches')).toBeInTheDocument();
    expect(screen.getByText('Apply to a job')).toBeInTheDocument();
    expect(screen.getByText('View my profile')).toBeInTheDocument();
  });

  it('renders the file upload button', () => {
    renderWithProviders(<ChatInterface />);

    expect(screen.getByTitle('Upload CV (PDF)')).toBeInTheDocument();
  });

  it('disables send button when input is empty', () => {
    renderWithProviders(<ChatInterface />);

    // The send IconButton (icon-only, no text) should be disabled
    const sendIcon = screen.getByTestId('SendIcon');
    const sendButton = sendIcon.closest('button');
    expect(sendButton).toBeDisabled();
  });

  it('helper chip "Show my matches" fills input', async () => {
    renderWithProviders(<ChatInterface />);

    await user.click(screen.getByText('Show my matches'));

    expect(screen.getByPlaceholderText('Type your message...')).toHaveValue(
      'Show me my job matches'
    );
  });

  it('helper chip "Apply to a job" fills input', async () => {
    renderWithProviders(<ChatInterface />);

    await user.click(screen.getByText('Apply to a job'));

    expect(screen.getByPlaceholderText('Type your message...')).toHaveValue(
      'I want to apply for a job'
    );
  });

  it('helper chip "View my profile" fills input', async () => {
    renderWithProviders(<ChatInterface />);

    await user.click(screen.getByText('View my profile'));

    expect(screen.getByPlaceholderText('Type your message...')).toHaveValue(
      'Show my profile'
    );
  });

  it('sends a message and displays the user message', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'Here are your matches!',
    });

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Show me jobs');
    await user.keyboard('{Enter}');

    expect(screen.getByText('Show me jobs')).toBeInTheDocument();
  });

  it('displays assistant response after sending', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'Here are your matches!',
    });

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Show me jobs');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByText('Here are your matches!')).toBeInTheDocument();
    });
  });

  it('clears input after sending', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'Got it!',
    });

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Show me jobs');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });

  it('displays error message when chat fails', async () => {
    mockChatMutateAsync.mockRejectedValue(new Error('Network error'));

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Hello');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(
        screen.getByText(/I apologize, but I encountered an error/i)
      ).toBeInTheDocument();
    });
  });

  it('shows upload error alert when upload fails', () => {
    uploadError = true;

    renderWithProviders(<ChatInterface />);

    expect(
      screen.getByText(/Failed to upload CV/i)
    ).toBeInTheDocument();
  });

  it('uploads a file successfully and shows success message', async () => {
    const onCandidateCreated = vi.fn();
    mockUploadMutateAsync.mockResolvedValue({
      candidate_id: 'c123',
      parsed: {
        name: 'John Doe',
        skills: [{ name: 'React' }, { name: 'TypeScript' }],
        years_experience: 5,
      },
    });

    const { container } = renderWithProviders(
      <ChatInterface onCandidateCreated={onCandidateCreated} />
    );

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy'], 'resume.pdf', { type: 'application/pdf' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(mockUploadMutateAsync).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText(/John Doe/)).toBeInTheDocument();
      expect(screen.getByText(/2 skills/)).toBeInTheDocument();
      expect(screen.getByText(/5 years of experience/)).toBeInTheDocument();
    });

    expect(onCandidateCreated).toHaveBeenCalledWith('c123');
  });

  it('shows error message when file upload fails', async () => {
    mockUploadMutateAsync.mockRejectedValue(new Error('Upload failed'));

    const { container } = renderWithProviders(<ChatInterface />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dummy'], 'resume.pdf', { type: 'application/pdf' });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(
        screen.getByText(/I apologize, but I encountered an error uploading/i)
      ).toBeInTheDocument();
    });
  });

  it('does nothing when file input is cancelled (no file)', async () => {
    const { container } = renderWithProviders(<ChatInterface />);

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(fileInput, { target: { files: [] } });

    // No upload mutation should be called
    expect(mockUploadMutateAsync).not.toHaveBeenCalled();
  });

  it('shows Send-to-Recruiter button when chat response mentions applying', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'I can help you apply to this position via email recruiter!',
    });

    mockStore.selectedJobId = 'j1';
    mockStore.selectedJobTitle = 'Frontend Developer';
    mockStore.matches = [
      { job_id: 'j1', match_score: 0.85, tier: 'STRONG_MATCH' },
    ];

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Apply to the job');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByText('Send to Recruiter')).toBeInTheDocument();
    });
  });

  it('shows confirmation text with job title in Send-to-Recruiter area', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'You can apply via email to the recruiter.',
    });

    mockStore.selectedJobId = 'j1';
    mockStore.selectedJobTitle = 'Frontend Developer';
    mockStore.matches = [
      { job_id: 'j1', match_score: 0.85, tier: 'STRONG_MATCH' },
    ];

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Apply');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByText(/Frontend Developer/)).toBeInTheDocument();
      expect(screen.getByText(/email the recruiter/)).toBeInTheDocument();
    });
  });

  it('dismisses Send-to-Recruiter area on cancel', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'Apply via email recruiter.',
    });

    mockStore.selectedJobId = 'j1';
    mockStore.selectedJobTitle = 'Frontend Developer';
    mockStore.matches = [];

    renderWithProviders(<ChatInterface />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Apply');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByText('Send to Recruiter')).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    await user.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByText('Send to Recruiter')).not.toBeInTheDocument();
    });
  });

  it('calls submitMutation when Send to Recruiter is clicked', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'I recommend you apply via email to the recruiter!',
    });
    mockSubmitMutateAsync.mockResolvedValue({ status: 'sent', message_id: 'm1' });

    mockStore.selectedJobId = 'j1';
    mockStore.selectedJobTitle = 'Frontend Developer';
    mockStore.matches = [
      { job_id: 'j1', match_score: 0.85, tier: 'STRONG_MATCH' },
    ];

    renderWithProviders(<ChatInterface candidateId="c1" />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Apply');
    await user.keyboard('{Enter}');

    // Wait for Send-to-Recruiter button
    await waitFor(() => {
      expect(screen.getByText('Send to Recruiter')).toBeInTheDocument();
    });

    // Click the "Send to Recruiter" button
    const sendBtn = screen.getByRole('button', { name: 'Send to Recruiter' });
    await user.click(sendBtn);

    await waitFor(() => {
      expect(mockSubmitMutateAsync).toHaveBeenCalledWith({
        candidateId: 'c1',
        jobId: 'j1',
        matchScore: 0.85,
        matchTier: 'STRONG_MATCH',
      });
    });
  });

  it('shows success message after sending to recruiter', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'Apply via email to the recruiter!',
    });
    mockSubmitMutateAsync.mockResolvedValue({ status: 'sent', message_id: 'm1' });

    mockStore.selectedJobId = 'j1';
    mockStore.selectedJobTitle = 'Frontend Developer';
    mockStore.matches = [
      { job_id: 'j1', match_score: 0.85, tier: 'STRONG_MATCH' },
    ];

    renderWithProviders(<ChatInterface candidateId="c1" />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Apply');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByText('Send to Recruiter')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Send to Recruiter' }));

    await waitFor(() => {
      expect(
        screen.getByText(/Your application for.*Frontend Developer.*has been sent/i)
      ).toBeInTheDocument();
    });
  });

  it('shows error message when submit to recruiter fails', async () => {
    mockChatMutateAsync.mockResolvedValue({
      assistant_text: 'Apply via email to the recruiter!',
    });
    mockSubmitMutateAsync.mockRejectedValue(new Error('Email failed'));

    mockStore.selectedJobId = 'j1';
    mockStore.selectedJobTitle = 'Frontend Developer';
    mockStore.matches = [];

    renderWithProviders(<ChatInterface candidateId="c1" />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Apply');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(screen.getByText('Send to Recruiter')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Send to Recruiter' }));

    await waitFor(() => {
      expect(
        screen.getByText(/Failed to send application/i)
      ).toBeInTheDocument();
    });
  });

  it('announces a successful application when lastSentApplication is set', async () => {
    // Stash an announcement in the store BEFORE rendering, as ScreeningPanel
    // does right before unmounting. The ChatInterface mount effect should
    // pick it up, post a confirmation message, and clear the field.
    mockStore.lastSentApplication = {
      jobId: 'j1',
      jobTitle: 'Frontend Developer',
      sentAt: Date.now(),
    };

    renderWithProviders(<ChatInterface candidateId="c1" />);

    // Confirmation message references the job title and asks about a
    // different job. The user can then click another job in the sidebar.
    await waitFor(() => {
      expect(
        screen.getByText(/has been sent to the recruiter/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/different job/i)
      ).toBeInTheDocument();
    });

    // The effect must clear the announcement so a remount (e.g. switching
    // tabs and back) does not re-fire the same message.
    expect(mockStore.clearAnnouncedApplication).toHaveBeenCalled();
  });

  it('posts the application confirmation exactly once', async () => {
    // Regression: a duplicate copy of the same message was being posted
    // by the announcement effect. Pin the count to 1 so the next regression
    // is caught.
    mockStore.lastSentApplication = {
      jobId: 'j1',
      jobTitle: 'Senior Backend Engineer',
      sentAt: Date.now(),
    };

    renderWithProviders(<ChatInterface candidateId="c1" />);

    await waitFor(() => {
      expect(
        screen.getAllByText(/has been sent to the recruiter/i)
      ).toHaveLength(1);
    });
  });

  it('does not announce anything when lastSentApplication is null', () => {
    renderWithProviders(<ChatInterface candidateId="c1" />);

    // Only the default welcome message should be present; no
    // "has been sent" copy.
    expect(screen.queryByText(/has been sent to the recruiter/i)).toBeNull();
    expect(mockStore.clearAnnouncedApplication).not.toHaveBeenCalled();
  });
});
