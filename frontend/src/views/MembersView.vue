<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { membersFor } from '../fixtures/members'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const list = computed(() => membersFor(slug.value))

const q = ref('')
const filtered = computed(() => {
  if (!q.value.trim()) return list.value
  const needle = q.value.trim().toLowerCase()
  return list.value.filter((m) => m.name.toLowerCase().includes(needle) || m.role.includes(needle))
})
</script>

<template>
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
