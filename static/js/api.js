import { state, clearAuth } from './state.js';

export class APIError extends Error {
  constructor(status, detail, body) {
    super(`${status} ${detail}`);
    this.status = status;
    this.detail = detail;
    this.body = body;
  }
}

export async function api(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (state.accessToken) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }

  const res = await fetch(path, { ...options, headers, credentials: 'include' });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};

  if (!res.ok) {
    if (res.status === 401) {
      clearAuth();
    }
    throw new APIError(res.status, data.detail || res.statusText, data);
  }

  return data;
}
