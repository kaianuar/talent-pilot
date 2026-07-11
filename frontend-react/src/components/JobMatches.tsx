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
  Badge,
} from '@mui/material';
import WorkIcon from '@mui/icons-material/Work';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
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

const MIN_MATCH_SCORE = 0.50;

const JobMatches: React.FC<JobMatchesProps> = ({ candidateId }) => {
  const {
    data: rawMatches,
    isLoading,
    isError,
  } = useMatches(candidateId || '', {
    enabled: !!candidateId,
  });

  // Filter out weak matches and sort by score descending
  const matches = React.useMemo(() => {
    if (!rawMatches) return undefined;
    return rawMatches
      .filter((m) => m.match_score >= MIN_MATCH_SCORE)
      .sort((a, b) => b.match_score - a.match_score);
  }, [rawMatches]);

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
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary' }}>
            Job Matches
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Roles ranked by fit for this candidate
          </Typography>
        </Box>
        <Badge
          badgeContent={matches.length}
          color="primary"
          sx={{ '& .MuiBadge-badge': { fontWeight: 700, fontSize: '0.75rem', minWidth: 24, height: 24 } }}
        >
          <Chip
            icon={<TrendingUpIcon />}
            label="matches"
            color="primary"
            variant="outlined"
            size="small"
          />
        </Badge>
      </Box>

      {matches.map((match) => (
        <Card
          key={match.job_id}
          elevation={1}
          sx={{
            mb: 2.5,
            border: '1px solid',
            borderColor: 'divider',
            cursor: 'pointer',
            '&:hover': {
              boxShadow: '0 8px 24px rgba(107,77,87,0.12)',
              borderColor: 'primary.light',
            },
          }}
          onClick={() => useAppStore.getState().setSelectedJob(match.job_id, match.job_title)}
        >
          <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'text.primary' }}>
                {match.job_title}
              </Typography>
              <Tooltip title={match.reasoning_explanation} arrow>
                <Chip
                  label={getMatchLabel(match.tier)}
                  color={getMatchColor(match.tier) as 'success' | 'warning' | 'error' | 'default'}
                  size="small"
                  sx={{
                    fontWeight: 600,
                    fontSize: '0.7rem',
                    height: 26,
                    opacity: 0.9,
                  }}
                />
              </Tooltip>
            </Box>

            <Box sx={{ mb: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.75 }}>
                <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100, fontWeight: 500 }}>
                  Match Score:
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={match.match_score * 100}
                  sx={{
                    flex: 1,
                    mr: 1.5,
                    height: 10,
                    borderRadius: 5,
                    bgcolor: 'grey.200',
                    '& .MuiLinearProgress-bar': {
                      borderRadius: 5,
                      bgcolor: match.tier === 'STRONG_MATCH' ? 'success.main' :
                               match.tier === 'PARTIAL_MATCH' ? 'warning.main' : 'error.main',
                    },
                  }}
                />
                <Typography variant="body2" sx={{ fontWeight: 700, minWidth: 36, textAlign: 'right' }}>
                  {Math.round(match.match_score * 100)}%
                </Typography>
              </Box>
            </Box>

            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.5 }}>
              <Chip
                icon={<CheckCircleIcon />}
                label={`${Math.round(match.required_match_ratio * 100)}% skills match`}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 500 }}
              />
              {match.adjacent_bonus > 0 && (
                <Chip
                  label={`+${Math.round(match.adjacent_bonus * 100)}% adjacent skills`}
                  size="small"
                  variant="outlined"
                  color="info"
                  sx={{ fontWeight: 500 }}
                />
              )}
            </Box>
            <Button
              variant="outlined"
              size="medium"
              color="primary"
              fullWidth
              startIcon={<PlayArrowRoundedIcon />}
              sx={{
                mt: 0.5,
                borderColor: 'primary.main',
                color: 'primary.main',
                fontWeight: 600,
                '&:hover': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  borderColor: 'primary.main',
                },
              }}
              onClick={(e) => {
                e.stopPropagation();
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
