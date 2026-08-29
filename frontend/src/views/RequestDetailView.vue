<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { requestByRef } from '../fixtures/requests'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const request = computed(() => requestByRef(slug.value, route.params.ref))

function fmt(iso) {
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function resolve() {
  toast.success(`${request.value.ref} marked resolved. This is a UI stub until the request_flow write path lands.`)
}
function escalate() {
  toast.info(`${request.value.ref} escalated to the committee. This is a UI stub until the request_flow write path lands.`)
}
</script>

<template>
  <TenantShell v-if="request" :title="request.title" :subtitle="`${request.ref} · ${tenant.labels.request}`">
    <template #actions>
      <button class="btn btn-ghost" @click="escalate">Escalate</button>
      <button class="btn btn-primary" @click="resolve"><span>Mark resolved</span></button>
    </template>

    <div class="row r-32">
      <div class="card">
        <div class="chead">
          <div>
            <h3>{{ request.title }}</h3>
            <div class="sub">{{ request.category.replace(/_/g, ' ') }} · {{ request.location || 'no location' }} · raised by {{ request.raised_by }}</div>
          </div>
          <span class="badge" :class="'badge-' + request.status.replace('_', '-').replace('in-progress', 'progress')">{{ request.status.replace('_', ' ') }}</span>
        </div>
        <p style="font-size:14.5px;line-height:1.65;color:var(--ink-2)">{{ request.description }}</p>
        <div class="meta">
          <span><b>priority</b> {{ request.priority.replace('_', ' ') }}</span>
          <span><b>assignee</b> {{ request.assignee || 'unassigned' }}</span>
          <span><b>channel</b> {{ request.channel }}</span>
        </div>

        <div v-if="request.near_duplicates.length" class="callout callout-warn">
          <span>Possible duplicate: <b>{{ request.near_duplicates[0].title }}</b> ({{ request.near_duplicates[0].ref }}), similarity {{ (request.near_duplicates[0].similarity * 100).toFixed(0) }}%. <code style="font-family:var(--font-mono)">text.near_duplicate_candidates</code>, computed on submission.</span>
        </div>
      </div>

      <div class="card">
        <div class="chead"><div><h3>Status history</h3></div></div>
        <div class="timeline">
          <div v-for="(t, i) in request.timeline" :key="i" class="tl-item">
            <div class="tl-label">{{ t.label }}</div>
            <div class="tl-at">{{ fmt(t.at) }}</div>
            <div v-if="t.detail" class="tl-detail">{{ t.detail }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="row" style="grid-template-columns:1fr" v-if="request.eta">
      <StatTile
        title="Estimated time to resolution"
        subtitle="conformalised survival eta"
        :evidence="request.eta"
        display="range"
      >
        <template #why>
          <p>A conformal interval guarantees marginal coverage: across many requests like this one, the true resolution time falls inside the stated bound the stated fraction of the time. It is not a promise about this one request alone.</p>
        </template>
      </StatTile>
    </div>
  </TenantShell>

  <TenantShell v-else title="Not found">
    <div class="empty-state">
      <h3>No such {{ tenant.labels.request.toLowerCase() }}</h3>
      <p><router-link :to="`/t/${slug}/requests`">Back to the list</router-link></p>
    </div>
  </TenantShell>
</template>
