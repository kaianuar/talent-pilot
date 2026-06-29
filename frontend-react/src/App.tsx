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
import { useStatus } from './api/hooks';

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

// Main App Content
const AppContent: React.FC = () => {
  const [candidateId, setCandidateId] = useState<string | undefined>();

  const handleCandidateCreated = (id: string) => {
    setCandidateId(id);
  };

  return (
    <Box sx={{ flexGrow: 1, height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* App Bar */}
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <SmartToyIcon sx={{ mr: 2 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            TalentPilot
          </Typography>
          <Chip
            label={candidateId ? 'Profile Active' : 'No Profile'}
            color={candidateId ? 'success' : 'default'}
            size="small"
            sx={{ mr: 1 }}
          />
        </Toolbar>
      </AppBar>

      {/* Status Check */}
      <Container maxWidth="xl" sx={{ mt: 2 }}>
        <StatusCheck />
      </Container>

      {/* Main Content */}
      <Container maxWidth="xl" sx={{ flex: 1, py: 2, display: 'flex', flexDirection: 'column' }}>
      <Grid container spacing={2} sx={{ flex: 1 }}>
          {/* Chat Area */}
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
                <ChatInterface
                  candidateId={candidateId}
                  onCandidateCreated={handleCandidateCreated}
                />
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
