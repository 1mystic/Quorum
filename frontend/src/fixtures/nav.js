// Sidebar nav groups, built per tenant so every page is actually reachable
// (not just routed), matching design/samples/quorum/dashboard.html's groups.

// A flat, unlabelled group: TenantShell.vue only renders a collapsible
// header when `group.label` is truthy, so an empty label here renders as a
// single top-level link, not buried inside Community/Insights/Admin - the
// assistant is core to the product thesis ("the LLM narrates, statistics
// decide"), not a feature to go hunting for.
export function assistantNav(slug) {
  return [{ label: '', items: [
    { name: 'assistant', to: `/t/${slug}/assistant`, label: 'Assistant' }
  ] }]
}

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

// One Insights section for every enabled pack, not one micro-section per
// pack: four enabled packs used to mean four headers each holding a single
// link. The pack number stays on the item itself (not a repeated header) so
// a Method Card can still be traced back to its pack at a glance.
export function insightNav(slug, tenant) {
  const has = (id) => tenant.enabled_packs.includes(id) || tenant.optional_packs.includes(id)

  const items = []
  if (has('reliability_ops')) {
    items.push({ name: 'insights-operations', to: `/t/${slug}/insights/operations`, label: 'Resolution', pack: '01' })
  }
  if (has('bayes_ranking')) {
    items.push({ name: 'insights-comparison', to: `/t/${slug}/insights/comparison`, label: 'Leaderboard', pack: '02' })
  }
  if (has('forecast_risk')) {
    items.push({ name: 'insights-forecast', to: `/t/${slug}/insights/forecast`, label: 'Forecast', pack: '03' })
  }
  if (has('governance_insight')) {
    items.push({ name: 'insights-governance', to: `/t/${slug}/insights/governance`, label: 'Segmentation', pack: '04' })
  }
  if (items.length === 0) return []
  return [{ label: 'Insights', items }]
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
