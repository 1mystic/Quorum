import { defineStore } from 'pinia'

// Quorum is multi-tenant: a session belongs to a role inside a tenant
// (identified by its slug), not to a college.
//
// `role` is the coarse tier ('member' | 'admin') that route.meta.role is
// checked against, set for real from the JWT's MEMBER/TENANT_ADMIN claim on
// login (useAuthSession.completeSignIn). `demoRole` is the finer vertical
// role (e.g. 'treasurer', 'core_team', see docs/VERTICALS.md) shown in the
// role switcher, for label/copy purposes only - it can narrow which label
// is shown within a tier but does not grant access the JWT-derived tier
// does not already have; router.beforeEach's real gate is the backend.

const defaultUser = {
  name: '',
  email: '',
  tenantSlug: '',
  tenantName: '',
  initials: ''
}

function readStoredRole() {
  const stored = localStorage.getItem('qm_role')
  if (stored === 'admin') {
    return stored
  }
  return 'member'
}

function readStoredDemoRole() {
  return localStorage.getItem('qm_demo_role') || ''
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    role: readStoredRole(),
    demoRole: readStoredDemoRole(),
    token: localStorage.getItem('qm_token') || '',
    user: JSON.parse(localStorage.getItem('qm_user')) || defaultUser
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    homeRoute: (state) => {
      const slug = state.user.tenantSlug

      if (!slug) {
        return '/'
      }

      if (state.role === 'admin') {
        return `/t/${slug}/admin`
      }

      return `/t/${slug}/dashboard`
    }
  },

  actions: {
    setRole(role) {
      this.role = role
      localStorage.setItem('qm_role', role)
    },

    // Label preference only - never touches `role`. `role` comes from the
    // JWT and is the real access tier; letting a vertical role label like
    // "President" or "Resident" overwrite it would desync the UI from what
    // the backend actually grants, so this only picks which role name
    // within that tier is displayed.
    setDemoRole(roleId) {
      this.demoRole = roleId
      localStorage.setItem('qm_demo_role', roleId)
    },

    setToken(token) {
      this.token = token
      localStorage.setItem('qm_token', token)
    },

    setUser(user) {
      this.user = user
      localStorage.setItem('qm_user', JSON.stringify(user))
    },

    logout() {
      this.role = 'member'
      this.demoRole = ''
      this.token = ''
      this.user = { ...defaultUser }
      localStorage.removeItem('qm_role')
      localStorage.removeItem('qm_demo_role')
      localStorage.removeItem('qm_token')
      localStorage.removeItem('qm_user')
    },

    $reset() {
      this.logout()
    }
  }
})
