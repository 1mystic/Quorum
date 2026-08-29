import { describe, test, expect, vi, beforeEach } from 'vitest'
import { getClubs, getClubById, requestToJoinClub } from './clubs'

describe('clubs api', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  test('getClubs returns the server response when fetch works', async () => {
    const serverClubs = [{ id: 99, name: 'Server Club' }]
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(serverClubs) })

    const result = await getClubs()

    expect(result).toEqual(serverClubs)
  })

  test('getClubs falls back to the 9 mock clubs when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await getClubs()

    expect(result.length).toBe(9)
  })

  test('getClubById finds the matching mock club when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await getClubById('6')

    expect(result.name).toBe('Entrepreneurship Cell')
  })

  test('requestToJoinClub falls back to a pending status when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await requestToJoinClub(1)

    expect(result.status).toBe('pending')
  })
})
