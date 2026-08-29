import { useRouter } from 'vue-router'
import { jwtDecode } from 'jwt-decode'
import { useAuthStore } from '../stores/auth'

// Completes a sign-in: decodes the JWT, seeds the auth store and routes the
// session to its tenant home. Kept deliberately thin until the API exists -
// the backend agent owns the token shape (docs/EVIDENCE_CONTRACT.md and the
// tenant routing rule in docs/RULES.md section 5: routes are /api/t/{slug}/... and the
// slug must match the JWT claim).

export function useAuthSession() {
  const router = useRouter()
  const auth = useAuthStore()

  async function completeSignIn(result) {
    auth.setToken(result.access_token)

    const payload = jwtDecode(result.access_token)
    const role = (payload.role || '').toLowerCase()

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

    auth.setRole(role === 'admin' ? 'admin' : 'member')

    router.push(auth.homeRoute)
  }

  return { completeSignIn }
}
