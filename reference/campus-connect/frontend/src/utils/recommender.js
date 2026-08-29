// Deterministic club/event matching for the AI Club Finder.
// This is the frontend mock of the backend recommender core described in
// the design doc (backend/services/recommender.py). The LLM never decides
// which clubs exist here - it only ever gets to phrase reasons on top of
// this ranking once the real backend is wired in.

const TOKEN_RE = /[a-z0-9]+/g

const STOP_WORDS = new Set([
  'the', 'and', 'for', 'with', 'this', 'that', 'club', 'clubs', 'like',
  'love', 'want', 'interested', 'interest', 'hobby', 'hobbies', 'join',
  'campus', 'college', 'student', 'students', 'really', 'very'
])

const DEFAULT_CONFIG = {
  clubThreshold: 0.3,
  eventThreshold: 0.2,
  topK: 3
}

export function normalizeTokens(text) {
  if (!text) return new Set()
  const rawTokens = text.toLowerCase().match(TOKEN_RE) || []
  const cleanTokens = rawTokens.filter(function keepToken(token) {
    return !STOP_WORDS.has(token) && token.length > 2
  })
  return new Set(cleanTokens)
}

function itemTokens(...texts) {
  const joined = texts.filter(Boolean).join(' ')
  return normalizeTokens(joined)
}

function overlapFraction(interestTokens, itemTokenSet) {
  if (interestTokens.size === 0 || itemTokenSet.size === 0) return 0

  let hits = 0
  interestTokens.forEach(function countHit(token) {
    if (itemTokenSet.has(token)) hits += 1
  })

  return hits / interestTokens.size
}

function roundScore(score) {
  return Math.round(Math.min(score, 1) * 10000) / 10000
}

export function scoreClub(interestTokens, club, maxMembers) {
  const text = itemTokens(club.name, club.category, club.description, (club.tags || []).join(' '))
  const interestOverlap = overlapFraction(interestTokens, text)
  const popularity = maxMembers ? (club.members || 0) / maxMembers : 0
  const score = 0.75 * interestOverlap + 0.25 * popularity
  return roundScore(score)
}

export function scoreEvent(interestTokens, event) {
  const text = itemTokens(event.title, event.club)
  return roundScore(overlapFraction(interestTokens, text))
}

export function explainClubMatch(interestTokens, club) {
  const text = itemTokens(club.name, club.category, club.description, (club.tags || []).join(' '))
  const sharedTokens = []

  interestTokens.forEach(function collectShared(token) {
    if (text.has(token)) sharedTokens.push(token)
  })

  if (sharedTokens.length > 0) {
    return 'Matched because you mentioned ' + sharedTokens.slice(0, 3).join(', ') + '.'
  }

  return 'One of the most active ' + club.category.toLowerCase() + ' clubs on campus.'
}

export function selectRecommendations(interestText, clubs, events, cfg = DEFAULT_CONFIG) {
  const interestTokens = normalizeTokens(interestText)

  const maxMembers = clubs.reduce(function trackMax(max, club) {
    return Math.max(max, club.members || 0)
  }, 0)

  const scoredClubs = clubs
    .map(function attachClubScore(club) {
      return { ...club, matchScore: scoreClub(interestTokens, club, maxMembers) }
    })
    .sort(function byScoreThenMembers(a, b) {
      return b.matchScore - a.matchScore || (b.members || 0) - (a.members || 0)
    })

  const matchedClubs = scoredClubs.filter(function aboveThreshold(club) {
    return club.matchScore >= cfg.clubThreshold
  })

  if (matchedClubs.length > 0) {
    const topClubs = matchedClubs.slice(0, cfg.topK).map(function attachReason(club) {
      return { ...club, reason: explainClubMatch(interestTokens, club) }
    })
    return {
      kind: 'clubs',
      items: topClubs,
      message: 'Here are the clubs that best match what you described.'
    }
  }

  const upcomingEvents = events.filter(function notPast(event) {
    return event.status !== 'past'
  })

  const scoredEvents = upcomingEvents
    .map(function attachEventScore(event) {
      return { ...event, matchScore: scoreEvent(interestTokens, event) }
    })
    .sort(function byEventScore(a, b) {
      return b.matchScore - a.matchScore
    })

  const matchedEvents = scoredEvents.filter(function aboveEventThreshold(event) {
    return event.matchScore >= cfg.eventThreshold
  })

  if (matchedEvents.length > 0) {
    const bestEvent = matchedEvents[0]
    const topEvents = matchedEvents.slice(0, 3).map(function attachEventReason(matchedEvent) {
      return { ...matchedEvent, reason: 'Hosted by ' + matchedEvent.club + ' — closest match to what you described.' }
    })
    return {
      kind: 'event_fallback',
      items: topEvents,
      message: 'I could not find a club that matches yet, but "' + bestEvent.title +
        '" hosted by ' + bestEvent.club + ' covers something similar. ' +
        'You can reach out through the platform if you want to know more.'
    }
  }

  const popularClubs = [...clubs]
    .sort(function byMembers(a, b) {
      return (b.members || 0) - (a.members || 0)
    })
    .slice(0, cfg.topK)
    .map(function attachPopularReason(club, index) {
      return { ...club, reason: 'Ranked #' + (index + 1) + ' by member activity on campus.' }
    })

  return {
    kind: 'popularity',
    items: popularClubs,
    message: 'Nothing matched your exact interests yet, so here are the most active clubs on campus.'
  }
}

export { DEFAULT_CONFIG }
