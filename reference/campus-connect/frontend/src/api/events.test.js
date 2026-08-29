import { describe, test, expect, vi, beforeEach } from 'vitest'
import { getEvents, getEventById, registerForEvent, payForEvent } from './events'

describe('events api', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  test('getEvents falls back to the 6 mock events when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await getEvents()

    expect(result.length).toBe(6)
  })

  test('getEventById finds the matching mock event when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await getEventById('3')

    expect(result.title).toBe('Open Mic Night')
  })

  test('registerForEvent falls back to a registration id when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await registerForEvent(2)

    expect(result.registrationId).toBe('CC-2026-0482')
  })

  test('payForEvent resolves immediately with a simulated status', async () => {
    const result = await payForEvent(2, 100)

    expect(result.ok).toBe(true)
    expect(result.paymentStatus).toBe('simulated')
  })
})
