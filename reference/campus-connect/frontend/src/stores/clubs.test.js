import { describe, test, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useClubsStore } from './clubs'

describe('clubs store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))
  })

  test('loadClubs fills clubs and joined clubs from the mock fallback', async () => {
    const store = useClubsStore()

    await store.loadClubs()

    expect(store.clubs.length).toBe(9)
    expect(store.joinedClubs.length).toBe(4)
    expect(store.loaded).toBe(true)
  })

  test('recommendedClubs only returns clubs flagged as recommended', async () => {
    const store = useClubsStore()

    await store.loadClubs()

    expect(store.recommendedClubs.length).toBe(3)
    store.recommendedClubs.forEach(function checkFlag(club) {
      expect(club.recommended).toBe(true)
    })
  })

  test('loadClub sets the current club by id', async () => {
    const store = useClubsStore()

    await store.loadClub(3)

    expect(store.currentClub.name).toBe('Coding Society')
  })

  test('loadClubs does not refetch once loaded', async () => {
    const store = useClubsStore()

    await store.loadClubs()
    const callsAfterFirstLoad = global.fetch.mock.calls.length
    await store.loadClubs()

    expect(global.fetch.mock.calls.length).toBe(callsAfterFirstLoad)
  })
})
