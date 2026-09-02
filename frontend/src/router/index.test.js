import { describe, test, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from './index'
import { useAuthStore } from '../stores/auth'
import { roleMismatchState, dismissRoleMismatch } from '../composables/useRoleMismatch'

// The real guard (router/index.js's checkAccess), not a reimplementation:
// a tier mismatch has to actually stop the navigation now that auth.role is
// JWT-derived, not just warn while letting the admin shell render.

function signIn(auth, role) {
  auth.setToken('t')
  auth.setUser({ name: 'A', email: 'a@b.c', tenantSlug: 'vaikunth-heights', tenantName: 'Vaikunth Heights', initials: 'A' })
  auth.setRole(role)
}

describe('router RBAC guard', () => {
  beforeEach(async () => {
    localStorage.clear()
    setActivePinia(createPinia())
    dismissRoleMismatch()
    await router.push('/')
    await router.isReady()
  })

  test('an unauthenticated visitor hitting a member route is sent to /login', async () => {
    await router.push('/t/vaikunth-heights/dashboard')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  test('an unauthenticated visitor hitting an admin route is also sent to /login, not the tenant dashboard', async () => {
    await router.push('/t/vaikunth-heights/admin')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  test('a member hitting an admin route is redirected to their own dashboard and told why', async () => {
    const auth = useAuthStore()
    signIn(auth, 'member')

    await router.push('/t/vaikunth-heights/admin')

    expect(router.currentRoute.value.path).toBe('/t/vaikunth-heights/dashboard')
    expect(roleMismatchState.visible).toBe(true)
    expect(roleMismatchState.message).toContain('Admin-only')
  })

  test('an admin can reach an admin route', async () => {
    const auth = useAuthStore()
    signIn(auth, 'admin')

    await router.push('/t/vaikunth-heights/admin')
    expect(router.currentRoute.value.path).toBe('/t/vaikunth-heights/admin')
  })

  test('a member can reach a member route with no redirect and no banner', async () => {
    const auth = useAuthStore()
    signIn(auth, 'member')

    await router.push('/t/vaikunth-heights/dashboard')
    expect(router.currentRoute.value.path).toBe('/t/vaikunth-heights/dashboard')
    expect(roleMismatchState.visible).toBe(false)
  })

  test('a public route needs no session at all', async () => {
    await router.push('/methods')
    expect(router.currentRoute.value.path).toBe('/methods')
  })
})
