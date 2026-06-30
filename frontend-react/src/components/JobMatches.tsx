import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  LinearProgress,
  Alert,
  Skeleton,
  Tooltip,
} from '@mui/material';
import WorkIcon from '@mui/icons-material/Work';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { useMatches, useMatchJobs } from '../api/hooks';
import { useAppStore } from '../store';
import type { JobMatch } from '../api/client';

interface JobMatchesProps {
  candidateId?: string;
}

const getMatchColor = (tier: JobMatch['tier']) => {
  switch (tier) {
    case 'STRONG_MATCH':
      return 'success';
    case 'PARTIAL_MATCH':
      return 'warning';
    case 'POOR_MATCH':
      return 'error';
    default:
      return 'default';
  }
};

const getMatchLabel = (tier: JobMatch['tier']) => {
  switch (tier) {
    case 'STRONG_MATCH':
      return 'Strong Match';
    case 'PARTIAL_MATCH':
      return 'Partial Match';
    case 'POOR_MATCH':
      return 'Poor Match';
    default:
      return 'No Match';
  }
};

const JobMatches: React.FC<JobMatchesProps> = ({ candidateId }) => {
  const {
    data: matches,
    isLoading,
    isError,
  } = useMatches(candidateId || '', {
    enabled: !!candidateId,
  });

  const matchJobsMutation = useMatchJobs();

  const handleRefresh = () => {
    if (candidateId) {
      matchJobsMutation.mutate(candidateId);
    }
  };

  if (!candidateId) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Job Matches
        </Typography>
        <Alert severity="info" icon={<WorkIcon />}>
          Upload your CV to see job matches!
        </Alert>
      </Box>
    );
  }

  if (isLoading) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Job Matches
        </Typography>
        <Skeleton variant="rectangular" height={100} sx={{ mb: 1 }} />
        <Skeleton variant="rectangular" height={100} sx={{ mb: 1 }} />
        <Skeleton variant="rectangular" height={100} />
      </Box>
    );
  }

  if (isError) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Job Matches
        </Typography>
        <Alert severity="error" icon={<ErrorIcon />}>
          Failed to load job matches. Please try again.
        </Alert>
        <Button
          variant="outlined"
          size="small"
          onClick={handleRefresh}
          sx={{ mt: 1 }}
        >
          Retry
        </Button>
      </Box>
    );
  }

  if (!matches || matches.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Job Matches
        </Typography>
        <Alert severity="info">
          No job matches found at the moment. Check back later for new opportunities!
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">
          Job Matches
        </Typography>
        <Chip
          icon={<TrendingUpIcon />}
          label={`${matches.length} matches`}
          color="primary"
          size="small"
        />
      </Box>

      {matches.map((match) => (
        <Card key={match.job_id} sx={{ mb: 2, '&:hover': { boxShadow: 4 }, cursor: 'pointer' }} onClick={() => useAppStore.getState().setSelectedJob(match.job_id, match.job_title)}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
              <Typography variant="h6" component="div">
                {match.job_title}
              </Typography>
              <Tooltip title={match.reasoning_explanation}>
                <Chip
                  label={getMatchLabel(match.tier)}
                  color={getMatchColor(match.tier) as 'success' | 'warning' | 'error' | 'default'}
                  size="small"
                />
              </Tooltip>
            </Box>

            <Box sx={{ mb: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100 }}>
                  Match Score:
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={match.match_score * 100}
                  sx={{
                    flex: 1,
                    mr: 1,
                    height: 8,
                    borderRadius: 4,
                    bgcolor: 'grey.200',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: match.tier === 'STRONG_MATCH' ? 'success.main' :
                               match.tier === 'PARTIAL_MATCH' ? 'warning.main' : 'error.main',
                    },
                  }}
                />
                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                  {Math.round(match.match_score * 100)}%
                </Typography>
              </Box>
            </Box>

            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip
                icon={<CheckCircleIcon />}
                label={`${Math.round(match.required_match_ratio * 100)}% skills match`}
                size="small"
                variant="outlined"
              />
              {match.adjacent_bonus > 0 && (
                <Chip
                  label={`+${Math.round(match.adjacent_bonus * 100)}% adjacent skills`}
                  size="small"
                  variant="outlined"
                  color="info"
                />
              )}
            </Box>
            <Button
              variant="contained"
              size="small"
              color="primary"
              fullWidth
              sx={{ mt: 1.5 }}
              onClick={(e) => {
                e.stopPropagation(); // prevent duplicate card onClick
                useAppStore.getState().setSelectedJob(match.job_id, match.job_title);
              }}
            >
              Start Screening
            </Button>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
};

export default JobMatches;
