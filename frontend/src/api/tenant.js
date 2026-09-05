// Real GET /api/t/{slug}/tenant. Per-tenant identity - name, vertical,
// enabled_packs, description, timezone - for the tenant the JWT/URL slug
// actually names, not the two-entry fixture in fixtures/tenants.js. See
// stores/tenant.js for the cache this feeds and its shape assumptions.

import { api, tenantPath } from './client'

export function getTenant(slug) {
  return api.get(tenantPath(slug, '/tenant'))
}
