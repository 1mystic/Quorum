<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import TenantPending from '../components/layout/TenantPending.vue'
import { useTenant } from '../composables/useTenant'
import { membersFor } from '../fixtures/members'

// TODO(frontend): still fixture-backed. app/api/member.py has no "list all
// members of a tenant" route (only /me and /{member_id}), so there is no
// single real endpoint this list maps onto; out of this session's scope.
const route = useRoute()
const slug = computed(() => route.params.slug)
const { tenant, loading: tenantLoading, error: tenantError } = useTenant(slug)
const list = computed(() => membersFor(slug.value))

const q = ref('')
const filtered = computed(() => {
  if (!q.value.trim()) return list.value
  const needle = q.value.trim().toLowerCase()
  return list.value.filter((m) => m.name.toLowerCase().includes(needle) || m.role.includes(needle))
})
</script>

<template>
  <template v-if="tenant">
  <TenantShell :title="tenant.labels.member + ' directory'" :subtitle="`${list.length} total`">
    <div class="card">
      <div class="field" style="max-width:320px">
        <label for="search">Search</label>
        <input id="search" v-model="q" type="text" placeholder="Name or role" />
      </div>

      <div class="tbl-scroll">
        <table class="tbl">
          <thead>
            <tr>
              <th>Name</th><th>Role</th>
              <th v-if="tenant.vertical === 'rwa_society'">Unit</th>
              <th v-if="tenant.vertical === 'campus_club'">Year / dept</th>
              <th>Since</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in filtered" :key="m.id">
              <td class="nm">{{ m.name }}</td>
              <td class="dim">{{ m.role.replace('_', ' ') }}</td>
              <td v-if="tenant.vertical === 'rwa_society'" class="dim">{{ m.unit }} ({{ m.ownership }})</td>
              <td v-if="tenant.vertical === 'campus_club'" class="dim">Y{{ m.year }} · {{ m.department }}</td>
              <td class="dim">{{ m.joined_at }}</td>
              <td><span class="badge" :class="m.status === 'active' ? 'badge-resolved' : 'badge-pending'">{{ m.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </TenantShell>
  </template>
  <TenantPending v-else :loading="tenantLoading" :error="tenantError" />
</template>
