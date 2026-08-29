const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'


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
    throw new Error(error.detail || error.message || "Request failed")
  }

  if (response.status === 204) {
  return null
  }

  return response.json()
}



export async function getClubs() {
  return apiRequest("/clubs")
}

// Public, unauthenticated - powers the marketing landing page. No token is
// sent even if one exists, since this must work for logged-out visitors.
export async function getTrendingClubs(limit = 8) {
  const response = await fetch(`${BASE_URL}/clubs/public/trending?limit=${limit}`)

  if (!response.ok) {
    throw new Error("Failed to load trending clubs")
  }

  return response.json()
}

export async function getMyClubs(params = {}) {
  const query = new URLSearchParams(params).toString()

  return apiRequest(`/clubs/me${query ? `?${query}` : ""}`)
}

export async function getClubById(clubId) {
  return apiRequest(`/clubs/${clubId}`)
}

export async function requestToJoinClub(clubId) {
  return apiRequest(`/clubs/${clubId}/join`, {
    method: "POST"
  })
}

export async function leaveClub(clubId) {
  return apiRequest(`/clubs/${clubId}/join`, {
    method: "DELETE"
  })
}

// Club create/update take multipart/form-data, not JSON: the backend reads the
// body as a JSON string in a `data` field with an optional `image` file beside
// it. Content-Type is left unset on purpose so the browser adds its own
// multipart boundary - setting it by hand makes the upload unparseable.
async function multipartRequest(endpoint, method, payload, image) {
  const token = localStorage.getItem("cc_token")
  const headers = {}

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const form = new FormData()
  form.append("data", JSON.stringify(payload))

  if (image) {
    form.append("image", image)
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method,
    headers,
    body: form
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || error.message || "Request failed")
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export async function createClub(clubData, image = null) {
  return multipartRequest("/clubs", "POST", clubData, image)
}

export async function updateClub(clubId, clubData, image = null) {
  return multipartRequest(`/clubs/${clubId}`, "PUT", clubData, image)
}

export async function deleteClub(clubId) {
  return apiRequest(`/clubs/${clubId}`, {
    method: "DELETE"
  })
}

export async function getClubMembers(clubId) {
  return apiRequest(`/clubs/${clubId}/members`)
}

export async function removeMember(clubId, studentId) {
  return apiRequest(`/clubs/${clubId}/members/${studentId}`, {
    method: "DELETE"
  })
}

export async function getPendingRequests(clubId) {
  return apiRequest(`/clubs/${clubId}/requests`)
}

export async function handleMembershipRequest(
  clubId,
  membershipId,
  action
) {
  return apiRequest(`/clubs/${clubId}/requests/${membershipId}`, {
    method: "PATCH",
    body: JSON.stringify({
      action
    })
  })
}

export async function getClubApprovals(status = "PENDING") {
  return apiRequest(`/clubs?status=${status}`)
}

export async function approveClubRequest(clubId) {
  return apiRequest(`/clubs/${clubId}/approve`, {
    method: "PATCH"
  })
}

export async function rejectClubRequest(clubId) {
  return apiRequest(`/clubs/${clubId}/reject`, {
    method: "PATCH"
  })
}

export { BASE_URL }
