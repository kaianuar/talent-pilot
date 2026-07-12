import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Candidate, Job, JobMatch } from '../api/client';

interface AppState {
  // Auth/User State
  candidateId: string | null;
  setCandidateId: (id: string | null) => void;

  // UI State
  activeTab: 'chat' | 'matches' | 'profile';
  setActiveTab: (tab: 'chat' | 'matches' | 'profile') => void;
  isDarkMode: boolean;
  toggleDarkMode: () => void;

  // Chat State
  chatHistory: Array<{ role: string; content: string; timestamp: Date }>;
  addMessage: (role: string, content: string) => void;
  clearChat: () => void;

  // Data Cache
  candidate: Candidate | null;
  setCandidate: (candidate: Candidate | null) => void;
  jobs: Job[];
  setJobs: (jobs: Job[]) => void;
  matches: JobMatch[];
  setMatches: (matches: JobMatch[]) => void;
  selectedJobId: string | null;
  selectedJobTitle: string | null;
  setSelectedJob: (jobId: string | null, jobTitle?: string | null) => void;
  // Actions
  reset: () => void;
}

const initialState = {
  candidateId: null,
  activeTab: 'chat' as const,
  isDarkMode: false,
  chatHistory: [],
  candidate: null,
  jobs: [],
  matches: [],
  selectedJobId: null,
  selectedJobTitle: null,
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      ...initialState,

      setCandidateId: (id) => set({ candidateId: id }),

      setActiveTab: (tab) => set({ activeTab: tab }),

      toggleDarkMode: () => {
        const newMode = !get().isDarkMode;
        set({ isDarkMode: newMode });
        // You can add theme switching logic here
      },

      addMessage: (role, content) => {
        set((state) => ({
          chatHistory: [
            ...state.chatHistory,
            { role, content, timestamp: new Date() },
          ],
        }));
      },

      clearChat: () => set({ chatHistory: [] }),

      setCandidate: (candidate) => set({ candidate }),

      setJobs: (jobs) => set({ jobs }),

      setMatches: (matches) => set({ matches }),

      setSelectedJob: (jobId, jobTitle = null) => set({ selectedJobId: jobId, selectedJobTitle: jobTitle }),

      reset: () => {
        set(initialState);
        // Clear persisted storage
        localStorage.removeItem('talentpilot-storage');
      },
    }),
    {
      name: 'talentpilot-storage',
      partialize: (state) => ({
        candidateId: state.candidateId,
        isDarkMode: state.isDarkMode,
      }),
    }
  )
);

export default useAppStore;
