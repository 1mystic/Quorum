// decision stream fixtures, per docs/STATS_CATALOG.md voting.schulze /
// voting.condorcet_winner. A Condorcet cycle is disclosed, never hidden
// behind whichever rule breaks the tie (docs/VERTICALS.md demo seed for
// rwa_society deliberately plants one).

const cycleEvidence = {
  value: {
    ranking: ['Renovate clubhouse roof', 'Add EV charging bays', 'Repaint common corridors'],
    strongest_paths: {
      'Renovate clubhouse roof': { 'Add EV charging bays': 62, 'Repaint common corridors': 58 },
      'Add EV charging bays': { 'Renovate clubhouse roof': 51, 'Repaint common corridors': 60 },
      'Repaint common corridors': { 'Renovate clubhouse roof': 55, 'Add EV charging bays': 49 }
    },
    winner: 'Renovate clubhouse roof',
    is_condorcet_winner: false,
    cycle_disclosed: true,
    pairwise: [
      { a: 'Renovate clubhouse roof', b: 'Add EV charging bays', a_votes: 62, b_votes: 51 },
      { a: 'Add EV charging bays', b: 'Repaint common corridors', a_votes: 60, b_votes: 49 },
      { a: 'Repaint common corridors', b: 'Renovate clubhouse roof', a_votes: 55, b_votes: 58 }
    ]
  },
  n: 113,
  method: 'voting.schulze',
  as_of: '2026-08-20T12:00:00Z',
  interval: null,
  interval_kind: 'none',
  assumptions: ['The declared rule was Schulze before ballots were cast'],
  checks: [
    {
      id: 'condorcet-cycle-present',
      label: 'A > B > C > A: no option beats every other head to head',
      status: 'WARN',
      statistic: null,
      detail: 'Renovate clubhouse roof beats Add EV charging bays, which beats Repaint corridors, which beats Renovate clubhouse roof. The Schulze winner resolves the cycle by strongest beatpath; it is not a Condorcet winner.',
      blocking: false
    }
  ],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: '',
  params_hash: '5c9a0e17',
  contract_version: 1
}

const cleanEvidence = {
  value: {
    ranking: ['Ananya Rao', 'Vivek Suresh', 'Diya Kapoor'],
    strongest_paths: {
      'Ananya Rao': { 'Vivek Suresh': 71, 'Diya Kapoor': 68 },
      'Vivek Suresh': { 'Ananya Rao': 45, 'Diya Kapoor': 60 },
      'Diya Kapoor': { 'Ananya Rao': 48, 'Vivek Suresh': 56 }
    },
    winner: 'Ananya Rao',
    is_condorcet_winner: true,
    cycle_disclosed: false,
    pairwise: [
      { a: 'Ananya Rao', b: 'Vivek Suresh', a_votes: 71, b_votes: 45 },
      { a: 'Ananya Rao', b: 'Diya Kapoor', a_votes: 68, b_votes: 48 },
      { a: 'Vivek Suresh', b: 'Diya Kapoor', a_votes: 60, b_votes: 56 }
    ]
  },
  n: 116,
  method: 'voting.schulze',
  as_of: '2026-08-18T12:00:00Z',
  interval: null,
  interval_kind: 'none',
  assumptions: ['The declared rule was Schulze before ballots were cast'],
  checks: [],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: '',
  params_hash: '91af0c3d',
  contract_version: 1
}

export const decisions = {
  'vaikunth-heights': [
    {
      id: 'dc-1', title: 'Capex priority for FY27', kind: 'poll', status: 'closed',
      opened_at: '2026-08-10T00:00:00Z', closed_at: '2026-08-20T00:00:00Z',
      options: ['Renovate clubhouse roof', 'Add EV charging bays', 'Repaint common corridors'],
      turnout: 113, eligible: 214, evidence: cycleEvidence
    },
    {
      id: 'dc-2', title: 'Sinking fund allocation, next quarter', kind: 'poll', status: 'open',
      opened_at: '2026-08-27T00:00:00Z', closed_at: null,
      options: ['STP upgrade', 'Lift modernisation', 'Rainwater harvesting'],
      turnout: 41, eligible: 214, evidence: null
    }
  ],
  'aavartan-robotics': [
    {
      id: 'dc-11', title: 'Core committee election', kind: 'poll', status: 'closed',
      opened_at: '2026-08-01T00:00:00Z', closed_at: '2026-08-08T00:00:00Z',
      options: ['Ananya Rao', 'Vivek Suresh', 'Diya Kapoor'],
      turnout: 116, eligible: 180, evidence: cleanEvidence
    },
    {
      id: 'dc-12', title: 'Annual fest theme', kind: 'poll', status: 'open',
      opened_at: '2026-08-25T00:00:00Z', closed_at: null,
      options: ['Retro tech', 'Space exploration', 'Sustainable futures'],
      turnout: 58, eligible: 180, evidence: null
    }
  ]
}

export function decisionsFor(slug) {
  return decisions[slug] || []
}

export function decisionById(slug, id) {
  return decisionsFor(slug).find((d) => d.id === id) || null
}
