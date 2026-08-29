import { describe, test, expect } from 'vitest'
import { resolveGuardTarget, routes } from './index'

function fakeAuth(role) {
  return {
    role,
    isLoggedIn: role !== '',
    homeRoute: { student: '/clubs', leader: '/leader/club', admin: '/admin' }[role] || '/login'
  }
}

describe('router guard', () => {
  test('public routes are always allowed', () => {
    const target = resolveGuardTarget({ role: 'public' }, fakeAuth(''))

    expect(target).toBe(null)
  })

  test('logged out users are sent to login for protected routes', () => {
    const target = resolveGuardTarget({ role: 'student' }, fakeAuth(''))

    expect(target).toBe('/login')
  })

  test('a student visiting a student route is allowed through', () => {
    const target = resolveGuardTarget({ role: 'student' }, fakeAuth('student'))

    expect(target).toBe(null)
  })

  test('a student visiting a leader route is sent to the student home', () => {
    const target = resolveGuardTarget({ role: 'leader' }, fakeAuth('student'))

    expect(target).toBe('/clubs')
  })

  test('a leader visiting an admin route is sent to the leader home', () => {
    const target = resolveGuardTarget({ role: 'admin' }, fakeAuth('leader'))

    expect(target).toBe('/leader/club')
  })

  test('an admin visiting an admin route is allowed through', () => {
    const target = resolveGuardTarget({ role: 'admin' }, fakeAuth('admin'))

    expect(target).toBe(null)
  })

  test('all thirty routes are registered with a role', () => {
    expect(routes.length).toBe(30)
    routes.forEach(function checkRoute(route) {
      expect(route.meta.role).toBeTruthy()
      expect(route.meta.bodyClass).toBeTruthy()
    })
  })
})
