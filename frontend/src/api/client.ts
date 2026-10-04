export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export function getAuthToken(): string | null {
  return sessionStorage.getItem('trustdesk_token');
}

export function setAuthToken(token: string): void {
  sessionStorage.setItem('trustdesk_token', token);
}

export function removeAuthToken(): void {
  sessionStorage.removeItem('trustdesk_token');
  sessionStorage.removeItem('trustdesk_user');
}

export function getCsrfToken(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)trustdesk_csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const token = getAuthToken();

  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');

  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      removeAuthToken();
      window.dispatchEvent(new CustomEvent('trustdesk:unauthorized'));
    }

    if (!response.ok) {
      let errorData: unknown;
      if (typeof response.clone === 'function') {
        try {
          errorData = await response.clone().json();
        } catch {
          try {
            errorData = await response.text();
          } catch {
            errorData = null;
          }
        }
      } else if (typeof response.text === 'function') {
        try {
          const rawText = await response.text();
          errorData = JSON.parse(rawText);
        } catch {
          errorData = null;
        }
      }
      if (!errorData && typeof response.json === 'function') {
        try {
          errorData = await response.json();
        } catch {
          errorData = null;
        }
      }

      const message = typeof errorData === 'object' && errorData !== null && 'error' in errorData
        ? String((errorData as { error: string }).error)
        : typeof errorData === 'object' && errorData !== null && 'detail' in errorData
        ? String((errorData as { detail: string }).detail)
        : typeof errorData === 'string' && errorData.trim()
        ? errorData
        : `Request failed with status ${response.status}`;

      throw new ApiError(message, response.status, errorData);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(
      err instanceof Error ? err.message : 'Network error or backend unreachable',
      0
    );
  }
}

export function streamDraftTokens(
  ticketId: string,
  onToken: (token: string) => void,
  onDone: (data: { draft_id?: string; citations?: string[] }) => void,
  onError: (err: Error) => void
): () => void {
  const token = getAuthToken();
  const url = `${API_BASE}/tickets/${ticketId}/draft/stream`;

  const controller = new AbortController();

  fetch(url, {
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Streaming failed with status ${response.status}`);
      }
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No readable stream available');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.done) {
                onDone({ draft_id: data.draft_id, citations: data.citations });
              } else if (data.token !== undefined) {
                onToken(data.token);
              }
            } catch (parseErr) {
              console.warn('Failed to parse SSE line:', line, parseErr);
              onError(new Error(`Malformed streaming data: ${parseErr instanceof Error ? parseErr.message : String(parseErr)}`));
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err instanceof Error ? err : new Error(String(err)));
      }
    });

  return () => {
    controller.abort();
  };
}
