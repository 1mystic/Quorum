import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { rolesForVertical, labelForRole } from '../fixtures/roles'

// The role switcher picks which vertical-role label is shown (Resident vs
// Auditor, President vs Treasurer); it cannot change what the session can
// actually do. `auth.role` is the real access tier, set from the JWT on
// login (useAuthSession.completeSignIn) and enforced by the backend, so the
// options offered here are filtered to that tier - a member never sees an
// admin-tier label to pick, and vice versa, keeping the switcher unable to
// desync from what the API will actually allow.

export function useDemoRole(tenant) {
  const auth = useAuthStore()

  const roles = computed(() => {
    const all = rolesForVertical(tenant.value ? tenant.value.vertical : 'rwa_society')
    return all.filter((r) => r.tier === auth.role)
  })

  const currentRoleId = computed(() => {
    if (auth.demoRole && roles.value.some((r) => r.id === auth.demoRole)) return auth.demoRole
    return roles.value[0] ? roles.value[0].id : 'resident'
  })

  const currentRoleLabel = computed(() => labelForRole(tenant.value ? tenant.value.vertical : 'rwa_society', currentRoleId.value))

  function selectRole(roleId) {
    auth.setDemoRole(roleId)
  }

  return { roles, currentRoleId, currentRoleLabel, currentTier: computed(() => auth.role), selectRole }
}
