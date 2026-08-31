// Real calls against app/api/ledger.py. Only the reads/writes that exist:
// there is no "list every entry" endpoint yet (see LedgerView.vue's comment),
// so this covers a member's own dues and recording a payment against one.

import { api, tenantPath } from './client'

export function myDues(slug) {
  return api.get(tenantPath(slug, '/ledger/dues/me'))
}

export function recordPayment(slug, payload) {
  return api.post(tenantPath(slug, '/ledger/payments'), payload)
}
