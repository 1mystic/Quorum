// Real calls against app/api/request.py (the request_flow domain, card C.8).
// Response shapes are app/schemas/request.py's MyRequestItem /
// RaiseRequestResponse / RequestActionResponse.

import { api, tenantPath } from './client'

export function listMyRequests(slug, { status, groupId } = {}) {
  return api.get(tenantPath(slug, '/requests'), { params: { status, group_id: groupId } })
}

export function raiseRequest(slug, payload) {
  return api.post(tenantPath(slug, '/requests'), payload)
}

export function resolveRequest(slug, id) {
  return api.patch(tenantPath(slug, `/requests/${id}/resolve`), {})
}

export function escalateRequest(slug, id) {
  return api.patch(tenantPath(slug, `/requests/${id}/escalate`), {})
}

export function withdrawRequest(slug, id) {
  return api.patch(tenantPath(slug, `/requests/${id}/withdraw`), {})
}
