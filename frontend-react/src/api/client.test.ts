import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock axios before importing client
const mockGet = vi.fn();
const mockPost = vi.fn();
const mockCreate = vi.fn(() => ({
  get: mockGet,
  post: mockPost,
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
}));

vi.mock('axios', () => ({
  default: {
    create: mockCreate,
    AxiosError: class AxiosError extends Error {},
  },
  AxiosError: class AxiosError extends Error {},
}));

// Now import — axios.create() returns our mock instance
const {
  getCandidate,
  listJobs,
  getJob,
  matchJobs,
  chat,
  getStatus,
  getAuditLog,
  submitApplication,
} = await import('./client');

describe('API client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getCandidate', () => {
    it('calls GET /candidates/:id and returns data', async () => {
      const fake = { id: 'c1', name: 'Alice', years_experience: 5, skills: [], education: [], experience: [], certifications: [] };
      mockGet.mockResolvedValueOnce({ data: fake });

      const result = await getCandidate('c1');

      expect(mockGet).toHaveBeenCalledWith('/candidates/c1');
      expect(result).toEqual(fake);
    });
  });

  describe('listJobs', () => {
    it('calls GET /jobs and returns data', async () => {
      const jobs = [{ id: 'j1', title: 'Engineer' }];
      mockGet.mockResolvedValueOnce({ data: jobs });

      const result = await listJobs();

      expect(mockGet).toHaveBeenCalledWith('/jobs');
      expect(result).toEqual(jobs);
    });
  });

  describe('getJob', () => {
    it('calls GET /jobs/:id and returns data', async () => {
      const job = { id: 'j1', title: 'Engineer' };
      mockGet.mockResolvedValueOnce({ data: job });

      const result = await getJob('j1');

      expect(mockGet).toHaveBeenCalledWith('/jobs/j1');
      expect(result).toEqual(job);
    });
  });

  describe('matchJobs', () => {
    it('calls POST /match with candidate_id', async () => {
      const response = { matches: [{ job_id: 'j1', match_score: 85 }] };
      mockPost.mockResolvedValueOnce({ data: response });

      const result = await matchJobs('c1');

      expect(mockPost).toHaveBeenCalledWith('/match', { candidate_id: 'c1' });
      expect(result).toEqual(response);
    });
  });

  describe('chat', () => {
    it('calls POST /chat with messages and candidate_id', async () => {
      const messages = [{ role: 'user', content: 'hello' }];
      const response = { messages, assistant_text: 'hi there' };
      mockPost.mockResolvedValueOnce({ data: response });

      const result = await chat(messages, 'c1');

      expect(mockPost).toHaveBeenCalledWith('/chat', {
        messages,
        candidate_id: 'c1',
        send_confirmed: false,
      });
      expect(result).toEqual(response);
    });

    it('defaults send_confirmed to false', async () => {
      mockPost.mockResolvedValueOnce({ data: { messages: [], assistant_text: '' } });

      await chat([]);

      expect(mockPost).toHaveBeenCalledWith('/chat', {
        messages: [],
        candidate_id: undefined,
        send_confirmed: false,
      });
    });
  });

  describe('getStatus', () => {
    it('calls GET /status', async () => {
      const status = { api_key_configured: true, smtp_configured: false, version: '1.0' };
      mockGet.mockResolvedValueOnce({ data: status });

      const result = await getStatus();

      expect(mockGet).toHaveBeenCalledWith('/status');
      expect(result).toEqual(status);
    });
  });

  describe('getAuditLog', () => {
    it('calls GET /audit-log with default params', async () => {
      const logs = [{ id: 'a1', action: 'upload' }];
      mockGet.mockResolvedValueOnce({ data: logs });

      const result = await getAuditLog();

      expect(mockGet).toHaveBeenCalledWith('/audit-log', { params: { limit: 20, candidate_id: undefined } });
      expect(result).toEqual(logs);
    });

    it('passes custom limit and candidateId', async () => {
      mockGet.mockResolvedValueOnce({ data: [] });

      await getAuditLog(5, 'c1');

      expect(mockGet).toHaveBeenCalledWith('/audit-log', { params: { limit: 5, candidate_id: 'c1' } });
    });
  });

  describe('submitApplication', () => {
    it('calls POST /applications with correct payload', async () => {
      const response = { status: 'sent', message_id: 'm1' };
      mockPost.mockResolvedValueOnce({ data: response });

      const result = await submitApplication('c1', 'j1', 85, 'STRONG_MATCH');

      expect(mockPost).toHaveBeenCalledWith('/applications', {
        candidate_id: 'c1',
        job_id: 'j1',
        draft: { match_score: 85, match_tier: 'STRONG_MATCH' },
        send_confirmed: true,
      });
      expect(result).toEqual(response);
    });
  });

  describe('error handling', () => {
    it('propagates errors from axios', async () => {
      mockGet.mockRejectedValueOnce(new Error('Network Error'));

      await expect(getCandidate('c1')).rejects.toThrow('Network Error');
    });
  });
});
