/**
 * Thin fetch wrapper around the FastAPI backend.
 * The base URL is configurable through VITE_API_URL (see .env.example).
 */

const BASE_URL = (import.meta.env?.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.append(key, value);
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (networkError) {
    throw new Error(`Cannot reach the fraud engine API at ${BASE_URL}`);
  }

  if (!response.ok) {
    let detail = `Request failed (HTTP ${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* response had no JSON body - keep the generic message */
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const apiBaseUrl = BASE_URL;

export const api = {
  health: () => request('/health'),
  engineInfo: () => request('/api/stats/engine'),
  summary: () => request('/api/stats/summary'),
  listFlags: (params) => request(`/api/fraud-flags${buildQuery(params)}`),
  getFlag: (id) => request(`/api/fraud-flags/${id}`),
  reviewFlag: (id, body) =>
    request(`/api/fraud-flags/${id}/review`, { method: 'PATCH', body: JSON.stringify(body) }),
  clearFlag: (id, body = {}) =>
    request(`/api/fraud-flags/${id}/clear`, { method: 'PATCH', body: JSON.stringify(body) }),
  listTransactions: (params) => request(`/api/transactions${buildQuery(params)}`),
};
