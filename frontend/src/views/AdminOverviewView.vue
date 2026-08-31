<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { requestsFor, requestStatuses } from '../fixtures/requests'

// TODO(frontend): still fixture-backed. This tenant-wide breakdown needs
// GET .../requests/group (app/api/request.py's leader queue, a different
// shape and role scope than RequestsView.vue's member list) plus the
// insights health endpoint for the "not currently trustworthy" panel; out
// of this session's scope.
const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const all = computed(() => requestsFor(slug.value))

const byStatus = computed(() => {
  const map = {}
  requestStatuses.forEach((s) => { map[s] = 0 })
  all.value.forEach((r) => { map[r.status] = (map[r.status] || 0) + 1 })
  return map
})

const byCategory = computed(() => {
  const map = {}
  all.value.forEach((r) => { map[r.category] = (map[r.category] || 0) + 1 })
  return Object.entries(map).sort((a, b) => b[1] - a[1])
})
</script>

<template>
  <TenantShell title="Oversight" :subtitle="`all ${tenant.labels.request.toLowerCase()}s across categories`">
    <div class="row r-4">
      <div v-for="s in requestStatuses" :key="s" class="card">
        <div class="chead"><div><h3>{{ s.replace('_', ' ') }}</h3></div></div>
        <div class="big">{{ byStatus[s] }}</div>
      </div>
    </div>

    <div class="row r-32">
      <div class="card">
        <div class="chead"><div><h3>By category</h3></div></div>
        <div class="tbl-scroll">
          <table class="tbl">
            <thead><tr><th>Category</th><th class="r">Count</th></tr></thead>
            <tbody>
              <tr v-for="[cat, count] in byCategory" :key="cat">
                <td>{{ cat.replace(/_/g, ' ') }}</td>
                <td class="r num">{{ count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="chead"><div><h3>Escalated {{ tenant.labels.request.toLowerCase() }}s</h3></div></div>
        <div class="list">
          <router-link v-for="r in all.filter((r) => r.status === 'escalated')" :key="r.ref" class="list-row" :to="`/t/${slug}/requests/${r.ref}`">
            <div class="lr-main">
              <div class="lr-title">{{ r.title }}</div>
              <div class="lr-sub">{{ r.ref }} · {{ r.category.replace(/_/g, ' ') }}</div>
            </div>
          </router-link>
          <p v-if="!all.filter((r) => r.status === 'escalated').length" style="color:var(--ink-3);font-size:13.5px">Nothing escalated right now.</p>
        </div>
      </div>
    </div>
  </TenantShell>
</template>
