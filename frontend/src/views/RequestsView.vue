<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import TenantPending from '../components/layout/TenantPending.vue'
import { useTenant } from '../composables/useTenant'
import { listMyRequests } from '../api/requests'
import { useAsyncData } from '../composables/useAsyncData'

// Real GET /api/t/{slug}/requests (app/api/request.py, card C.8). The
// backend has no near_duplicate_candidates or conformal ETA route yet
// (docs/STATS_API.md's text.*/conformal.* services are not exposed on this
// endpoint), so the fixture's `near_duplicates`/`eta` fields from
// fixtures/requests.js have no real source and are simply not shown here.

const route = useRoute()
const slug = computed(() => route.params.slug)
const { tenant, loading: tenantLoading, error: tenantError } = useTenant(slug)

// Matches app/models/request.py's RequestStatus exactly, lowercased for
// display; "closed" from the old fixture list is not a real backend status
// and is dropped.
const requestStatuses = ['open', 'in_progress', 'escalated', 'withdrawn', 'merged', 'resolved']

const statusFilter = ref('all')
const categoryFilter = ref('all')
const categories = computed(() => tenant.value.requestCategories)

const { loading, error, data, run } = useAsyncData()
const requests = computed(() => data.value || [])

function load() {
  run(() => listMyRequests(slug.value, {
    status: statusFilter.value === 'all' ? undefined : statusFilter.value.toUpperCase()
  }))
}

onMounted(load)
watch(statusFilter, load)
watch(() => route.params.slug, load)

const filtered = computed(() => requests.value.filter((r) => {
  if (categoryFilter.value !== 'all' && r.category !== categoryFilter.value) return false
  return true
}))

function badgeClass(status) {
  return 'badge badge-' + status.toLowerCase().replace('_', '-').replace('in-progress', 'progress')
}

function fmtDate(iso) {
  return iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''
}
</script>

<template>
  <template v-if="tenant">
  <TenantShell :title="tenant.labels.request + 's'" :subtitle="`request_flow · ${requests.length} total`">
    <template #actions>
      <router-link class="btn btn-primary" :to="`/t/${slug}/requests/new`"><span>Raise a {{ tenant.labels.request.toLowerCase() }}</span></router-link>
    </template>

    <div class="card">
      <div class="chips">
        <button class="chip" :class="{ on: statusFilter === 'all' }" @click="statusFilter = 'all'">All statuses</button>
        <button v-for="s in requestStatuses" :key="s" class="chip" :class="{ on: statusFilter === s }" @click="statusFilter = s">{{ s.replace('_', ' ') }}</button>
      </div>
      <div class="chips">
        <button class="chip" :class="{ on: categoryFilter === 'all' }" @click="categoryFilter = 'all'">All categories</button>
        <button v-for="c in categories" :key="c" class="chip" :class="{ on: categoryFilter === c }" @click="categoryFilter = c">{{ c.replace(/_/g, ' ') }}</button>
      </div>

      <div v-if="loading" class="empty-state">
        <h3>Loading…</h3>
      </div>

      <div v-else-if="error" class="callout callout-warn">
        <span>Could not load {{ tenant.labels.request.toLowerCase() }}s: {{ error }}</span>
      </div>

      <div v-else-if="!filtered.length" class="empty-state">
        <h3>No {{ tenant.labels.request.toLowerCase() }}s match</h3>
        <p>Try a different status or category filter.</p>
      </div>

      <div v-else class="list">
        <router-link
          v-for="r in filtered" :key="r.id"
          class="list-row" :to="`/t/${slug}/requests/${r.id}`"
        >
          <div class="lr-main">
            <div class="lr-title">{{ r.title }}</div>
            <div class="lr-sub">#{{ r.id }} · {{ r.category.replace(/_/g, ' ') }} · {{ r.location_ref || 'no location' }} · opened {{ fmtDate(r.created_at) }}</div>
          </div>
          <div class="lr-meta">
            <span v-if="r.priority" class="badge" :class="'badge-' + r.priority.replace('_', '-')">{{ r.priority.replace('_', ' ') }}</span>
            <span :class="badgeClass(r.status)">{{ r.status.replace('_', ' ').toLowerCase() }}</span>
          </div>
        </router-link>
      </div>
    </div>
  </TenantShell>
  </template>
  <TenantPending v-else :loading="tenantLoading" :error="tenantError" />
</template>
