import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
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
  Candidate,
  Job,
  JobMatch,
  UploadProgress,
  AuditLogEntry,
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

// Status query
export const useStatus = (options?: UseQueryOptions<{
  api_key_configured: boolean;
  smtp_configured: boolean;
  version: string;
}, Error>) => {
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: getStatus,
    retry: 2,
    staleTime: 30000,
    ...options,
  });
};

// Candidate queries
export const useCandidate = (id: string, options?: UseQueryOptions<Candidate, Error>) => {
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
      const { data } = await uploadResume(file, onProgress);
      return data;
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
export const useJobs = (options?: UseQueryOptions<Job[], Error>) => {
  return useQuery({
    queryKey: queryKeys.jobs,
    queryFn: listJobs,
    retry: 2,
    staleTime: 60000,
    ...options,
  });
};

export const useJob = (id: string, options?: UseQueryOptions<Job, Error>) => {
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
      const { data } = await matchJobs(candidateId);
      return data.matches;
    },
    onSuccess: (matches, candidateId) => {
      // Set the matches in the cache
      queryClient.setQueryData(queryKeys.matches(candidateId), matches);
    },
  });
};

// Matches query
export const useMatches = (candidateId: string, options?: UseQueryOptions<JobMatch[], Error>) => {
  return useQuery({
    queryKey: queryKeys.matches(candidateId),
    queryFn: async () => {
      const { data } = await matchJobs(candidateId);
      return data.matches;
    },
    enabled: !!candidateId,
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
      const { data } = await chat(messages, candidateId, sendConfirmed);
      return data;
    },
  });
};

// Audit log query
export const useAuditLog = (
  limit = 20,
  candidateId?: string,
  options?: UseQueryOptions<AuditLogEntry[], Error>
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
