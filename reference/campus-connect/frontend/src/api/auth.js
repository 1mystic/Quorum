const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function extractMessage(body) {
  if (typeof body.message === "string") return body.message;
  if (typeof body.detail === "string") return body.detail;

  if (Array.isArray(body.detail) && body.detail.length) {
    return body.detail[0].msg || "Request failed";
  }

  return "Request failed";
}

async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem("cc_token");

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  let body = {};

  if (response.status !== 204) {
    body = await response.json().catch(() => ({}));
  }

  if (!response.ok) {
    throw new Error(extractMessage(body));
  }

  return body;
}

export async function loginUser(email, password) {
  return apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export async function signupUser(data) {
  return apiRequest("/auth/signup", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function googleAuth(idToken, intent = "login") {
  return apiRequest("/auth/google", {
    method: "POST",
    body: JSON.stringify({ id_token: idToken, intent }),
  });
}

export async function verifyEmailOtp(email, code) {
  return apiRequest("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({
      email,
      code,
    }),
  });
}

export async function resendOtp(email) {
  return apiRequest("/auth/resend-otp", {
    method: "POST",
    body: JSON.stringify({
      email,
    }),
  });
}

export async function sendResetLink(email) {
  return apiRequest("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({
      email,
    }),
  });
}

export async function resetPassword(token, password, confirmPassword) {
  return apiRequest("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({
      token,
      password,
      confirm_password: confirmPassword,
    }),
  });
}

export async function onboardCollege(data, token) {
  return apiRequest("/college/onboarding", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });
}

/**
 * @deprecated POST /auth/onboarding was never implemented and returns 404.
 * Onboarding now saves through updateMyProfile() in api/students.js, which
 * calls the real PATCH /students/me. Kept only so the existing auth tests
 * that import it keep passing; no view calls this any more.
 */
export async function saveOnboarding(profile) {
  return apiRequest("/auth/onboarding", {
    method: "POST",
    body: JSON.stringify(profile),
  });
}

export { BASE_URL };
