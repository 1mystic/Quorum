import { describe, test, expect } from 'vitest'
import {
  normalizeTokens,
  scoreClub,
  scoreEvent,
  selectRecommendations
} from './recommender'

function club(overrides) {
  return {
    id: 1,
    name: 'Robotics Club',
    category: 'Technology',
    description: 'We build robots and drones',
    members: 100,
    tags: ['Robotics', 'IoT'],
    ...overrides
  }
}

function event(overrides) {
  return {
    id: 1,
    title: 'Astro Night',
    club: 'Astronomy Club',
    status: 'upcoming',
    ...overrides
  }
}

describe('normalizeTokens', () => {
  test('drops stopwords and short tokens', () => {
    const tokens = normalizeTokens('I want to join a club for robotics')
    expect(tokens).toEqual(new Set(['robotics']))
  })

  test('returns an empty set for blank text', () => {
    expect(normalizeTokens('').size).toBe(0)
    expect(normalizeTokens(undefined).size).toBe(0)
  })
})

describe('scoreClub', () => {
  test('scores an exact interest match highly', () => {
    const tokens = normalizeTokens('robotics and drones')
    const score = scoreClub(tokens, club({}), 100)
    expect(score).toBeGreaterThanOrEqual(0.5)
  })

  test('scores below threshold when nothing overlaps', () => {
    const tokens = normalizeTokens('poetry and painting')
    const score = scoreClub(tokens, club({}), 100)
    expect(score).toBeLessThan(0.3)
  })

  test('is deterministic for the same inputs', () => {
    const tokens = normalizeTokens('robotics')
    expect(scoreClub(tokens, club({}), 100)).toBe(scoreClub(tokens, club({}), 100))
  })

  test('stays within 0 and 1', () => {
    const tokens = normalizeTokens('robotics drones iot technology build')
    const score = scoreClub(tokens, club({}), 100)
    expect(score).toBeGreaterThanOrEqual(0)
    expect(score).toBeLessThanOrEqual(1)
  })

  test('breaks ties in favour of higher member counts', () => {
    const tokens = normalizeTokens('astronomy stars')
    const a = club({ id: 10, category: 'Science', description: 'astronomy stars', members: 90 })
    const b = club({ id: 11, category: 'Science', description: 'astronomy stars', members: 5 })
    expect(scoreClub(tokens, a, 90)).toBeGreaterThan(scoreClub(tokens, b, 90))
  })
})

describe('scoreEvent', () => {
  test('matches on title and hosting club name', () => {
    const tokens = normalizeTokens('astronomy stars')
    const score = scoreEvent(tokens, event({ title: 'Astronomy Stargazing Night' }))
    expect(score).toBeGreaterThan(0)
  })
})

describe('selectRecommendations', () => {
  const robotics = club({ id: 1, members: 100 })
  const poetry = club({
    id: 2,
    name: 'Poetry Society',
    category: 'Literature',
    description: 'Weekly poetry readings',
    members: 10,
    tags: []
  })

  test('returns matched clubs first when interests overlap', () => {
    const result = selectRecommendations('robotics and drones', [robotics, poetry], [])
    expect(result.kind).toBe('clubs')
    expect(result.items[0].id).toBe(1)
    expect(result.items[0].reason).toBeTruthy()
  })

  test('falls back to a public upcoming event when no club matches', () => {
    const astroEvent = event({ title: 'Astronomy Stargazing Night', club: 'Astronomy Club' })
    const result = selectRecommendations('astronomy stargazing', [poetry], [astroEvent])
    expect(result.kind).toBe('event_fallback')
    expect(result.message).toContain('Astronomy Stargazing Night')
  })

  test('ignores past events in the fallback', () => {
    const pastEvent = event({ title: 'Astronomy Stargazing Night', status: 'past' })
    const result = selectRecommendations('astronomy stargazing', [poetry], [pastEvent])
    expect(result.kind).toBe('popularity')
  })

  test('falls back to popularity when nothing matches at all', () => {
    const result = selectRecommendations('knitting', [robotics, poetry], [])
    expect(result.kind).toBe('popularity')
    expect(result.items[0].id).toBe(1)
    expect(result.items[0].reason).toContain('Ranked #1')
  })
})
