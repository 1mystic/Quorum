// Real calls against app/api/decision.py. Returns the raw Decision/
// DecisionOption/Ballot rows (app/schemas/decision.py's DecisionItem) - the
// tabulated result (voting.schulze, the pairwise matrix, the Condorcet-cycle
// disclosure) is a materialized Evidence envelope from insight_runs, not a
// field on this response. See DecisionDetailView.vue's comment for why that
// half still reads from fixtures.

import { api, tenantPath } from './client'

export function listDecisions(slug) {
  return api.get(tenantPath(slug, '/decisions'))
}

export function getDecision(slug, id) {
  return api.get(tenantPath(slug, `/decisions/${id}`))
}

export function castBallot(slug, id, payload) {
  return api.post(tenantPath(slug, `/decisions/${id}/ballots`), payload)
}
