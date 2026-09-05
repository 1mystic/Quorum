<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import TenantPending from '../components/layout/TenantPending.vue'
import { useTenant } from '../composables/useTenant'
import { toast } from '../composables/useToast'
import { listMyRequests, resolveRequest, escalateRequest } from '../api/requests'
import { useAsyncData } from '../composables/useAsyncData'

// There is no GET /api/t/{slug}/requests/{id} route (app/api/request.py only
// lists), so this reads the same list RequestsView does and finds the one
// row by id - honest about the real shape of the API rather than inventing
// a route. The fixture's `eta` (conformal.mondrian_eta) and `near_duplicates`
// (text.near_duplicate_candidates) have no backing endpoint yet and are not
// shown.

const route = useRoute()
const slug = computed(() => route.params.slug)
const { tenant, loading: tenantLoading, error: tenantError } = useTenant(slug)
const requestId = computed(() => Number(route.params.ref))

const { loading, error, data, run } = useAsyncData()
const request = computed(() => (data.value || []).find((r) => r.id === requestId.value) || null)

function load() {
  run(() => listMyRequests(slug.value))
}

onMounted(load)
watch(() => route.params.ref, load)

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''
}

async function resolve() {
  try {
    await resolveRequest(slug.value, requestId.value)
    toast.success(`#${requestId.value} marked resolved.`)
    load()
  } catch (err) {
    toast.error(err.message || 'Could not mark resolved.')
  }
}

async function escalate() {
  try {
    await escalateRequest(slug.value, requestId.value)
    toast.info(`#${requestId.value} escalated to the committee.`)
    load()
  } catch (err) {
    toast.error(err.message || 'Could not escalate.')
  }
}
</script>

<template>
  <TenantPending v-if="!tenant" :loading="tenantLoading" :error="tenantError" />

  <TenantShell v-else-if="loading" title="Loading…">
    <div class="empty-state"><h3>Loading…</h3></div>
  </TenantShell>

  <TenantShell v-else-if="error" title="Could not load">
    <div class="callout callout-warn"><span>{{ error }}</span></div>
  </TenantShell>

  <TenantShell
    v-else-if="request" :title="request.title" :subtitle="`#${request.id} · ${tenant.labels.request}`"
    :back-to="`/t/${slug}/requests`" :back-label="tenant.labels.request + 's'"
  >
    <template #actions>
      <button class="btn btn-ghost" @click="escalate">Escalate</button>
      <button class="btn btn-primary" @click="resolve"><span>Mark resolved</span></button>
    </template>

    <div class="row r-32">
      <div class="card">
        <div class="chead">
          <div>
            <h3>{{ request.title }}</h3>
            <div class="sub">{{ request.category.replace(/_/g, ' ') }} · {{ request.location_ref || 'no location' }} · {{ request.group_name }}</div>
          </div>
          <span class="badge" :class="'badge-' + request.status.toLowerCase().replace('_', '-')">{{ request.status.replace('_', ' ').toLowerCase() }}</span>
        </div>
        <p style="font-size:14.5px;line-height:1.65;color:var(--ink-2)">{{ request.description }}</p>
        <div class="meta">
          <span v-if="request.priority"><b>priority</b> {{ request.priority.replace('_', ' ') }}</span>
          <span v-if="request.channel"><b>channel</b> {{ request.channel }}</span>
          <span><b>opened</b> {{ fmt(request.created_at) }}</span>
        </div>
      </div>

      <div class="card">
        <div class="chead"><div><h3>Response</h3></div></div>
        <div v-if="request.response" class="timeline">
          <div class="tl-item">
            <div class="tl-label">Replied by {{ request.response.by }}</div>
            <div class="tl-at">{{ fmt(request.response.at) }}</div>
            <div class="tl-detail">{{ request.response.text }}</div>
          </div>
        </div>
        <p v-else style="font-size:14.5px;color:var(--ink-2)">No response yet.</p>
        <div v-if="request.resolved_at" class="timeline" style="margin-top:var(--sp3)">
          <div class="tl-item">
            <div class="tl-label">Resolved</div>
            <div class="tl-at">{{ fmt(request.resolved_at) }}</div>
          </div>
        </div>
      </div>
    </div>
  </TenantShell>

  <TenantShell v-else title="Not found">
    <div class="empty-state">
      <h3>No such {{ tenant.labels.request.toLowerCase() }}</h3>
      <p><router-link :to="`/t/${slug}/requests`">Back to the list</router-link></p>
    </div>
  </TenantShell>
</template>
