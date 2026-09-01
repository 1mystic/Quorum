// The one place that talks to the real backend. Every fetch in the app goes
// through `api.get/post/patch/put/delete`, never a bare `fetch(...)` in a
// view. Base URL comes from an env var so the same build can point at a
// local uvicorn, a staging box or nothing at all (see .env.example).
//
// Two error types on purpose, because a view needs to tell them apart:
// `NetworkError` is "the request never got a response" (offline, CORS,
// server down); `ApiError` is "the server answered and said no", and it
// carries the backend's own `message` (see app/exceptions.py's handler in
// main.py, which always returns `{"message": ...}`).

import { useAuthStore } from '../stores/auth'
import router from '../router'

export const API_BASE_URL = (
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  'http://localhost:8000/api'
).replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export class NetworkError extends Error {
  constructor(message) {
    super(message)
    this.name = 'NetworkError'
  }
}

// Two error shapes reach here, and a view must never see raw JSON or a bare
// "Request failed (422)" for either. The app's own AppException handler
// (main.py) always replies {"message": "..."}. Pydantic's automatic request
// validation, which fires before a route body even runs, replies
// {"detail": [{"loc": [...], "msg": "...", "type": "..."}]} instead, a
// completely different shape FastAPI builds without going through that
// handler. A too-short password or a malformed email hits this second path.
function describeErrorBody(data, status) {
  if (data && typeof data === 'object') {
    if (typeof data.message === 'string' && data.message) return data.message
    if (Array.isArray(data.detail) && data.detail.length) {
      return data.detail
        .map(function readOne(item) {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null
          return field && typeof field === 'string' ? field + ': ' + item.msg : item.msg
        })
        .filter(Boolean)
        .join(' ')
    }
    if (typeof data.detail === 'string' && data.detail) return data.detail
  }
  return 'Request failed (' + status + ').'
}

function buildUrl(path, params) {
  const url = new URL(path.startsWith('http') ? path : API_BASE_URL + path)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, value)
      }
    })
  }
  return url.toString()
}

// `tenantPath('vaikunth-heights', '/requests')` -> '/t/vaikunth-heights/requests',
// matching the backend's `/api/t/{slug}/...` prefix (docs/RULES.md §5).
export function tenantPath(slug, path) {
  return `/t/${slug}${path}`
}

async function request(path, { method = 'GET', body, params, auth: sendAuth = true } = {}) {
  const authStore = useAuthStore()
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (sendAuth && authStore.token) headers.Authorization = `Bearer ${authStore.token}`

  let response
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined
    })
  } catch {
    throw new NetworkError('Could not reach the Quorum server. Check your connection and try again.')
  }

  // A 401 on a call that actually carried a token means the session has
  // expired or was revoked, not that the credentials the caller just typed
  // were wrong (login/signup send auth:false and handle their own 401).
  if (response.status === 401 && sendAuth && authStore.token) {
    authStore.logout()
    if ((router.currentRoute.value.meta || {}).role !== 'public') {
      router.push('/login')
    }
    throw new ApiError('Your session has expired. Sign in again.', 401, null)
  }

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    throw new ApiError(describeErrorBody(data, response.status), response.status, data)
  }

  return data
}

export const api = {
  get: (path, opts) => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  patch: (path, body, opts) => request(path, { ...opts, method: 'PATCH', body }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  delete: (path, opts) => request(path, { ...opts, method: 'DELETE' })
}
