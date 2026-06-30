import React, { useState } from 'react';
import {
  Box,
  CircularProgress,
  CssBaseline,
  ThemeProvider,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Grid,
  Paper,
  Alert,
  Chip,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

import theme from './theme';
const ChatInterface = React.lazy(() => import('./components/ChatInterface'));
const JobMatches = React.lazy(() => import('./components/JobMatches'));
const CandidateProfile = React.lazy(() => import('./components/CandidateProfile'));
const ScreeningPanel = React.lazy(() => import('./components/ScreeningPanel'));
import { useAppStore } from './store';
import type { JobMatch } from './api/client';
import { useStatus } from './api/hooks';
import { submitApplication } from './api/client';
// Create Query Client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

// Status Check Component
const StatusCheck: React.FC = () => {
  const { data: status, isLoading, isError } = useStatus();

  if (isLoading) return null;

  if (isError) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        Cannot connect to the backend API. Please ensure the backend server is running.
      </Alert>
    );
  }

  if (!status?.api_key_configured) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        API key is not configured. Some features may not work properly.
      </Alert>
    );
  }

  return null;
};
const AppContent: React.FC = () => {
  const [candidateId, setCandidateId] = useState<string | undefined>();
  const selectedJobId = useAppStore((s) => s.selectedJobId);
  const selectedJobTitle = useAppStore((s) => s.selectedJobTitle);
  const matches = useAppStore((s) => s.matches);
  const clearSelectedJob = () => useAppStore.getState().setSelectedJob(null, null);

  const handleSendApplication = async () => {
    if (!candidateId || !selectedJobId) return;
    const match = matches.find((m: JobMatch) => m.job_id === selectedJobId);
    try {
      await submitApplication(candidateId, selectedJobId, match?.match_score ?? 0, match?.tier ?? 'CONFIRMED');
    } catch {
      // Silently handle — ScreeningPanel shows its own success UI
    }
    clearSelectedJob();
  };

  const handleCandidateCreated = (id: string) => {
    setCandidateId(id);
  };

  return (
    <Box sx={{ flexGrow: 1, height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* App Bar */}
      <AppBar position="static" elevation={0} sx={{ backdropFilter: 'blur(8px)' }}>
        <Toolbar sx={{ minHeight: { xs: 56, sm: 64 } }}>
          <SmartToyIcon sx={{ mr: 1.5, fontSize: 28 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 700, letterSpacing: '-0.01em' }}>
            TalentPilot
          </Typography>
          {candidateId && (
            <Chip
              label="Profile Active"
              color="success"
              size="small"
              variant="outlined"
              sx={{ borderColor: 'rgba(255,255,255,0.4)', color: '#fff' }}
            />
          )}
        </Toolbar>
      </AppBar>

      {/* Status Check */}
      <Container maxWidth="xl" sx={{ mt: 2 }}>
        <StatusCheck />
      </Container>

      {/* Main Content */}
      <Container maxWidth="xl" sx={{ flex: 1, py: 2, display: 'flex', flexDirection: 'column' }}>
      <Grid container spacing={2} sx={{ flex: 1 }}>
          {/* Chat / Screening Area */}
          <Grid size={{ xs: 12, md: 8 }} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Paper
              elevation={1}
              sx={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
                {selectedJobId && candidateId ? (
                  <ScreeningPanel
                    candidateId={candidateId}
                    jobId={selectedJobId}
                    jobTitle={selectedJobTitle || 'this position'}
                    matchTier={matches.find((m: JobMatch) => m.job_id === selectedJobId)?.tier || 'PARTIAL_MATCH'}
                    onComplete={() => handleSendApplication()}
                    onCancel={() => clearSelectedJob()}
                  />
                ) : (
                  <ChatInterface
                    candidateId={candidateId}
                    onCandidateCreated={handleCandidateCreated}
                  />
                )}
              </React.Suspense>
            </Paper>
          </Grid>


          {/* Side Panel */}
          <Grid size={{ xs: 12, md: 4 }} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Job Matches */}
            <Paper elevation={1} sx={{ flex: 1, mb: 2, overflow: 'auto' }}>
              <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
                <JobMatches candidateId={candidateId} />
              </React.Suspense>
            </Paper>

            {/* Candidate Profile */}
            <Paper elevation={1} sx={{ flex: 1, overflow: 'auto' }}>
              <React.Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>}>
                <CandidateProfile candidateId={candidateId} />
              </React.Suspense>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

// Main App
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
