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
import { submitApplication } from './api/client';

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

  const handleSendApplication = async () => {
    if (!candidateId || !selectedJobId) return;
    const match = matches.find((m: JobMatch) => m.job_id === selectedJobId);
    try {
      await submitApplication(candidateId, selectedJobId, match?.match_score ?? 0, match?.tier ?? 'CONFIRMED');
    } catch { /* silent */ }
    clearSelectedJob();
  };

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      {/* Header */}
      <Box sx={{
        bgcolor: 'white',
        py: 1.5,
        px: 3,
        borderBottom: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <SmartToyIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary', letterSpacing: '-0.01em' }}>
            TalentPilot
          </Typography>
        </Box>
        {candidateId && (
          <Chip label="Profile Active" color="primary" size="small" sx={{ bgcolor: 'primary.light', color: 'white' }} />
        )}
      </Box>

      {/* Main Content */}
      <Box sx={{ flex: 1, p: 3, display: 'flex', gap: 3, overflow: 'hidden' }}>
        {/* Chat Area */}
        <Box sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 2,
          bgcolor: 'background.paper',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
          overflow: 'hidden',
        }}>
          <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
            {selectedJobId && candidateId ? (
              <ScreeningPanel
                candidateId={candidateId}
                jobId={selectedJobId}
                jobTitle={selectedJobTitle || 'this position'}
                matchTier={matches.find((m: JobMatch) => m.job_id === selectedJobId)?.tier || 'PARTIAL_MATCH'}
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
          <Box sx={{ flex: 1, borderRadius: 2, bgcolor: 'background.paper', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'auto' }}>
            <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
              <JobMatches candidateId={candidateId} />
            </React.Suspense>
          </Box>
          <Box sx={{ flex: 1, borderRadius: 2, bgcolor: 'background.paper', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'auto' }}>
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
