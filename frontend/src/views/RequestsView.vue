<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { requestsFor, requestStatuses } from '../fixtures/requests'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const all = computed(() => requestsFor(slug.value))

const statusFilter = ref('all')
const categoryFilter = ref('all')

const categories = computed(() => tenant.value.requestCategories)

const filtered = computed(() => all.value.filter((r) => {
  if (statusFilter.value !== 'all' && r.status !== statusFilter.value) return false
  if (categoryFilter.value !== 'all' && r.category !== categoryFilter.value) return false
  return true
}))

function badgeClass(status) {
  return 'badge badge-' + status.replace('_', '-').replace('in-progress', 'progress')
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <TenantShell :title="tenant.labels.request + 's'" :subtitle="`request_flow · ${all.length} total`">
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

      <div v-if="!filtered.length" class="empty-state">
        <h3>No {{ tenant.labels.request.toLowerCase() }}s match</h3>
        <p>Try a different status or category filter.</p>
      </div>

      <div v-else class="list">
        <router-link
          v-for="r in filtered" :key="r.ref"
          class="list-row" :to="`/t/${slug}/requests/${r.ref}`"
        >
          <div class="lr-main">
            <div class="lr-title">{{ r.title }}</div>
            <div class="lr-sub">{{ r.ref }} · {{ r.category.replace(/_/g, ' ') }} · {{ r.location || 'no location' }} · opened {{ fmtDate(r.opened_at) }}</div>
            <div v-if="r.near_duplicates.length" class="lr-sub" style="color:var(--accent)">
              {{ r.near_duplicates.length }} similar {{ tenant.labels.request.toLowerCase() }} already reported: "{{ r.near_duplicates[0].title }}"
            </div>
          </div>
          <div class="lr-meta">
            <span class="badge" :class="'badge-' + r.priority.replace('_', '-')">{{ r.priority.replace('_', ' ') }}</span>
            <span :class="badgeClass(r.status)">{{ r.status.replace('_', ' ') }}</span>
          </div>
        </router-link>
      </div>
    </div>
  </TenantShell>
</template>
