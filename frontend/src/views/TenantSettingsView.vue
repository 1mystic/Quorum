<script setup>
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import TenantPending from '../components/layout/TenantPending.vue'
import { packMeta } from '../fixtures/tenants'
import { useTenant } from '../composables/useTenant'
import { toast } from '../composables/useToast'

// PUT /api/t/{slug}/insights/packs/{pack_id} per docs/STATS_API.md §4:
// admin-only, writes Tenant.enabled_packs, enqueues a backfill. Disabling
// does not delete insight_runs history. This view is the UI stub for that
// endpoint.

const route = useRoute()
const slug = computed(() => route.params.slug)
const { tenant, loading: tenantLoading, error: tenantError } = useTenant(slug)

const allPacks = ['reliability_ops', 'forecast_risk', 'bayes_ranking', 'governance_insight']

const toggles = reactive({})
// Seeded once the real tenant identity arrives, not at ref/reactive
// creation time - `tenant` is asynchronous now, unlike the old
// tenantBySlug(...) fixture lookup this replaced.
watch(tenant, (t) => {
  if (!t) return
  allPacks.forEach((p) => { toggles[p] = t.enabled_packs.includes(p) })
}, { immediate: true })

function toggle(packId) {
  toggles[packId] = !toggles[packId]
  toast.info(`${packMeta[packId].name} ${toggles[packId] ? 'enabled' : 'disabled'}. UI stub: does not yet write Tenant.enabled_packs.`)
}

function isAvailable(packId) {
  return tenant.value.enabled_packs.includes(packId) || tenant.value.optional_packs.includes(packId)
}
</script>

<template>
  <template v-if="tenant">
  <TenantShell title="Settings" :subtitle="`${tenant.name} · ${tenant.vertical}`">
    <div class="card">
      <div class="chead"><div><h3>Insight packs</h3><div class="sub">a pack is only offered when its required streams are supported</div></div></div>
      <div class="list">
        <div v-for="p in allPacks" :key="p" class="list-row">
          <div class="lr-main">
            <div class="lr-title">{{ packMeta[p].name }}</div>
            <div class="lr-sub">Pack {{ packMeta[p].number }}{{ !isAvailable(p) ? ' · needs streams this tenant has not enabled' : '' }}</div>
          </div>
          <div class="lr-meta">
            <button
              class="tgl"
              :disabled="!isAvailable(p)"
              :style="{ opacity: isAvailable(p) ? 1 : 0.4, borderColor: toggles[p] ? 'var(--brand)' : undefined, color: toggles[p] ? 'var(--brand)' : undefined }"
              @click="toggle(p)"
            >{{ !isAvailable(p) ? 'Unavailable' : (toggles[p] ? 'Enabled' : 'Disabled') }}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="chead"><div><h3>Vertical</h3></div></div>
      <div class="meta">
        <span><b>id</b> {{ tenant.vertical }}</span>
        <span><b>currency</b> {{ tenant.currency }}</span>
        <span><b>timezone</b> {{ tenant.timezone }}</span>
      </div>
      <p style="font-size:13.5px;color:var(--ink-3)">Vocabulary, categories, roles and privacy floors for this vertical are configuration, not code, per docs/VERTICALS.md. Changing the vertical after go-live is not supported from this screen.</p>
    </div>
  </TenantShell>
  </template>
  <TenantPending v-else :loading="tenantLoading" :error="tenantError" />
</template>
