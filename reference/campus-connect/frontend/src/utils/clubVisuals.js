/**
 * Colour and icon for a club, worked out from the club itself.
 *
 * The API returns no colour or icon field, so anything showing a club has to
 * derive them. Keeping that here means a club looks the same everywhere it
 * appears - discovery cards, the AI finder, the proposal list - instead of
 * each view inventing its own mapping.
 */

const BANNER_COLOURS = [
  'banner-orange',
  'banner-green',
  'banner-blue',
  'banner-yellow',
  'banner-pink',
  'banner-mint'
]

// Categories the backend actually uses. Anything unrecognised falls through
// to the name-based lookup below, so a new category is never blank.
const CATEGORY_STYLES = {
  technology: { colour: 'banner-blue', icon: 'laptop' },
  tech: { colour: 'banner-blue', icon: 'laptop' },
  culture: { colour: 'banner-pink', icon: 'music' },
  cultural: { colour: 'banner-pink', icon: 'music' },
  arts: { colour: 'banner-yellow', icon: 'palette' },
  art: { colour: 'banner-yellow', icon: 'palette' },
  business: { colour: 'banner-mint', icon: 'briefcase' },
  sports: { colour: 'banner-green', icon: 'sports' },
  sport: { colour: 'banner-green', icon: 'sports' },
  academic: { colour: 'banner-blue', icon: 'school' },
  academics: { colour: 'banner-blue', icon: 'school' },
  social: { colour: 'banner-orange', icon: 'megaphone' },
  literature: { colour: 'banner-yellow', icon: 'book' },
  literary: { colour: 'banner-yellow', icon: 'book' },
  science: { colour: 'banner-green', icon: 'microscope' },
  music: { colour: 'banner-pink', icon: 'music' },
  photography: { colour: 'banner-yellow', icon: 'camera' }
}

// Checked against the club name when the category is unfamiliar. Most
// specific first, since the first hit wins.
const NAME_KEYWORDS = [
  { match: 'robot', icon: 'robot' },
  { match: 'photo', icon: 'camera' },
  { match: 'camera', icon: 'camera' },
  { match: 'cod', icon: 'laptop' },
  { match: 'program', icon: 'laptop' },
  { match: 'software', icon: 'laptop' },
  { match: 'tech', icon: 'laptop' },
  { match: 'music', icon: 'music' },
  { match: 'band', icon: 'music' },
  { match: 'drama', icon: 'drama' },
  { match: 'theatre', icon: 'drama' },
  { match: 'theater', icon: 'drama' },
  { match: 'debate', icon: 'megaphone' },
  { match: 'literary', icon: 'book' },
  { match: 'book', icon: 'book' },
  { match: 'entrepreneur', icon: 'briefcase' },
  { match: 'business', icon: 'briefcase' },
  { match: 'startup', icon: 'briefcase' },
  { match: 'astro', icon: 'telescope' },
  { match: 'space', icon: 'telescope' },
  { match: 'science', icon: 'microscope' },
  { match: 'art', icon: 'palette' },
  { match: 'design', icon: 'palette' },
  { match: 'chess', icon: 'chess' },
  { match: 'dance', icon: 'dance' },
  { match: 'sport', icon: 'sports' },
  { match: 'athletic', icon: 'sports' }
]

function normalise(value) {
  return String(value || '').trim().toLowerCase()
}

// Small stable hash of the name, so the same club always gets the same
// colour across reloads and across every list it appears in.
function hashName(name) {
  let total = 0

  for (const character of normalise(name)) {
    total = total + character.charCodeAt(0)
  }

  return total
}

function findCategoryStyle(category) {
  return CATEGORY_STYLES[normalise(category)] || null
}

function findKeywordIcon(name) {
  const haystack = normalise(name)

  for (const entry of NAME_KEYWORDS) {
    if (haystack.includes(entry.match)) {
      return entry.icon
    }
  }

  return ''
}

export function bannerColourFor(club) {
  const fromCategory = findCategoryStyle(club?.category)

  if (fromCategory) {
    return fromCategory.colour
  }

  return BANNER_COLOURS[hashName(club?.name) % BANNER_COLOURS.length]
}

export function iconNameFor(club) {
  // The club's own name is the most specific signal, so it is checked first.
  const fromName = findKeywordIcon(club?.name)

  if (fromName) {
    return fromName
  }

  const fromCategory = findCategoryStyle(club?.category)

  if (fromCategory) {
    return fromCategory.icon
  }

  return 'school'
}

/**
 * Shape a raw ClubListItem/MyClubItem from the API into what ApprovalCard.vue
 * renders: a lower-case status (the API sends PENDING/ACTIVE/REJECTED, the
 * card template checks against 'pending'/'approved'/'rejected'), a derived
 * banner/icon, and the application document link pulled out of the club's
 * links array.
 *
 * Both admin approval screens need this exact shape, so it lives here once
 * rather than being reimplemented per view - which is how the dashboard card
 * ended up missing its buttons while the approvals page had them.
 */
const STATUS_MAP = { PENDING: 'pending', ACTIVE: 'approved', REJECTED: 'rejected' }

function formatSubmittedDate(value) {
  if (!value) return 'recently'

  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

export function toApprovalCard(club) {
  const applicationLink = (club.links || []).find(
    (link) => link.label === 'Application Document'
  ) || (club.links || [])[0]

  return {
    ...club,
    status: STATUS_MAP[club.status] || String(club.status || '').toLowerCase(),
    banner: bannerColourFor(club),
    icon: iconNameFor(club),
    applicationLink: applicationLink ? applicationLink.url : null,
    meta: `${club.category} · ${club.member_count} members`,
    // The approvals page (not the dashboard summary) shows this longer form -
    // it was referenced there as metaField="metaFull" but nothing ever set
    // it, so that line rendered blank.
    metaFull: `${club.category} · ${club.member_count} members · Submitted ${formatSubmittedDate(club.created_at)}`
  }
}
