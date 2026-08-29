import { describe, test, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useEventsStore } from './events'

describe('events store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))
  })

  test('loadEvents fills the events list from the mock fallback', async () => {
    const store = useEventsStore()

    await store.loadEvents()

    expect(store.events.length).toBe(6)
    expect(store.loaded).toBe(true)
  })

  test('upcomingEvents only returns events with upcoming status', async () => {
    const store = useEventsStore()

    await store.loadEvents()

    store.upcomingEvents.forEach(function checkStatus(event) {
      expect(event.status).toBe('upcoming')
    })
    expect(store.upcomingEvents.length).toBe(4)
  })

  test('loadEvent sets the current event by id', async () => {
    const store = useEventsStore()

    await store.loadEvent(2)

    expect(store.currentEvent.title).toBe('Automation Hackathon 2026')
  })
})
