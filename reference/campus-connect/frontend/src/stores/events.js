import { defineStore } from 'pinia'
import { getEvents, getEventById, getMyRegistrations, normalizeEvent } from '../api/events'

export const useEventsStore = defineStore('events', {
  state: () => ({
    events: [],
    currentEvent: null,
    myRegistrations: [],
    loaded: false,
    loading: false,
    error: ''
  }),

  getters: {
    upcomingEvents: (state) => state.events.filter((event) => event.status === 'upcoming'),
    registeredEventIds: (state) => new Set(state.myRegistrations.map((item) => item.event_id))
  },

  actions: {
    async loadEvent(eventId) {
  this.loading = true
  this.error = ''

  try {
    this.currentEvent = normalizeEvent(
      await getEventById(eventId)
    )
  } catch (error) {
    console.error('Failed to load event:', error)
    this.error = error?.message || 'Something went wrong.'
    this.currentEvent = null
  } finally {
    this.loading = false
  }

  return this.currentEvent
},

    async loadMyRegistrations() {
      try {
        const registrations = await getMyRegistrations()
        this.myRegistrations = Array.isArray(registrations) ? registrations : []
      } catch (error) {
        console.error('Failed to load my registrations:', error)
        this.myRegistrations = []
      }

      return this.myRegistrations
    },

    async refreshEvents() {
      await this.loadEvents(true)
    },

    async loadEvents(force = false) {
  if (this.loaded && !force) return

  this.loading = true
  this.error = ''

  await this.loadMyRegistrations()

  try {
    const events = await getEvents()

    this.events = events.map(event =>
      normalizeEvent(event, this.registeredEventIds)
    )

    this.loaded = true
  } catch (error) {
    console.error('Failed to load events:', error)
    this.error = error?.message || 'Something went wrong.'
    this.events = []
  } finally {
    this.loading = false
  }
}
  }
})

