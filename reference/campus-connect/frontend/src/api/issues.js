const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function extractMessage(body) {
  // AppException replies with {"message": ...}; FastAPI validation errors with
  // {"detail": [{msg, loc}, ...]} and auth failures with {"detail": "..."}.
  if (typeof body.message === 'string') return body.message
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail) && body.detail.length) {
    return body.detail[0].msg || 'Request failed'
  }
  return 'Request failed'
}

async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem('cc_token')

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(extractMessage(body))
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

// The API uses upper-case enum members; the UI works in lower case for its
// status pills and select options. These two helpers are the only place that
// difference is allowed to matter.
export function toApiCategory(category) {
  return String(category || '').toUpperCase()
}

// IN_PROGRESS becomes "in-progress", not "in_progress": the status pill CSS
// and the leader queue's filters were already written against the hyphenated
// form, so the API value is normalised to match rather than restyling them.
function toUiStatus(status) {
  return String(status || '').toLowerCase().replace(/_/g, '-')
}

const STATUS_LABELS = {
  'open': 'Open',
  'in-progress': 'In Progress',
  'resolved': 'Resolved'
}

function formatDate(value) {
  if (!value) return ''

  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

/**
 * Shape one API issue into what IssueCard renders.
 *
 * The card was written against the old mock shape (meta, desc, statusLabel),
 * so the mapping happens here rather than changing every template that uses
 * it.
 */
function toCardIssue(issue) {
  const status = toUiStatus(issue.status)

  return {
    id: issue.id,
    title: issue.title,
    desc: issue.description,
    status,
    statusLabel: STATUS_LABELS[status] || issue.status,
    meta: `${issue.club_name} · ${formatDate(issue.created_at)}`,
    tags: issue.category ? [String(issue.category).toLowerCase()] : [],
    response: issue.response
      ? {
          by: issue.response.by,
          text: issue.response.text,
          at: issue.response.at,
          atLabel: formatDate(issue.response.at)
        }
      : null,
    clubId: issue.club_id,
    createdAt: issue.created_at,
    resolvedAt: issue.resolved_at
  }
}

/** Issues raised by the signed-in student. */
export async function getIssues(params = {}) {
  const query = new URLSearchParams(params).toString()
  const rows = await apiRequest(`/issues${query ? `?${query}` : ''}`)

  return rows.map(toCardIssue)
}

/** The queue of issues raised against clubs the caller leads. */
export async function getLeaderIssues(params = {}) {
  const query = new URLSearchParams(params).toString()
  const rows = await apiRequest(`/issues/club${query ? `?${query}` : ''}`)

  return rows.map(function toLeaderCard(issue) {
    return {
      ...toCardIssue(issue),
      raisedBy: issue.raised_by || ''
    }
  })
}

/** How many open issues are waiting on the caller's clubs. */
export async function getOpenIssueCount() {
  const body = await apiRequest('/issues/club/open-count')

  return body?.count ?? 0
}

/**
 * Raise an issue against a club.
 *
 * `issue` must carry club_id, category, title and description - the shape of
 * RaiseIssueRequest. event_id is optional and only used when the query is
 * about a specific event.
 */
export async function raiseIssue(issue) {
  return apiRequest('/issues', {
    method: 'POST',
    body: JSON.stringify({
      club_id: issue.club_id,
      category: toApiCategory(issue.category),
      title: issue.title,
      description: issue.description,
      ...(issue.event_id ? { event_id: issue.event_id } : {})
    })
  })
}

export async function replyToIssue(issueId, reply) {
  return apiRequest(`/issues/${issueId}/reply`, {
    method: 'POST',
    body: JSON.stringify({ reply })
  })
}

export async function resolveIssue(issueId) {
  return apiRequest(`/issues/${issueId}/resolve`, { method: 'PATCH' })
}

export { BASE_URL }
