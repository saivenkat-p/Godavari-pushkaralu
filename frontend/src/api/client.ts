const API_BASE = '/api';

export function getAuthToken(): string | null {
  return localStorage.getItem('bandham_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('bandham_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('bandham_token');
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  const rawText = await response.text();

  if (!response.ok) {
    let errorDetail = rawText || `Request failed with status ${response.status}`;
    try {
      const errJson = JSON.parse(rawText);
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // Keep errorDetail as rawText
    }
    throw new Error(errorDetail);
  }

  if (!rawText) {
    return {} as T;
  }

  try {
    return JSON.parse(rawText) as T;
  } catch {
    return rawText as unknown as T;
  }
}
