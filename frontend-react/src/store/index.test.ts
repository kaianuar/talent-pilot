import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from './index';

// Reset store between tests
beforeEach(() => {
  const { reset } = useAppStore.getState();
  reset();
  // Also clear localStorage mock
  localStorage.clear();
});

describe('useAppStore', () => {
  it('has correct initial state', () => {
    const state = useAppStore.getState();

    expect(state.candidateId).toBeNull();
    expect(state.activeTab).toBe('chat');
    expect(state.isDarkMode).toBe(false);
    expect(state.chatHistory).toEqual([]);
    expect(state.candidate).toBeNull();
    expect(state.jobs).toEqual([]);
    expect(state.selectedJobId).toBeNull();
    expect(state.selectedJobTitle).toBeNull();
    expect(state.lastSentApplication).toBeNull();
  });

  describe('setCandidateId', () => {
    it('updates candidateId', () => {
      useAppStore.getState().setCandidateId('c1');
      expect(useAppStore.getState().candidateId).toBe('c1');
    });

    it('can be set to null', () => {
      useAppStore.getState().setCandidateId('c1');
      useAppStore.getState().setCandidateId(null);
      expect(useAppStore.getState().candidateId).toBeNull();
    });
  });

  describe('setSelectedJob', () => {
    it('updates selectedJobId and selectedJobTitle', () => {
      useAppStore.getState().setSelectedJob('j1', 'Engineer');
      const state = useAppStore.getState();
      expect(state.selectedJobId).toBe('j1');
      expect(state.selectedJobTitle).toBe('Engineer');
    });

    it('defaults jobTitle to null', () => {
      useAppStore.getState().setSelectedJob('j1');
      expect(useAppStore.getState().selectedJobTitle).toBeNull();
    });

    it('clears selection with null', () => {
      useAppStore.getState().setSelectedJob('j1', 'Engineer');
      useAppStore.getState().setSelectedJob(null, null);
      const state = useAppStore.getState();
      expect(state.selectedJobId).toBeNull();
      expect(state.selectedJobTitle).toBeNull();
    });
  });

  describe('addMessage', () => {
    it('appends to chatHistory', () => {
      useAppStore.getState().addMessage('user', 'hello');
      useAppStore.getState().addMessage('assistant', 'hi');

      const history = useAppStore.getState().chatHistory;
      expect(history).toHaveLength(2);
      expect(history[0]).toMatchObject({ role: 'user', content: 'hello' });
      expect(history[1]).toMatchObject({ role: 'assistant', content: 'hi' });
    });

    it('includes a timestamp', () => {
      useAppStore.getState().addMessage('user', 'test');
      expect(useAppStore.getState().chatHistory[0].timestamp).toBeInstanceOf(Date);
    });
  });

  describe('persistence', () => {
    it('does not persist chatHistory', () => {
      useAppStore.getState().setCandidateId('c1');
      useAppStore.getState().addMessage('user', 'should not survive refresh');

      const raw = localStorage.getItem('talentpilot-storage');
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw!);
      expect(parsed.state).toBeDefined();
      expect(parsed.state.chatHistory).toBeUndefined();
      expect(parsed.state.candidateId).toBe('c1');
      expect(parsed.state.isDarkMode).toBe(false);
    });
  });

  describe('reset', () => {
    it('clears all state back to initial', () => {
      const store = useAppStore.getState();
      store.setCandidateId('c1');
      store.addMessage('user', 'hello');
      store.setSelectedJob('j1', 'Engineer');
      store.setActiveTab('matches');

      useAppStore.getState().reset();

      const state = useAppStore.getState();
      expect(state.candidateId).toBeNull();
      expect(state.chatHistory).toEqual([]);
      expect(state.selectedJobId).toBeNull();
      expect(state.selectedJobTitle).toBeNull();
      expect(state.activeTab).toBe('chat');
    });
  });

  describe('other setters', () => {
    it('setActiveTab updates tab', () => {
      useAppStore.getState().setActiveTab('profile');
      expect(useAppStore.getState().activeTab).toBe('profile');
    });

    it('toggleDarkMode flips isDarkMode', () => {
      expect(useAppStore.getState().isDarkMode).toBe(false);
      useAppStore.getState().toggleDarkMode();
      expect(useAppStore.getState().isDarkMode).toBe(true);
      useAppStore.getState().toggleDarkMode();
      expect(useAppStore.getState().isDarkMode).toBe(false);
    });

    it('setCandidate sets candidate data', () => {
      const candidate = { id: 'c1', name: 'Alice', years_experience: 3, skills: [], education: [], experience: [], certifications: [] };
      useAppStore.getState().setCandidate(candidate as any);
      expect(useAppStore.getState().candidate).toEqual(candidate);
    });

    it('clearChat empties chatHistory', () => {
      useAppStore.getState().addMessage('user', 'test');
      useAppStore.getState().clearChat();
      expect(useAppStore.getState().chatHistory).toEqual([]);
    });
  });

  describe('announceApplication', () => {
    it('sets lastSentApplication with jobId, jobTitle, and a sentAt timestamp', () => {
      const before = Date.now();
      useAppStore.getState().announceApplication('j1', 'Frontend Developer');
      const ann = useAppStore.getState().lastSentApplication;
      const after = Date.now();

      expect(ann).not.toBeNull();
      expect(ann).toMatchObject({ jobId: 'j1', jobTitle: 'Frontend Developer' });
      expect(ann!.sentAt).toBeGreaterThanOrEqual(before);
      expect(ann!.sentAt).toBeLessThanOrEqual(after);
    });

    it('clearAnnouncedApplication resets lastSentApplication to null', () => {
      useAppStore.getState().announceApplication('j1', 'Frontend Developer');
      expect(useAppStore.getState().lastSentApplication).not.toBeNull();

      useAppStore.getState().clearAnnouncedApplication();
      expect(useAppStore.getState().lastSentApplication).toBeNull();
    });

    it('is not persisted across refreshes (one-shot event)', () => {
      useAppStore.getState().announceApplication('j1', 'Frontend Developer');

      const raw = localStorage.getItem('talentpilot-storage');
      expect(raw).not.toBeNull();
      const parsed = JSON.parse(raw!);
      // lastSentApplication is intentionally excluded from the persist
      // partialize — it is a one-shot event, not session state. If it leaks
      // into localStorage, a refresh would re-announce the last send.
      expect(parsed.state.lastSentApplication).toBeUndefined();
    });
  });
});
