import { describe, test, expect, vi, beforeEach } from 'vitest'
import { loginUser, signupUser, verifyEmailOtp, resendOtp, sendResetLink, saveOnboarding } from './auth'

describe('auth api', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  test('loginUser posts credentials and returns the server response', async () => {
    const fakeResponse = { ok: true, token: 'abc', role: 'student' }
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(fakeResponse) })

    const result = await loginUser('shikha@knit.ac.in', 'secret123')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/login'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(result).toEqual(fakeResponse)
  })

  test('loginUser falls back to mock data when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await loginUser('shikha@knit.ac.in', 'secret123')

    expect(result.ok).toBe(true)
    expect(result.token).toBe('mock-token')
  })

  test('signupUser falls back to mock data when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await signupUser('Shikha Singh', 'shikha@knit.ac.in', 'secret123', 'student')

    expect(result.ok).toBe(true)
    expect(result.email).toBe('shikha@knit.ac.in')
  })

  test('verifyEmailOtp falls back to verified when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await verifyEmailOtp('shikha@knit.ac.in', '123456')

    expect(result.verified).toBe(true)
  })

  test('resendOtp falls back to sent when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await resendOtp('shikha@knit.ac.in')

    expect(result.sent).toBe(true)
  })

  test('sendResetLink falls back to sent when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await sendResetLink('shikha@knit.ac.in')

    expect(result.sent).toBe(true)
  })

  test('saveOnboarding falls back to saved when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('no server'))

    const result = await saveOnboarding({ dept: 'cs', year: '1', interests: ['coding'], goal: 'discover' })

    expect(result.saved).toBe(true)
  })
})
