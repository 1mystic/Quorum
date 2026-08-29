import { describe, test, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore, personas } from './auth'

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  test('defaults to the student role when nothing is stored', () => {
    const auth = useAuthStore()

    expect(auth.role).toBe('student')
    expect(auth.user).toEqual(personas.student)
  })

  test('reads a stored leader role from localStorage', () => {
    localStorage.setItem('cc_role', 'leader')

    const auth = useAuthStore()

    expect(auth.role).toBe('leader')
    expect(auth.user.name).toBe('Aayansh Yadav')
  })

  test('setRole switches persona and persists the role', () => {
    const auth = useAuthStore()

    auth.setRole('admin')

    expect(auth.user.initials).toBe('SA')
    expect(localStorage.getItem('cc_role')).toBe('admin')
  })

  test('setRole ignores unknown roles', () => {
    const auth = useAuthStore()

    auth.setRole('hacker')

    expect(auth.role).toBe('student')
  })

  test('homeRoute maps each role to its landing page', () => {
    const auth = useAuthStore()

    auth.setRole('leader')

    expect(auth.homeRoute).toBe('/leader/club')
  })

  test('logout clears role, token and persisted state', () => {
    const auth = useAuthStore()
    auth.setToken('abc')

    auth.logout()

    expect(auth.role).toBe('')
    expect(auth.isLoggedIn).toBe(false)
    expect(localStorage.getItem('cc_role')).toBe(null)
    expect(localStorage.getItem('cc_token')).toBe(null)
  })
})
