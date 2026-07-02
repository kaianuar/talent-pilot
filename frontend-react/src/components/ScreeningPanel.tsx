/**
 * ScreeningPanel — gRPC-powered multi-turn screening interview.
 * Starts a screening session, presents questions one at a time,
 * submits answers, shows assessments, and displays the email draft.
 */
import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  LinearProgress,
  Chip,
  CircularProgress,
  Alert,
  Divider,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import {
  startScreening,
  submitAnswer,
  getScreeningResult,
} from '../api/grpcClient';
import { useScreeningProgress } from '../api/useScreeningProgress';
import type {
  StartScreeningResponse,
  SubmitAnswerResponse,
  GetScreeningResultResponse,
} from '../generated/screening';

interface ScreeningPanelProps {
  candidateId: string;
  jobId: string;
  jobTitle: string;
  matchTier: string;
  onComplete?: (result: GetScreeningResultResponse) => void;
  onCancel?: () => void;
}

type ScreenState =
  | { phase: 'idle' }
  | { phase: 'starting' }
  | { phase: 'error'; message: string }
  | { phase: 'question'; screeningId: string; questionId: string; text: string; questionNumber: number; totalQuestions: number }
  | { phase: 'submitting'; screeningId: string; questionId: string; text: string; questionNumber: number; totalQuestions: number }
  | { phase: 'assessing'; screeningId: string; message: string }
  | { phase: 'complete'; screeningId: string; result: GetScreeningResultResponse };

