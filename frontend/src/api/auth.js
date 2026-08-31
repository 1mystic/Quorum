// Real calls against app/api/auth.py and app/api/tenant.py. Shapes match
// app/schemas/user.py and app/schemas/tenant.py exactly - see those files
// before changing a field name here.

import { api } from './client'

export function login(email, password) {
  return api.post('/auth/login', { email, password }, { auth: false })
}

export function signup({ fullName, email, password, confirmPassword, role, tenantSlug }) {
  return api.post('/auth/signup', {
    full_name: fullName,
    email,
    password,
    confirm_password: confirmPassword,
    role,
    tenant_slug: tenantSlug || null
  }, { auth: false })
}

export function forgotPassword(email) {
  return api.post('/auth/forgot-password', { email }, { auth: false })
}

export function resetPassword(token, password, confirmPassword) {
  return api.post('/auth/reset-password', {
    token,
    password,
    confirm_password: confirmPassword
  }, { auth: false })
}

// Requires an authenticated TENANT_ADMIN session - call after signup()/login()
// has set the token, per app/api/tenant.py's Security(scopes=["TENANT_ADMIN"]).
export function onboardTenant({ name, slug, vertical, description }) {
  return api.post('/tenant/onboarding', { name, slug, vertical, description })
}
