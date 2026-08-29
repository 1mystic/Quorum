// Sidebar nav groups, built per tenant so every page is actually reachable
// (not just routed), matching design/samples/quorum/dashboard.html's groups.

export function coreNav(slug) {
  return [
    { label: 'Community', items: [
      { name: 'requests', to: `/t/${slug}/requests`, label: 'Requests' },
      { name: 'ledger', to: `/t/${slug}/ledger`, label: 'Ledger' },
      { name: 'events', to: `/t/${slug}/events`, label: 'Events' },
      { name: 'announcements', to: `/t/${slug}/announcements`, label: 'Announcements' },
      { name: 'decisions', to: `/t/${slug}/decisions`, label: 'Decisions' },
      { name: 'members', to: `/t/${slug}/members`, label: 'Members' }
    ] }
  ]
}

export function insightNav(slug, tenant) {
  const groups = []
  const has = (id) => tenant.enabled_packs.includes(id) || tenant.optional_packs.includes(id)

  if (has('reliability_ops')) {
    groups.push({ label: 'Pack 01 · Operations', items: [
      { name: 'insights-operations', to: `/t/${slug}/insights/operations`, label: 'Resolution' }
    ] })
  }
  if (has('bayes_ranking')) {
    groups.push({ label: 'Pack 02 · Comparison', items: [
      { name: 'insights-comparison', to: `/t/${slug}/insights/comparison`, label: 'Leaderboard' }
    ] })
  }
  if (has('forecast_risk')) {
    groups.push({ label: 'Pack 03 · Foresight', items: [
      { name: 'insights-forecast', to: `/t/${slug}/insights/forecast`, label: 'Forecast' }
    ] })
  }
  if (has('governance_insight')) {
    groups.push({ label: 'Pack 04 · Voice', items: [
      { name: 'insights-governance', to: `/t/${slug}/insights/governance`, label: 'Segmentation' }
    ] })
  }
  return groups
}

export function adminNav(slug) {
  return [
    { label: 'Admin', items: [
      { name: 'admin-overview', to: `/t/${slug}/admin`, label: 'Oversight' },
      { name: 'admin-approvals', to: `/t/${slug}/admin/approvals`, label: 'Approvals' },
      { name: 'tenant-settings', to: `/t/${slug}/settings`, label: 'Settings' }
    ] }
  ]
}

export function footNav(slug) {
  return [
    { label: '', items: [
      { name: 'method-cards', to: '/methods', label: 'Method cards' },
      { name: 'workspace', to: '/workspace', label: 'Switch tenant' }
    ] }
  ]
}