const ScreeningPanel: React.FC<ScreeningPanelProps> = ({
  candidateId,
  jobId,
  jobTitle,
  matchTier,
  onComplete,
  onCancel,
}) => {
  const [state, setState] = useState<ScreenState>({ phase: 'idle' });
  const [answer, setAnswer] = useState('');
  const [questionNumber, setQuestionNumber] = useState(0);

  const screeningId = state.phase !== 'idle' && state.phase !== 'starting' && state.phase !== 'error'
    ? state.screeningId
    : null;

  const { progress } = useScreeningProgress({
    screeningId,
    enabled: screeningId !== null,
  });

  // Start screening on mount
  useEffect(() => {
    const init = async () => {
      setState({ phase: 'starting' });
      try {
        const result: StartScreeningResponse = await startScreening(
          candidateId,
          jobId,
          matchTier,
          3,
        );
        if (!result.success) {
          setState({ phase: 'error', message: result.errorMessage || 'Failed to start screening' });
          return;
        }
        if (result.firstQuestion) {
          setQuestionNumber(1);
          setState({
            phase: 'question',
            screeningId: result.screeningId,
            questionId: result.firstQuestion.id,
            text: result.firstQuestion.text,
            questionNumber: 1,
            totalQuestions: 3,
          });
        }
      } catch (err) {
        setState({ phase: 'error', message: err instanceof Error ? err.message : 'Connection error' });
      }
    };
    init();
  }, [candidateId, jobId, matchTier]);

  const handleSubmitAnswer = useCallback(async () => {
    if (state.phase !== 'question' || !answer.trim()) return;

    const { screeningId, questionId, text, questionNumber: qNum, totalQuestions } = state;
    setState({ phase: 'submitting', screeningId, questionId, text, questionNumber: qNum, totalQuestions });

    try {
      const result: SubmitAnswerResponse = await submitAnswer(
        screeningId,
        candidateId,
        questionId,
        answer.trim(),
      );
      setAnswer('');

      if (result.isComplete && result.emailDraft) {
        // Screening complete — fetch final result
        const finalResult = await getScreeningResult(screeningId, candidateId);
        setState({ phase: 'complete', screeningId, result: finalResult });
        onComplete?.(finalResult);
      } else if (result.nextQuestion) {
        // Don't increment for probes (same question, different wording)
        const isProbe = result.assessment?.decision === 'PROBE_FOR_CLARITY';
        const nextNum = isProbe ? qNum : qNum + 1;
        setQuestionNumber(nextNum);
        setState({
          phase: 'question',
          screeningId,
          questionId: result.nextQuestion.id,
          text: result.nextQuestion.text,
          questionNumber: nextNum,
          totalQuestions,
        });
      } else {
        setState({
          phase: 'assessing',
          screeningId,
          message: result.assessment?.reasoning || 'Assessing your answer...',
        });
      }
    } catch (err) {
      setState({ phase: 'error', message: err instanceof Error ? err.message : 'Failed to submit answer' });
    }
  }, [state, answer, candidateId, onComplete]);

  // --- Render by phase ---

  if (state.phase === 'idle' || state.phase === 'starting') {
    return (
      <Paper elevation={1} sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={32} sx={{ mb: 2 }} />
        <Typography variant="body1">Starting screening for <strong>{jobTitle}</strong>...</Typography>
      </Paper>
    );
  }

  if (state.phase === 'error') {
    return (
      <Paper elevation={1} sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>{state.message}</Alert>
        <Button variant="outlined" onClick={onCancel}>Go Back</Button>
      </Paper>
    );
  }

  if (state.phase === 'complete') {
    const { result } = state;
    const draft = result.emailDraft;
    const summary = result.summary;
    return (
      <Paper elevation={1} sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <CheckCircleIcon color="success" />
          <Typography variant="h6">Screening Complete</Typography>
        </Box>

        {summary && (
          <Box sx={{ mb: 2 }}>
            <Chip
              label={`${summary.totalQuestionsAsked} questions answered`}
              size="small"
              sx={{ mr: 1 }}
            />
            <Chip
              label={`Status: ${summary.status}`}
              size="small"
              color={summary.sufficientEvidence ? 'success' : 'warning'}
            />
            {summary.finalAssessment && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                {summary.finalAssessment}
              </Typography>
            )}
          </Box>
        )}

        {draft && (
          <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
            <Typography variant="subtitle2" gutterBottom>Email Draft</Typography>
            <Typography variant="caption" color="text.secondary">To: {draft.to}</Typography>
            <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 'medium' }}>{draft.subject}</Typography>
            <Divider sx={{ my: 1 }} />
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{draft.body}</Typography>
          </Paper>
        )}

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="contained" color="success" onClick={() => onComplete?.(result)}>
            Send to Recruiter
          </Button>
          <Button variant="outlined" onClick={onCancel}>Close</Button>
        </Box>
      </Paper>
    );
  }

  // Question / submitting / assessing phases
  const isSubmitting = state.phase === 'submitting';
  const currentNum = 'questionNumber' in state ? state.questionNumber : questionNumber;
  const totalQ = 'totalQuestions' in state ? state.totalQuestions : 3;
  const progPct = progress?.progressPercentage ?? (currentNum / totalQ) * 100;

  return (
    <Paper elevation={1} sx={{ p: 3 }}>
      {/* Progress bar */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="body2" color="text.secondary">
            Question {currentNum} of {totalQ}
          </Typography>
          <Chip
            icon={<TrendingUpIcon />}
            label={`${Math.round(progPct)}%`}
            size="small"
            color="primary"
          />
        </Box>
        <LinearProgress
          variant="determinate"
          value={progPct}
          sx={{ height: 6, borderRadius: 3 }}
        />
      </Box>

      {/* Question */}
      {'text' in state && (
        <Typography variant="body1" sx={{ mb: 2, fontWeight: 500 }}>
          {state.text}
        </Typography>
      )}

      {/* Assessment feedback */}
      {state.phase === 'submitting' && 'text' in state && state.text && (
        <Alert severity="info" icon={<CircularProgress size={20} />} sx={{ mb: 2 }}>
          Assessing your answer...
        </Alert>
      )}

      {state.phase === 'assessing' && (
        <Alert severity="info" sx={{ mb: 2 }}>{state.message}</Alert>
      )}

      {/* Answer input */}
      {state.phase === 'question' && (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            multiline
            minRows={3}
            maxRows={6}
            placeholder="Type your answer..."
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.metaKey) {
                e.preventDefault();
                handleSubmitAnswer();
              }
            }}
            disabled={isSubmitting}
          />
          <Button
            variant="contained"
            onClick={handleSubmitAnswer}
            disabled={!answer.trim() || isSubmitting}
            sx={{ alignSelf: 'flex-end' }}
          >
            {isSubmitting ? <CircularProgress size={20} /> : <SendIcon />}
          </Button>
        </Box>
      )}

      {onCancel && (
        <Button variant="text" size="small" onClick={onCancel} sx={{ mt: 1 }}>
          Cancel Screening
        </Button>
      )}
    </Paper>
  );
};

export default ScreeningPanel;
