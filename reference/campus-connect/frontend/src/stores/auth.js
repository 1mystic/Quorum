import { defineStore } from 'pinia'
import { useClubsStore } from './clubs'
import { useEventsStore } from './events'
import { invalidateCache } from '../utils/apiCache'

const defaultUser = {
  name: "",
  email: "",
  collegeSlug: "",
  collegeName: "",
  initials: ""
}

function readStoredRole() {
  // Only two account types log in now: a member (student) or an institute admin.
  // Club leadership is a capability layered on a member account, not a login role.
  const stored = localStorage.getItem('cc_role')
  if (stored === 'admin') {
    return stored
  }
  return 'student'
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
  role: readStoredRole(),
  token: localStorage.getItem("cc_token") || "",
  user: JSON.parse(localStorage.getItem("cc_user")) || defaultUser,
  isClubLeader:
    JSON.parse(localStorage.getItem("cc_isClubLeader")) || false
}),

  getters: {
    isLoggedIn: (state) => !!state.token,
    homeRoute: (state) => {
      const slug = state.user.collegeSlug

      if (!slug) {
        return '/'
      }

      if (state.role === 'admin') {
        return `/${slug}/admin`
      }

      return `/${slug}/clubs`
},
    // A member who leads a club may open the club-leader tools.
    canManageClubs: (state) => state.role === 'student' && state.isClubLeader
  },

  actions: {
    setRole(role) {
    this.role = role
    localStorage.setItem("cc_role", role)
},

    setToken(token) {
      this.token = token
      localStorage.setItem('cc_token', token)
    },

    setUser(user) {
      this.user = user
      localStorage.setItem("cc_user", JSON.stringify(user))
    },

    setClubLeader(value) {
      this.isClubLeader = value
      localStorage.setItem(
      "cc_isClubLeader",
      JSON.stringify(value)
    )
    },

    logout() {
      this.role = "student"
      this.token = ""
      this.user = { ...defaultUser }
      this.isClubLeader = false

      localStorage.removeItem("cc_role")
      localStorage.removeItem("cc_token")
      localStorage.removeItem("cc_user")
      localStorage.removeItem("cc_isClubLeader")
      localStorage.removeItem("cc_remember")

      // The AI Finder's conversation is per-student context (interests,
      // already-joined clubs it referenced) that has no business surviving
      // into the next person who signs in on this device/tab.
      sessionStorage.removeItem("cc_finder_conversation")

      // Clubs and events cache themselves with a "loaded" flag that only
      // resets on a hard page reload, so switching accounts in the same tab
      // left the next student looking at the previous account's list - or a
      // failed unauthenticated fetch's empty one. Clearing both here is what
      // makes "loaded" mean "loaded for the current session" rather than
      // "loaded once, ever."
      useClubsStore().$reset()
      useEventsStore().$reset()
      invalidateCache()
    }
  }
})

export { defaultUser }
