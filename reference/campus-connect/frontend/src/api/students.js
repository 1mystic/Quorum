const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function authHeaders() {
  const token = localStorage.getItem('cc_token')
  const headers = {}

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  return headers
}

async function readError(response) {
  const body = await response.json().catch(() => ({}))
  return new Error(body.detail || body.message || 'Request failed')
}

/**
 * The student's own profile, including the interests the AI Club Finder reads.
 */
export async function getMyProfile() {
  const response = await fetch(`${BASE_URL}/students/me`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders()
    }
  })

  if (!response.ok) {
    throw await readError(response)
  }

  return response.json()
}

/**
 * Update the signed-in student's profile.
 *
 * The endpoint takes multipart/form-data, not JSON: the backend reads the
 * profile as a JSON string in a `data` field and an optional `image` file
 * alongside it (see app/core/forms.py parse_form_model). Content-Type is
 * deliberately not set here - the browser has to add its own multipart
 * boundary, and setting it by hand breaks the upload.
 *
 * Only the keys present in `profile` are changed; the backend applies the
 * update with exclude_unset, so omitted fields keep their current value.
 */
export async function updateMyProfile(profile, image = null) {
  const form = new FormData()
  form.append('data', JSON.stringify(profile))

  if (image) {
    form.append('image', image)
  }

  const response = await fetch(`${BASE_URL}/students/me`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: form
  })

  if (!response.ok) {
    throw await readError(response)
  }

  return response.json()
}

export { BASE_URL }
