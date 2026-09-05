<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import TenantPending from '../components/layout/TenantPending.vue'
import { useTenant } from '../composables/useTenant'
import { decisionsFor } from '../fixtures/decisions'

// Still fixture-backed. GET /api/t/{slug}/decisions is real
// (app/api/decision.py), but this page's whole point is the tabulated
// voting.schulze result and turnout/eligible figures, which are a
// materialized Pack 4 Evidence envelope with no seeded tenant to compute
// them from yet (CONTEXT.md's C.19 is still blocked). Swapping only the raw
// list to the real endpoint would break every link to DecisionDetailView
// below, whose fixture ids ('dc-1') do not match real integer ids - so both
// stay on fixtures together rather than half-wiring a broken cross-link.
const route = useRoute()
const slug = computed(() => route.params.slug)
const { tenant, loading: tenantLoading, error: tenantError } = useTenant(slug)
const list = computed(() => decisionsFor(slug.value))

function fmt(iso) {
  return iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''
}
</script>

<template>
  <template v-if="tenant">
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
  <TenantPending v-else :loading="tenantLoading" :error="tenantError" />
</template>
