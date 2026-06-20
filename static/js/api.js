import { state, clearAuth } from './state.js';

/** Extract a human-readable message from any API error shape. */
function _humanError(body) {
  if (!body) return '请求失败';
  if (typeof body === 'string') return body;
  if (Array.isArray(body) && body.length) return _humanError(body[0]);
  if (body.detail) {
    if (typeof body.detail === 'string') return body.detail;
    if (typeof body.detail === 'object') {
      if (body.detail.message) return body.detail.message;
      if (body.detail.issues && Array.isArray(body.detail.issues)) {
        return body.detail.issues.map(i => i.message || i.code || '').filter(Boolean).join('; ') || '请求失败';
      }
      return JSON.stringify(body.detail);
    }
  }
  if (body.message) return body.message;
  if (body.issues && Array.isArray(body.issues)) {
    return body.issues.map(i => i.message || i.code || '').filter(Boolean).join('; ') || '请求失败';
  }
  return '请求失败';
}

export class APIError extends Error {
  constructor(status, detail, body) {
    const msg = _humanError(detail !== undefined ? detail : body);
    super(msg);
    this.status = status;
    this.detail = detail;
    this.body = body;
    this.humanMessage = msg;
  }
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const isFormData = options.body instanceof FormData;

  // Never set Content-Type manually for FormData — browser handles multipart boundary
  if (!isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  if (state.accessToken) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }

  const res = await fetch(path, { ...options, headers, credentials: 'include' });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { detail: text || res.statusText }; }

  if (!res.ok) {
    if (res.status === 401) {
      clearAuth();
    }
    throw new APIError(res.status, data.detail || data, data);
  }

  return data;
}
