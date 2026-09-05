import { defineStore } from 'pinia'
import { getTenant } from '../api/tenant'
import { configForVertical, packMeta } from '../fixtures/tenants'

// The real per-tenant identity cache: GET /api/t/{slug}/tenant, fetched
// once per slug and kept until a forced refetch (TenantSettingsView after a
// pack toggle, say). This is the fix for fixtures/tenants.js's tenantBySlug
// returning a hardcoded two-entry object for every real tenant a user signs
// up into or onboards - see useTenant.js for the composable views actually
// call.

const VERTICAL_LABEL = {
  rwa_society: 'Housing society',
  campus_club: 'Campus club',
  housing_coop: 'Housing co-op',
  ngo_volunteer: 'NGO volunteer group',
  alumni_chapter: 'Alumni chapter',
  sports_club: 'Sports club',
  professional_guild: 'Professional guild'
}

// A small fixed palette drawn from design/tokens.css's --brand/--s1..--s6 -
// never a hex here, and never random per render: the same slug always
// lands on the same color.
const DOT_PALETTE = ['var(--brand)', 'var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)']

function initialsFor(name) {
  const words = (name || '').trim().split(/\s+/).filter(Boolean)
  if (!words.length) return '??'
  return words.slice(0, 2).map((w) => w[0].toUpperCase()).join('')
}

function colorFor(slug) {
  let hash = 0
  for (let i = 0; i < slug.length; i += 1) {
    hash = (hash * 31 + slug.charCodeAt(i)) >>> 0
  }
  return DOT_PALETTE[hash % DOT_PALETTE.length]
}

// The real endpoint has no `optional_packs` field - it only says what is
// on. "Optional" here means every known pack this tenant has not enabled,
// which is exactly what the old fixture's two hand-written arrays summed
// to (enabled + optional always covered all four packs).
function optionalPacksFor(enabledPacks) {
  return Object.keys(packMeta).filter((id) => !enabledPacks.includes(id))
}

// Turns the API's minimal contract (name, slug, vertical, description,
// enabled_packs, timezone) into the full shape every view already reads:
// vertical vocabulary from the static config, plus cosmetic per-instance
// bits derived deterministically rather than invented.
function enrich(raw) {
  const vertical = raw.vertical
  const verticalLabel = VERTICAL_LABEL[vertical] || vertical
  const enabledPacks = raw.enabled_packs || []
  return {
    ...raw,
    enabled_packs: enabledPacks,
    optional_packs: optionalPacksFor(enabledPacks),
    dot: initialsFor(raw.name),
    dotColor: colorFor(raw.slug),
    tagline: raw.description ? `${verticalLabel} · ${raw.description}` : verticalLabel,
    currency: raw.currency || 'INR',
    ...configForVertical(vertical)
  }
}

export const useTenantStore = defineStore('tenant', {
  state: () => ({
    bySlug: {},
    // At most one fetch is ever "in flight" for the UI's purposes - the
    // slug currently loading, or '' when idle.
    loadingSlug: '',
    errorSlug: '',
    errorMessage: '',
    // A view and the TenantShell it renders both call useTenant() with the
    // same slug on the same mount - this dedupes the two into one real
    // request rather than firing GET /tenant twice for one page load.
    _pending: {}
  }),

  actions: {
    fetchTenant(slug, { force = false } = {}) {
      if (!slug) return Promise.resolve(null)
      if (!force && this.bySlug[slug]) return Promise.resolve(this.bySlug[slug])
      if (!force && this._pending[slug]) return this._pending[slug]

      this.loadingSlug = slug
      if (this.errorSlug === slug) {
        this.errorSlug = ''
        this.errorMessage = ''
      }

      const promise = getTenant(slug)
        .then((raw) => {
          const enriched = enrich(raw)
          this.bySlug = { ...this.bySlug, [slug]: enriched }
          return enriched
        })
        .catch((err) => {
          this.errorSlug = slug
          this.errorMessage = (err && err.message) || 'Could not load this tenant.'
          return null
        })
        .finally(() => {
          if (this.loadingSlug === slug) this.loadingSlug = ''
          delete this._pending[slug]
        })

      this._pending[slug] = promise
      return promise
    }
  }
})
