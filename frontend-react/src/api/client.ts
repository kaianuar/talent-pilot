import axios, { type AxiosInstance, type AxiosProgressEvent } from 'axios';
import { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:9000';

export interface Candidate {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  website?: string;
  years_experience: number;
  skills: Skill[];
  education: Education[];
  experience: Experience[];
  certifications: string[];
  raw_text: string;
}

export interface Skill {
  name: string;
  level?: string;
  years?: number;
}

export interface Education {
  degree: string;
  field?: string;
  institution: string;
  graduation_date?: string;
}

export interface Experience {
  title: string;
  company: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  description?: string;
}

export interface Job {
  id: string;
  title: string;
  department: string;
  location: string;
  salary_range?: string;
  description: string;
  requirements: string[];
  nice_to_have: string[];
  employment_type: string;
  remote_policy: string;
  posted_date: string;
  status: string;
}

export interface JobMatch {
  job_id: string;
  job_title: string;
  match_score: number;
  tier: 'STRONG_MATCH' | 'PARTIAL_MATCH' | 'POOR_MATCH' | 'NO_MATCH';
  required_match_ratio: number;
  adjacent_bonus: number;
  experience_score: number;
  llm_reasoning_score: number;
  reasoning_explanation: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  candidate_id?: string;
  job_id?: string;
  status: string;
  details: Record<string, unknown>;
}

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const message = error.response?.data?.detail || error.message || 'Unknown error';
    console.error('[API Error]', message);
    return Promise.reject(new Error(message));
  }
);

// API functions — all return unwrapped data (not AxiosResponse)
export const uploadResume = (
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<{ candidate_id: string; parsed: Candidate; pdf_path: string }> => {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.post<{ candidate_id: string; parsed: Candidate; pdf_path: string }>(
    '/upload',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const loaded = progressEvent.loaded;
          const total = progressEvent.total;
          const percentage = Math.round((loaded * 100) / total);
          onProgress({ loaded, total, percentage });
        }
      },
    }
  ).then(r => r.data);
};

export const getCandidate = (id: string): Promise<Candidate> => {
  return apiClient.get<Candidate>(`/candidates/${id}`).then(r => r.data);
};

export const listJobs = (): Promise<Job[]> => {
  return apiClient.get<Job[]>('/jobs').then(r => r.data);
};

export const getJob = (id: string): Promise<Job> => {
  return apiClient.get<Job>(`/jobs/${id}`).then(r => r.data);
};

export const matchJobs = (candidateId: string): Promise<{ matches: JobMatch[] }> => {
  return apiClient.post<{ matches: JobMatch[] }>('/match', { candidate_id: candidateId }).then(r => r.data);
};

export const chat = (messages: Array<{ role: string; content: string }>, candidateId?: string, sendConfirmed?: boolean): Promise<{
    messages: Array<{ role: string; content: string }>;
    assistant_text: string;
  }> => {
  return apiClient.post<{
    messages: Array<{ role: string; content: string }>;
    assistant_text: string;
  }>('/chat', {
    messages,
    candidate_id: candidateId,
    send_confirmed: sendConfirmed || false,
  }).then(r => r.data);
};

export const getAuditLog = (limit = 20, candidateId?: string): Promise<AuditLogEntry[]> => {
  return apiClient.get<AuditLogEntry[]>('/audit-log', {
    params: { limit, candidate_id: candidateId },
  }).then(r => r.data);
};

export const getStatus = (): Promise<{
    api_key_configured: boolean;
    smtp_configured: boolean;
    version: string;
  }> => {
  return apiClient.get<{
    api_key_configured: boolean;
    smtp_configured: boolean;
    version: string;
  }>('/status').then(r => r.data);
};
export default apiClient;
