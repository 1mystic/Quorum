// Two demo tenants, per docs/VERTICALS.md §1 (rwa_society) and §2
// (campus_club), for the public marketing pages only (LandingHero,
// LandingFooter, LandingCta, VerticalsView - see each file's own comment).
// A real tenant-scoped session never reads this object: stores/tenant.js
// fetches GET /api/t/{slug}/tenant for that, see useTenant.js.
//
// `verticalConfig` below is the genuinely-static per-vertical vocabulary
// (labels/categories/priorities) that mirrors backend/app/verticals/
// manifests/*.json - it is not per-tenant instance data, so it stays local
// config keyed by the vertical string the real fetch returns, rather than
// a second API call. The demo tenants below draw from the same map so
// there is exactly one copy of each vertical's vocabulary.

export const verticalConfig = {
  rwa_society: {
    labels: {
      request: 'Complaint',
      member: 'Resident',
      group: 'Committee',
      decision: 'Resolution',
      ledger: 'Society accounts',
      participation: 'Involvement'
    },
    requestCategories: ['water_supply', 'sewage_stp', 'electrical', 'lift', 'security', 'housekeeping', 'parking', 'common_area', 'pest_control', 'noise_nuisance', 'builder_defect', 'other'],
    requestPriorities: ['routine', 'urgent', 'safety'],
    ledgerCategories: ['maintenance_dues', 'corpus_fund', 'sinking_fund', 'stp_maintenance', 'lift_amc', 'security_wages', 'housekeeping_wages', 'electricity_common', 'water_tanker', 'festival_fund', 'repairs_capex', 'penalty_late_fee', 'misc']
  },
  campus_club: {
    labels: {
      request: 'Issue',
      member: 'Member',
      group: 'Club',
      decision: 'Vote',
      ledger: 'Club funds',
      participation: 'Activity'
    },
    requestCategories: ['venue_booking', 'equipment', 'funding_request', 'permissions', 'event_logistics', 'membership_query', 'grievance', 'other'],
    requestPriorities: ['low', 'normal', 'deadline_bound'],
    ledgerCategories: ['membership_fee', 'college_grant', 'sponsorship', 'ticket_sales', 'event_expense', 'equipment_purchase', 'printing', 'refreshments', 'travel', 'misc']
  }
}

// housing_coop, ngo_volunteer, alumni_chapter, sports_club and
// professional_guild have no real backend adapter yet (docs/VERTICALS.md) -
// an admin who picked one of those at onboarding gets this generic
// vocabulary rather than a second wave of undefined crashes.
const fallbackVerticalConfig = {
  labels: {
    request: 'Request',
    member: 'Member',
    group: 'Group',
    decision: 'Decision',
    ledger: 'Ledger',
    participation: 'Participation'
  },
  requestCategories: ['general', 'other'],
  requestPriorities: ['low', 'normal', 'high'],
  ledgerCategories: ['dues', 'other']
}

export function configForVertical(vertical) {
  return verticalConfig[vertical] || fallbackVerticalConfig
}

export const tenants = {
  'vaikunth-heights': {
    slug: 'vaikunth-heights',
    name: 'Vaikunth Heights',
    vertical: 'rwa_society',
    tagline: 'housing society · 214 flats',
    dot: 'VH',
    dotColor: 'var(--brand)',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    enabled_packs: ['reliability_ops', 'forecast_risk'],
    optional_packs: ['governance_insight', 'bayes_ranking'],
    ...configForVertical('rwa_society')
  },
  'aavartan-robotics': {
    slug: 'aavartan-robotics',
    name: 'Aavartan Robotics',
    vertical: 'campus_club',
    tagline: 'campus club · 96 members',
    dot: 'AR',
    dotColor: 'var(--s3)',
    currency: 'INR',
    timezone: 'Asia/Kolkata',
    enabled_packs: ['reliability_ops', 'governance_insight'],
    optional_packs: ['forecast_risk', 'bayes_ranking'],
    ...configForVertical('campus_club')
  }
}

export const demoTenantList = Object.values(tenants)

// Demo-fixture lookup, for the marketing pages named above only. Real
// tenant-scoped views must use stores/tenant.js's useTenant() instead - see
// that file's comment for why (this always resolves to a demo tenant, even
// for a slug that does not exist, which is a real crash for anything real).
export function tenantBySlug(slug) {
  return tenants[slug] || demoTenantList[0]
}

export const packMeta = {
  reliability_ops: { id: 'reliability_ops', name: 'Reliability & Service Ops', number: '01', route: 'insights-operations' },
  forecast_risk: { id: 'forecast_risk', name: 'Foresight', number: '03', route: 'insights-forecast' },
  bayes_ranking: { id: 'bayes_ranking', name: 'Comparison', number: '02', route: 'insights-comparison' },
  governance_insight: { id: 'governance_insight', name: 'Voice', number: '04', route: 'insights-governance' }
}
