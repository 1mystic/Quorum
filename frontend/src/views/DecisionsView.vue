<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { decisionsFor } from '../fixtures/decisions'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const list = computed(() => decisionsFor(slug.value))

function fmt(iso) {
  return iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''
}
</script>

<template>
  <TenantShell :title="tenant.labels.decision + 's'" :subtitle="`decision · ${list.length} total`">
    <div class="card">
      <div class="list">
        <router-link v-for="d in list" :key="d.id" class="list-row" :to="`/t/${slug}/decisions/${d.id}`">
          <div class="lr-main">
            <div class="lr-title">
              {{ d.title }}
              <span v-if="d.evidence && d.evidence.value.cycle_disclosed" class="flag">Cycle disclosed</span>
            </div>
            <div class="lr-sub">{{ d.options.length }} options · opened {{ fmt(d.opened_at) }}{{ d.closed_at ? ` · closed ${fmt(d.closed_at)}` : '' }} · turnout {{ d.turnout }} of {{ d.eligible }}</div>
          </div>
          <div class="lr-meta">
            <span class="badge" :class="d.status === 'open' ? 'badge-open' : 'badge-closed'">{{ d.status }}</span>
          </div>
        </router-link>
      </div>
    </div>
  </TenantShell>
</template>
