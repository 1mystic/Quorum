import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { rolesForVertical, defaultRoleForVertical, tierForRole, labelForRole } from '../fixtures/roles'

// Demo-only role state, shared by the role switcher (TenantShell) and the
// route guard (router/index.js). There is no real backend to authorize
// against yet, per CONTEXT.md's decision log, so this only ever informs the
// UI: it never blocks navigation.

export function useDemoRole(tenant) {
  const auth = useAuthStore()

  const roles = computed(() => rolesForVertical(tenant.value ? tenant.value.vertical : 'rwa_society'))

  const currentRoleId = computed(() => {
    if (auth.demoRole) return auth.demoRole
    return tenant.value ? defaultRoleForVertical(tenant.value.vertical) : 'resident'
  })

  const currentRoleLabel = computed(() => labelForRole(tenant.value ? tenant.value.vertical : 'rwa_society', currentRoleId.value))

  const currentTier = computed(() => tierForRole(tenant.value ? tenant.value.vertical : 'rwa_society', currentRoleId.value))

  function selectRole(roleId) {
    auth.setDemoRole(roleId, tenant.value ? tenant.value.vertical : 'rwa_society')
  }

  return { roles, currentRoleId, currentRoleLabel, currentTier, selectRole }
}
