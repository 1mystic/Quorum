const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"


function extractMessage(body) {
  if (typeof body.message === 'string') return body.message
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail) && body.detail.length) return body.detail[0].msg || 'Request failed'
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

export async function getNotifications(params = {}) {
  const query = new URLSearchParams(params).toString()

  return apiRequest(
    `/notifications${query ? `?${query}` : ""}`
  )
}

export async function getUnreadNotificationCount() {
  return apiRequest("/notifications/unread-count")
}

export async function markNotificationRead(notificationId) {
  return apiRequest(`/notifications/${notificationId}/read`, {
    method: "PATCH"
  })
}

export async function markAllNotificationsRead() {
  return apiRequest("/notifications/read-all", {
    method: "POST"
  })
}

export { BASE_URL }