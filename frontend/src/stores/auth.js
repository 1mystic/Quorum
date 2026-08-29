import { defineStore } from 'pinia'

// Quorum is multi-tenant: a session belongs to a role inside a tenant
// (identified by its slug), not to a college. Mirrors campus-connect's
// auth store shape but renamed per docs/GLOSSARY.md (College -> Tenant).

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

export const useAuthStore = defineStore('auth', {
  state: () => ({
    role: readStoredRole(),
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
      this.token = ''
      this.user = { ...defaultUser }
      localStorage.removeItem('qm_role')
      localStorage.removeItem('qm_token')
      localStorage.removeItem('qm_user')
    },

    $reset() {
      this.logout()
    }
  }
})
