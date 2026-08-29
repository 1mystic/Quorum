import { describe, test, expect, vi, beforeEach } from 'vitest'
import { getLeaderboard } from './leaderboard'

describe('leaderboard api', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  test('returns the ranked list from the server', async () => {
    const serverEntries = [
      { rank: 1, club_id: 1, name: 'Robotics & Automation', category: 'Tech', score: 1240 },
      { rank: 2, club_id: 2, name: 'Coding Society', category: 'Tech', score: 1090 }
    ]
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => serverEntries })

    const result = await getLeaderboard()

    expect(result).toEqual(serverEntries)
  })

  test('throws with the server message when the request fails', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Not authenticated' })
    })

    await expect(getLeaderboard()).rejects.toThrow('Not authenticated')
  })

  test('attaches the bearer token when the student is signed in', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] })
    localStorage.setItem('cc_token', 'test-token')

    await getLeaderboard()

    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer test-token')
  })
})
