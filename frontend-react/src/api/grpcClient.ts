/**
 * gRPC-Web client for the TalentPilot ScreeningService.
 * Uses the gRPC-Web proxy registered at /grpc-web on the backend.
 */
import { GrpcWebFetchTransport } from '@protobuf-ts/grpcweb-transport';
import { ScreeningServiceClient } from '../generated/screening.client';
import type {
  StartScreeningResponse,
  GetNextQuestionResponse,
  SubmitAnswerResponse,
  GetScreeningResultResponse,
  ScreeningProgressUpdate,
} from '../generated/screening';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim() || "";

// Create gRPC-Web transport pointing to the backend proxy
const transport = new GrpcWebFetchTransport({
  baseUrl: `${API_BASE}/grpc-web`,
  format: 'binary', // binary is more efficient than text
});

// Create the typed client
const client = new ScreeningServiceClient(transport);

/** Start a new screening session for a candidate applying to a job */
export async function startScreening(
  candidateId: string,
  jobId: string,
  matchTier: string,
  questionCount = 3,
): Promise<StartScreeningResponse> {
  const { response } = await client.startScreening({
    candidateId,
    jobId,
    matchTier,
    questionCount,
  });
  return response;
}

/** Get the next question in an ongoing screening session */
export async function getNextQuestion(
  screeningId: string,
  candidateId: string,
): Promise<GetNextQuestionResponse> {
  const { response } = await client.getNextQuestion({
    screeningId,
    candidateId,
  });
  return response;
}

/** Submit an answer and get assessment + next question */
export async function submitAnswer(
  screeningId: string,
  candidateId: string,
  questionId: string,
  answerText: string,
  responseTimeSeconds = 0,
): Promise<SubmitAnswerResponse> {
  const { response } = await client.submitAnswer({
    screeningId,
    candidateId,
    questionId,
    answerText,
    responseTimeSeconds,
  });
  return response;
}

/** Get the final screening result with summary and email draft */
export async function getScreeningResult(
  screeningId: string,
  candidateId: string,
): Promise<GetScreeningResultResponse> {
  const { response } = await client.getScreeningResult({
    screeningId,
    candidateId,
  });
  return response;
}

/** Stream real-time screening progress updates */
export function streamScreeningProgress(
  screeningId: string,
  candidateId: string,
  onUpdate: (update: ScreeningProgressUpdate) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
): AbortController {
  const abort = new AbortController();
  const call = client.streamScreeningProgress(
    { screeningId, candidateId },
    { abort: abort.signal },
  );

  call.responses.onMessage((msg: ScreeningProgressUpdate) => onUpdate(msg));
  call.responses.onError((err: Error) => onError?.(err));
  call.responses.onComplete(() => onComplete?.());

  // Don't await — return controller for cancellation
  call.then(() => {}).catch(() => {});

  return abort;
}
