// Demo-only role catalogue, per docs/VERTICALS.md role lists. Used by the
// role switcher and the route-guard mismatch banner, not by any real
// authorization: there is no backend to enforce these against yet.

export const verticalRoles = {
  rwa_society: [
    { id: 'president', label: 'President', tier: 'admin' },
    { id: 'secretary', label: 'Secretary', tier: 'admin' },
    { id: 'treasurer', label: 'Treasurer', tier: 'admin' },
    { id: 'committee_member', label: 'Committee member', tier: 'admin' },
    { id: 'resident', label: 'Resident', tier: 'member' },
    { id: 'auditor', label: 'Auditor', tier: 'member' },
    { id: 'guest', label: 'Guest', tier: 'member' }
  ],
  campus_club: [
    { id: 'faculty_advisor', label: 'Faculty advisor', tier: 'admin' },
    { id: 'president', label: 'President', tier: 'admin' },
    { id: 'core_team', label: 'Core team', tier: 'admin' },
    { id: 'member', label: 'Member', tier: 'member' },
    { id: 'alumnus', label: 'Alumnus', tier: 'member' },
    { id: 'guest', label: 'Guest', tier: 'member' }
  ]
}

export function rolesForVertical(vertical) {
  return verticalRoles[vertical] || verticalRoles.rwa_society
}

export function tierForRole(vertical, roleId) {
  const found = rolesForVertical(vertical).find((r) => r.id === roleId)
  return found ? found.tier : 'member'
}

export function defaultRoleForVertical(vertical) {
  const roles = rolesForVertical(vertical)
  const member = roles.find((r) => r.tier === 'member')
  return (member || roles[0]).id
}

export function labelForRole(vertical, roleId) {
  const found = rolesForVertical(vertical).find((r) => r.id === roleId)
  return found ? found.label : roleId
}
