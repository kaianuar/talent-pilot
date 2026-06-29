import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import {
  uploadResume,
  getCandidate,
  listJobs,
  getJob,
  matchJobs,
  chat,
  getAuditLog,
  getStatus,
  type Candidate,
  type Job,
  type JobMatch,
  type UploadProgress,
  type AuditLogEntry,
} from './client';

// Query keys
export const queryKeys = {
  status: ['status'] as const,
  candidate: (id: string) => ['candidate', id] as const,
  jobs: ['jobs'] as const,
  job: (id: string) => ['job', id] as const,
  matches: (candidateId: string) => ['matches', candidateId] as const,
  auditLog: (limit: number, candidateId?: string) =>
    ['auditLog', limit, candidateId] as const,
  chat: (candidateId?: string) => ['chat', candidateId] as const,
};

type QueryOpts<T> = Omit<UseQueryOptions<T, Error>, 'queryKey' | 'queryFn'>;

// Status query
export const useStatus = (options?: QueryOpts<{
  api_key_configured: boolean;
  smtp_configured: boolean;
  version: string;
}>) => {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: getStatus,
    retry: 2,
    staleTime: 30000,
    ...options,
  });
};

// Candidate queries
export const useCandidate = (id: string, options?: QueryOpts<Candidate>) => {
  return useQuery({
    queryKey: queryKeys.candidate(id),
    queryFn: () => getCandidate(id),
    enabled: !!id,
    retry: 2,
    ...options,
  });
};

// Upload mutation
export const useUploadResume = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      onProgress,
    }: {
      file: File;
      onProgress?: (progress: UploadProgress) => void;
    }) => {
      return await uploadResume(file, onProgress);
    },
    onSuccess: (data) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: queryKeys.candidate(data.candidate_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.matches(data.candidate_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.status });
    },
  });
};

// Jobs queries
export const useJobs = (options?: QueryOpts<Job[]>) => {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: listJobs,
    retry: 2,
    staleTime: 60000,
    ...options,
  });
};

export const useJob = (id: string, options?: QueryOpts<Job>) => {
  return useQuery({
    queryKey: queryKeys.job(id),
    queryFn: () => getJob(id),
    enabled: !!id,
    retry: 2,
    ...options,
  });
};

// Match jobs mutation
export const useMatchJobs = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (candidateId: string) => {
      const result = await matchJobs(candidateId);
      return result.matches;
    },
    onSuccess: (matches, candidateId) => {
      queryClient.setQueryData(queryKeys.matches(candidateId), matches);
    },
  });
};

// Matches query
export const useMatches = (candidateId: string, options?: QueryOpts<JobMatch[]>) => {
  return useQuery({
    queryKey: queryKeys.matches(candidateId),
    queryFn: async () => {
      const result = await matchJobs(candidateId);
      return result.matches;
    },
    retry: 2,
    ...options,
  });
};

// Chat mutation
export const useChat = () => {
  return useMutation({
    mutationFn: async ({
      messages,
      candidateId,
      sendConfirmed,
    }: {
      messages: Array<{ role: string; content: string }>;
      candidateId?: string;
      sendConfirmed?: boolean;
    }) => {
      return await chat(messages, candidateId, sendConfirmed);
    },
  });
};

// Audit log query
export const useAuditLog = (
  limit = 20,
  candidateId?: string,
  options?: QueryOpts<AuditLogEntry[]>
) => {
  return useQuery({
    queryKey: queryKeys.auditLog(limit, candidateId),
    queryFn: () => getAuditLog(limit, candidateId),
    retry: 2,
    staleTime: 10000,
    ...options,
  });
};

export default {
  useStatus,
  useCandidate,
  useUploadResume,
  useJobs,
  useJob,
  useMatchJobs,
  useMatches,
  useChat,
  useAuditLog,
};
