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
 * The signed-in student's certificate wallet.
 * Shape per item: { serial, result, event_id, event_title, club_name,
 *                    issued_at, download_url }
 */
export async function getMyCertificates() {
  return apiRequest('/certificates/me')
}

/**
 * A fresh, time-limited download link for one certificate.
 * Shape: { serial, filename, download_url, expires_in }
 */
export async function getCertificateDownload(serial) {
  return apiRequest(`/certificates/${encodeURIComponent(serial)}/download`)
}

/**
 * Public lookup by serial - no token required, and the backend enforces
 * that: this call never attaches Authorization, matching the certificate
 * router's unauthenticated verify route.
 *
 * Returns { valid: true, ...certificate } on a match. A serial the backend
 * does not recognise is a 404, which resolves to { valid: false } rather
 * than throwing, since "not found" is the expected outcome of a lookup, not
 * a failure of the request.
 */
export async function verifyCertificate(serial) {
  const response = await fetch(
    `${BASE_URL}/certificates/verify/${encodeURIComponent(serial)}`
  )

  if (response.status === 404) {
    return { valid: false }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || body.message || 'Request failed')
  }

  const certificate = await response.json()

  return { valid: certificate.valid, certificate }
}

export { BASE_URL }
