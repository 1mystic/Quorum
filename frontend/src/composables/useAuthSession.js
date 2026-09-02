import { useRouter } from 'vue-router'
import { jwtDecode } from 'jwt-decode'
import { useAuthStore } from '../stores/auth'

// Completes a sign-in: decodes the JWT, seeds the auth store and routes the
// session to its tenant home. Called by LoginView/SignupView/OnboardView
// after a real api/auth.js call returns an access_token, per
// app/services/user.py's JWT payload (sub, full_name, email, role,
// tenant_id, tenant_slug) and the tenant routing rule in docs/RULES.md
// section 5 (routes are /api/t/{slug}/... and the slug must match the JWT
// claim). A TENANT_ADMIN's token has no tenant_slug until onboarding.

export function useAuthSession() {
  const router = useRouter()
  const auth = useAuthStore()

  async function completeSignIn(result) {
    auth.setToken(result.access_token)

    const payload = jwtDecode(result.access_token)
    const role = (payload.role || '').toLowerCase()
    // Backend role enum is MEMBER / TENANT_ADMIN (app/models/user.py), not
    // "admin" - a real admin login was silently landing here as 'member'
    // and losing access to every /admin route.

    auth.setUser({
      name: payload.full_name,
      email: payload.email,
      tenantSlug: payload.tenant_slug,
      tenantName: auth.user.tenantName,
      initials: (payload.full_name || '')
        .split(' ')
        .map((word) => word[0])
        .join('')
        .toUpperCase()
    })

    auth.setRole(role === 'tenant_admin' ? 'admin' : 'member')

    router.push(auth.homeRoute)
  }

  return { completeSignIn }
}
