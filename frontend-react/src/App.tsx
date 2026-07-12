import React, { useState } from 'react';
import {
  Box,
  CircularProgress,
  CssBaseline,
  ThemeProvider,
  Typography,
  Chip,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

import theme from './theme';
import { useAppStore } from './store';
import type { JobMatch } from './api/client';

const ChatInterface = React.lazy(() => import('./components/ChatInterface'));
const JobMatches = React.lazy(() => import('./components/JobMatches'));
const CandidateProfile = React.lazy(() => import('./components/CandidateProfile'));
const ScreeningPanel = React.lazy(() => import('./components/ScreeningPanel'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

const AppContent: React.FC = () => {
  const [candidateId, setCandidateId] = useState<string | undefined>();
  const selectedJobId = useAppStore((s) => s.selectedJobId);
  const selectedJobTitle = useAppStore((s) => s.selectedJobTitle);
  const matches = useAppStore((s) => s.matches);
  const clearSelectedJob = () => useAppStore.getState().setSelectedJob(null, null);

  const handleCandidateCreated = (id: string) => setCandidateId(id);

  // ScreeningPanel now handles the application submission itself, including
  // progress and error UI. The parent only needs to clear the selected job
  // after a successful send, which the panel triggers via onComplete.
  const handleSendApplication = () => {
    clearSelectedJob();
  };
  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      {/* Header */}
      <Box sx={{
        bgcolor: 'background.default',
        py: 1.5,
        px: 3,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <SmartToyIcon sx={{ color: 'text.primary', fontSize: 28 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary', letterSpacing: '-0.01em' }}>
            TalentPilot
          </Typography>
        </Box>
        {candidateId && (
          <Chip label="Profile Active" size="small" sx={{ bgcolor: 'primary.main', color: 'primary.contrastText' }} />
        )}
      </Box>

      {/* Main Content */}
      <Box sx={{ flex: 1, p: 2, display: 'flex', gap: 2, overflow: 'hidden' }}>
        {/* Chat Area */}
        <Box sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 3,
          bgcolor: 'background.paper',
          overflow: 'hidden',
        }}>
          <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
            {selectedJobId && candidateId ? (
              <ScreeningPanel
                candidateId={candidateId}
                jobId={selectedJobId}
                jobTitle={selectedJobTitle || 'this position'}
                matchTier={matches.find((m: JobMatch) => m.job_id === selectedJobId)?.tier || 'PARTIAL_MATCH'}
                matchScore={matches.find((m: JobMatch) => m.job_id === selectedJobId)?.match_score ?? 0}
                onComplete={handleSendApplication}
                onCancel={clearSelectedJob}
              />
            ) : (
              <ChatInterface candidateId={candidateId} onCandidateCreated={handleCandidateCreated} />
            )}
          </React.Suspense>
        </Box>

        {/* Sidebar */}
        <Box sx={{ width: 380, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ flex: 1, bgcolor: 'background.paper', overflow: 'auto' }}>
            <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
              <JobMatches candidateId={candidateId} />
            </React.Suspense>
          </Box>
          <Box sx={{ flex: 1, bgcolor: 'background.paper', overflow: 'auto' }}>
            <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
              <CandidateProfile candidateId={candidateId} />
            </React.Suspense>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AppContent />
        <ReactQueryDevtools initialIsOpen={false} />
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
