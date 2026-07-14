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

  describe('response interceptor', () => {
    it('passes through successful responses unchanged', async () => {
      // The first argument to interceptors.response.use is the success
      // pass-through. Verify it returns the response as-is.
      // The mock factory is recreated on each module import; capture the
      // call args from the latest call to apiClient's create().
      // Re-import the client module to get a fresh interceptors capture.
      // The mock already provides apiClient.interceptors.response.use
      // as a vi.fn; we read it from the most recent call.
      // Since the module is already loaded, the interceptors were set
      // up at import time. We can capture them by re-reading the
      // singleton. Simplest: clear the mock, re-import.
      vi.resetModules();
      mockGet.mockReset();
      mockPost.mockReset();
      mockCreate.mockClear();
      await import('./client');
      // After the re-import, mockCreate was called once, and the
      // resulting object's interceptors.response.use was invoked once.
      const lastInstance = mockCreate.mock.results[mockCreate.mock.results.length - 1].value;
      const successHandler = lastInstance.interceptors.response.use.mock.calls[0][0];
      const response = { data: { ok: true }, status: 200, headers: {} };
      expect(successHandler(response)).toBe(response);
      vi.resetModules();
    });

    it('extracts the FastAPI detail field and rejects with an Error', async () => {
      vi.resetModules();
      mockCreate.mockClear();
      await import('./client');
      const lastInstance = mockCreate.mock.results[mockCreate.mock.results.length - 1].value;
      const errorHandler = lastInstance.interceptors.response.use.mock.calls[0][1];

      // Build an Axios-shaped error with a FastAPI 422 response
      const err = {
        response: { data: { detail: 'Only PDF files are accepted' } },
        message: 'Request failed with status code 422',
      };
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      try {
        await expect(errorHandler(err)).rejects.toThrow('Only PDF files are accepted');
        expect(spy).toHaveBeenCalledWith('[API Error]', 'Only PDF files are accepted');
      } finally {
        spy.mockRestore();
        vi.resetModules();
      }
    });

    it('falls back to error.message when no detail is present', async () => {
      vi.resetModules();
      mockCreate.mockClear();
      await import('./client');
      const lastInstance = mockCreate.mock.results[mockCreate.mock.results.length - 1].value;
      const errorHandler = lastInstance.interceptors.response.use.mock.calls[0][1];

      const err = { message: 'Network Error' };
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      try {
        await expect(errorHandler(err)).rejects.toThrow('Network Error');
        expect(spy).toHaveBeenCalledWith('[API Error]', 'Network Error');
      } finally {
        spy.mockRestore();
        vi.resetModules();
      }
    });

    it('falls back to a generic message when neither detail nor message is present', async () => {
      vi.resetModules();
      mockCreate.mockClear();
      await import('./client');
      const lastInstance = mockCreate.mock.results[mockCreate.mock.results.length - 1].value;
      const errorHandler = lastInstance.interceptors.response.use.mock.calls[0][1];

      const err = {};
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      try {
        await expect(errorHandler(err)).rejects.toThrow('Unknown error');
        expect(spy).toHaveBeenCalledWith('[API Error]', 'Unknown error');
      } finally {
        spy.mockRestore();
        vi.resetModules();
      }
    });
  });

  describe('uploadResume', () => {
    it('POSTs multipart/form-data to /upload and returns the parsed data', async () => {
      const { uploadResume } = await import('./client');
      const parsed = {
        candidate_id: 'c1',
        parsed: { id: 'c1', name: 'Alice', years_experience: 5, skills: [], education: [], experience: [], certifications: [] },
        pdf_path: 'uploads/c1.pdf',
      };
      mockPost.mockResolvedValueOnce({ data: parsed });

      const file = new File(['pdf bytes'], 'resume.pdf', { type: 'application/pdf' });
      const result = await uploadResume(file);

      expect(mockPost).toHaveBeenCalledTimes(1);
      const [url, body, config] = mockPost.mock.calls[0];
      expect(url).toBe('/upload');
      expect(body).toBeInstanceOf(FormData);
      // The FormData contains the file under the 'file' key
      expect((body as FormData).get('file')).toBe(file);
      expect(config.headers['Content-Type']).toBe('multipart/form-data');
      expect(config.onUploadProgress).toBeTypeOf('function');
      expect(result).toEqual(parsed);
    });

    it('invokes the onProgress callback with percentage when total is set', async () => {
      const { uploadResume } = await import('./client');
      mockPost.mockImplementationOnce((_url, _body, config) => {
        // Simulate the onUploadProgress callback the way axios would
        config.onUploadProgress({ loaded: 50, total: 100 });
        config.onUploadProgress({ loaded: 75, total: 100 });
        return Promise.resolve({ data: { candidate_id: 'c1', parsed: {} as never, pdf_path: 'p' } });
      });

      const file = new File(['x'], 'a.pdf', { type: 'application/pdf' });
      const progress: Array<{ loaded: number; total: number; percentage: number }> = [];
      await uploadResume(file, (p) => progress.push(p));

      expect(progress).toEqual([
        { loaded: 50, total: 100, percentage: 50 },
        { loaded: 75, total: 100, percentage: 75 },
      ]);
    });

    it('skips progress callbacks when total is zero (unknown size)', async () => {
      const { uploadResume } = await import('./client');
      mockPost.mockImplementationOnce((_url, _body, config) => {
        // Some servers don't send Content-Length; total is 0/undefined.
        config.onUploadProgress({ loaded: 50, total: 0 });
        return Promise.resolve({ data: { candidate_id: 'c1', parsed: {} as never, pdf_path: 'p' } });
      });

      const file = new File(['x'], 'a.pdf', { type: 'application/pdf' });
      const progress: unknown[] = [];
      await uploadResume(file, (p) => progress.push(p));

      // Callback should not have fired because total was falsy
      expect(progress).toEqual([]);
    });
  });
});
