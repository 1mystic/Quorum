import { defineStore } from 'pinia'
import { getClubs, getMyClubs, getClubById } from "../api/clubs"

export const useClubsStore = defineStore('clubs', {
  state: () => ({
  clubs: [],
  joinedClubs: [],
  currentClub: null,

  leaderClubs: [],
  selectedLeaderClub: null,

  loaded: false
}),

  getters: {
    recommendedClubs: (state) => {
      const joinedIds = new Set(state.joinedClubs.map(club => club.id))

      return state.clubs.filter(club => !joinedIds.has(club.id))
}
  },

  actions: {
  async loadClubs() {
  if (this.loaded) return

  try {
    const clubs = await getClubs()
    this.clubs = Array.isArray(clubs) ? clubs : []
  } catch (error) {
    console.error("Failed to load clubs:", error)
    this.clubs = []
  }

  try {
    const myClubs = await getMyClubs()

    this.joinedClubs = Array.isArray(myClubs)
      ? myClubs.filter(club => club.status !== 'ARCHIVED')
      : []

} catch (error) {
    console.error("Failed to load my clubs:", error)
    this.joinedClubs = []
}

  this.loaded = true
},

  async refreshClubs() {
    this.loaded = false
    await this.loadClubs()
},
  async loadClub(clubId) {
    try {
    this.currentClub = await getClubById(clubId)
  } catch (error) {
    console.error("Failed to load club:", error)
    this.currentClub = null
  }
},
  async loadLeaderClubs() {
    try {
      const clubs = await getMyClubs({ role: 'LEADER' })

      this.leaderClubs = Array.isArray(clubs)
        ? clubs.filter(club => club.status === 'ACTIVE')
        : []

      const stillExists = this.leaderClubs.some(
       club => club.id === this.selectedLeaderClub?.id
      )

      if (!stillExists) {
        this.selectedLeaderClub =
          this.leaderClubs.length
            ? this.leaderClubs[0]
            : null
      }
    } catch (error) {
      console.error("Failed to load leader clubs:", error)
       this.leaderClubs = []
      this.selectedLeaderClub = null
    }
},
  selectLeaderClub(clubId) {
  this.selectedLeaderClub =
    this.leaderClubs.find(c => c.id === clubId) ?? null
}
  }
})
