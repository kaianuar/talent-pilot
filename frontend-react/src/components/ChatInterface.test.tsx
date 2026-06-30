import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import ChatInterface from './ChatInterface';

// Mock the API hooks module
vi.mock('../api/hooks', () => ({
  useChat: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
  }),
  useUploadResume: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
  }),
  useSubmitApplication: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
  }),
}));

describe('ChatInterface', () => {
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
});
