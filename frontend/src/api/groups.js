// Just enough of app/api/group.py to populate the group picker on the
// "raise a request" form - a request always belongs to a group. Full group
// management (create/edit/approve/members) has no page yet and stays out
// of scope here.

import { api, tenantPath } from './client'

export function myApprovedGroups(slug) {
  return api.get(tenantPath(slug, '/groups/me'), { params: { role: 'MEMBER', status: 'APPROVED' } })
}
