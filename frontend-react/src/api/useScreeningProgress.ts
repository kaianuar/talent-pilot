/**
 * WebSocket hook for real-time screening progress updates.
 * Connects to /ws/screening/{screeningId} on the backend.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const WS_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:9000').replace(/^http/, 'ws');

export interface ScreeningProgress {
  screeningId: string;
  status: string;
  currentQuestionNumber: number;
  totalQuestions: number;
  progressPercentage: number;
  currentQuestionText?: string;
  latestAssessment?: {
    quality: string;
    confidence: number;
    decision: string;
    reasoning: string;
  };
  timestamp: string;
}

interface UseScreeningProgressOptions {
  screeningId: string | null;
  enabled?: boolean;
}

export function useScreeningProgress({ screeningId, enabled = true }: UseScreeningProgressOptions) {
  const [progress, setProgress] = useState<ScreeningProgress | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const connect = useCallback(() => {
    if (!screeningId || !enabled) return;

    const url = `${WS_BASE}/ws/screening/${screeningId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.message_type === 'heartbeat') return;
        setProgress({
          screeningId: data.screening_id || screeningId,
          status: data.status || data.message_type || 'unknown',
          currentQuestionNumber: data.current_question_number ?? progress?.currentQuestionNumber ?? 0,
          totalQuestions: data.total_questions ?? progress?.totalQuestions ?? 3,
          progressPercentage: data.progress_percentage ?? 0,
          currentQuestionText: data.current_question_text,
          latestAssessment: data.latest_assessment || data.assessment,
          timestamp: data.timestamp || new Date().toISOString(),
        });
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
    };

    ws.onclose = () => {
      setConnected(false);
      // Auto-reconnect after 3 seconds if still enabled
      if (enabled && screeningId) {
        reconnectRef.current = setTimeout(connect, 3000);
      }
    };
  }, [screeningId, enabled]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { progress, connected, error };
}
