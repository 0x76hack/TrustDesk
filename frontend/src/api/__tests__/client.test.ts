import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  ApiError,
  getAuthToken,
  setAuthToken,
  removeAuthToken,
  apiFetch,
} from '../client';

describe('Frontend API Client Suite', () => {
  const mockStorage: Record<string, string> = {};

  beforeEach(() => {
    Object.keys(mockStorage).forEach((key) => delete mockStorage[key]);
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => mockStorage[key] || null,
      setItem: (key: string, value: string) => {
        mockStorage[key] = value;
      },
      removeItem: (key: string) => {
        delete mockStorage[key];
      },
      clear: () => {
        Object.keys(mockStorage).forEach((key) => delete mockStorage[key]);
      },
    });

    vi.stubGlobal('window', {
      dispatchEvent: vi.fn(),
    });
  });

  describe('ApiError', () => {
    it('creates an ApiError with status, message, and optional payload data', () => {
      const err = new ApiError('Resource not found', 404, { detail: 'Ticket #123 missing' });
      expect(err).toBeInstanceOf(Error);
      expect(err).toBeInstanceOf(ApiError);
      expect(err.name).toBe('ApiError');
      expect(err.message).toBe('Resource not found');
      expect(err.status).toBe(404);
      expect(err.data).toEqual({ detail: 'Ticket #123 missing' });
    });
  });

  describe('Token Storage Operations', () => {
    it('stores, retrieves, and clears authentication tokens', () => {
      expect(getAuthToken()).toBeNull();

      setAuthToken('jwt-sample-token-abc');
      expect(getAuthToken()).toBe('jwt-sample-token-abc');

      removeAuthToken();
      expect(getAuthToken()).toBeNull();
    });
  });

  describe('apiFetch() HTTP Request Handling', () => {
    it('attaches Authorization header when token is present', async () => {
      setAuthToken('bearer-token-123');

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ success: true, count: 5 }),
      });
      vi.stubGlobal('fetch', mockFetch);

      const result = await apiFetch<{ success: boolean; count: number }>('/tickets');

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [calledUrl, calledInit] = mockFetch.mock.calls[0];
      expect(calledUrl).toContain('/tickets');
      const headers = calledInit.headers as Headers;
      expect(headers.get('Authorization')).toBe('Bearer bearer-token-123');
      expect(headers.get('Accept')).toBe('application/json');
      expect(result).toEqual({ success: true, count: 5 });
    });

    it('handles 204 No Content gracefully by returning an empty object', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
      });
      vi.stubGlobal('fetch', mockFetch);

      const result = await apiFetch('/admin/users/123', { method: 'DELETE' });
      expect(result).toEqual({});
    });

    it('extracts detail string on HTTP 400/404 errors', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Target ticket not found' }),
      });
      vi.stubGlobal('fetch', mockFetch);

      await expect(apiFetch('/tickets/invalid-id')).rejects.toThrow('Target ticket not found');
    });

    it('extracts error string when response returns {"error": ...}', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid payload schema' }),
      });
      vi.stubGlobal('fetch', mockFetch);

      await expect(apiFetch('/tickets/create')).rejects.toThrow('Invalid payload schema');
    });

    it('clears token and dispatches unauthorized event on HTTP 401', async () => {
      setAuthToken('expired-token');

      const dispatchSpy = vi.fn();
      vi.stubGlobal('window', { dispatchEvent: dispatchSpy });

      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Token has expired' }),
      });
      vi.stubGlobal('fetch', mockFetch);

      await expect(apiFetch('/profile')).rejects.toThrow('Token has expired');
      expect(getAuthToken()).toBeNull();
      expect(dispatchSpy).toHaveBeenCalledTimes(1);
    });
  });
});
