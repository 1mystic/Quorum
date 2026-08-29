// Two demo tenants, per docs/VERTICALS.md §1 (rwa_society) and §2 (campus_club).
// Everything downstream (nav, requests, ledger, decisions...) keys off these
// slugs so a real /api/t/{slug}/... swap is a one-line change per view.

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
    ledgerCategories: ['maintenance_dues', 'corpus_fund', 'sinking_fund', 'stp_maintenance', 'lift_amc', 'security_wages', 'housekeeping_wages', 'electricity_common', 'water_tanker', 'festival_fund', 'repairs_capex', 'penalty_late_fee', 'misc'],
    roles: ['president', 'secretary', 'treasurer', 'committee_member', 'resident', 'auditor', 'guest']
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
    ledgerCategories: ['membership_fee', 'college_grant', 'sponsorship', 'ticket_sales', 'event_expense', 'equipment_purchase', 'printing', 'refreshments', 'travel', 'misc'],
    roles: ['faculty_advisor', 'president', 'core_team', 'member', 'alumnus', 'guest']
  }
}

export const demoTenantList = Object.values(tenants)

export function tenantBySlug(slug) {
  return tenants[slug] || demoTenantList[0]
}

export const packMeta = {
  reliability_ops: { id: 'reliability_ops', name: 'Reliability & Service Ops', number: '01', route: 'insights-operations' },
  forecast_risk: { id: 'forecast_risk', name: 'Foresight', number: '03', route: 'insights-forecast' },
  bayes_ranking: { id: 'bayes_ranking', name: 'Comparison', number: '02', route: 'insights-comparison' },
  governance_insight: { id: 'governance_insight', name: 'Voice', number: '04', route: 'insights-governance' }
}
