const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"


function extractMessage(body) {
  if (typeof body.message === 'string') return body.message
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail) && body.detail.length) {
    return body.detail[0].msg || 'Request failed'
  }
  return 'Request failed'
}

async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem("cc_token")

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(extractMessage(error))
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export async function getLeaderAnnouncements(params = {}) {
  const query = new URLSearchParams(params).toString()

  return apiRequest(`/announcements/mine${query ? `?${query}` : ""}`)
}

export async function getAnnouncements(params = {}) {
  const query = new URLSearchParams(params).toString()

  return apiRequest(`/announcements${query ? `?${query}` : ""}`)
}

export async function postAnnouncement(data) {
  return apiRequest("/announcements", {
    method: "POST",
    body: JSON.stringify(data)
  })
}

export async function togglePin(announcementId, pinned) {
  return apiRequest(`/announcements/${announcementId}/pin`, {
    method: "PATCH",
    body: JSON.stringify({
      pinned
    })
  })
}

export async function deleteAnnouncement(announcementId) {
  return apiRequest(`/announcements/${announcementId}`, {
    method: "DELETE"
  })
}

export async function getUnreadCount() {
  return apiRequest("/announcements/unread-count")
}

export async function markAnnouncementsRead() {
  return apiRequest("/announcements/read-all", {
    method: "POST"
  })
}

export { BASE_URL }
