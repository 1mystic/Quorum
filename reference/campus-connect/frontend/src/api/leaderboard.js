const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
    throw new Error(body.detail || body.message || 'Request failed')
  }

  return response.json()
}

/**
 * The full club ranking, one row per club, already sorted by rank.
 * Shape: { rank, club_id, name, image_url, category, score, events_held,
 *          new_members, issues_resolved, attendance_rate, attendance_bonus }
 */
export async function getLeaderboard() {
  return apiRequest('/leaderboard')
}

export { BASE_URL }
