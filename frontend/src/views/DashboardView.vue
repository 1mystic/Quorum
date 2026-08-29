<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import SurvivalCurve from '../components/evidence/SurvivalCurve.vue'
import { tenantBySlug, packMeta } from '../fixtures/tenants'
import { operationsPack, forecastPack } from '../fixtures/insights'
import { ledgerSummary } from '../fixtures/ledger'
import { requestsFor } from '../fixtures/requests'

// The tenant home: one headline figure per enabled pack (per
// docs/VERTICALS.md's "headline statistics for the tenant home" lists),
// the flagship KM curve, recent activity and a way into every pack. This is
// deliberately not the Pack 1 Operations page again: that page (and its
// control chart) lives at insights/operations.

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))

const ops = computed(() => operationsPack[slug.value])
const forecast = computed(() => forecastPack[slug.value])
const ledger = computed(() => ledgerSummary[slug.value])

const fourthOpsTile = computed(() => ops.value.tiles[3])
const recentRequests = computed(() => requestsFor(slug.value).slice(0, 4))

function has(packId) {
  return tenant.value.enabled_packs.includes(packId) || tenant.value.optional_packs.includes(packId)
}

const packLinks = computed(() => Object.values(packMeta).filter((p) => has(p.id)))

const packQuestions = {
  reliability_ops: 'Is this getting better or worse?',
  forecast_risk: 'What is coming, and how sure are we?',
  bayes_ranking: 'Is the new vendor actually better?',
  governance_insight: 'What does the community actually want?'
}

function badgeClass(status) {
  return 'badge badge-' + status.replace('_', '-').replace('in-progress', 'progress')
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <TenantShell title="Overview" :subtitle="`${tenant.name} · ${tenant.tagline}`" as-of="insight_run · contract v1">
    <div class="row r-4">
      <StatTile :title="ops.tiles[0].title" :subtitle="ops.tiles[0].subtitle" :evidence="ops.tiles[0].evidence">
        <template v-if="ops.tiles[0].why" #why><p>{{ ops.tiles[0].why }}</p></template>
      </StatTile>
      <StatTile :title="`${tenant.labels.ledger} receipt gap`" subtitle="share of receipts never collected" :evidence="ledger.receiptGap">
        <template #why><p>Payment is bank transfer, WhatsApp screenshot and manual treasurer verification, so a receipt issued is not always a receipt collected. This is the honest share that goes uncollected, with a Wilson interval, not an average.</p></template>
      </StatTile>
      <StatTile :title="fourthOpsTile.title" :subtitle="fourthOpsTile.subtitle" :evidence="fourthOpsTile.evidence">
        <template v-if="fourthOpsTile.why" #why><p>{{ fourthOpsTile.why }}</p></template>
      </StatTile>
      <StatTile :title="forecast.calibration.title" :subtitle="forecast.calibration.subtitle" :evidence="forecast.calibration.evidence">
        <template #why><p>{{ forecast.calibration.why }}</p></template>
      </StatTile>
    </div>

    <div class="row r-32">
      <SurvivalCurve :title="ops.survival.title" :subtitle="ops.survival.subtitle" :evidence="ops.survival.evidence" />

      <div class="card">
        <div class="chead">
          <div><h3>Recent {{ tenant.labels.request.toLowerCase() }}s</h3><div class="sub">latest activity, request_flow</div></div>
        </div>
        <div class="list">
          <router-link v-for="r in recentRequests" :key="r.ref" class="list-row" :to="`/t/${slug}/requests/${r.ref}`">
            <div class="lr-main">
              <div class="lr-title">{{ r.title }}</div>
              <div class="lr-sub">{{ r.ref }} · {{ r.category.replace(/_/g, ' ') }} · opened {{ fmtDate(r.opened_at) }}</div>
            </div>
            <div class="lr-meta">
              <span :class="badgeClass(r.status)">{{ r.status.replace('_', ' ') }}</span>
            </div>
          </router-link>
        </div>
        <router-link class="tl" :to="`/t/${slug}/requests`">All {{ tenant.labels.request.toLowerCase() }}s</router-link>
      </div>
    </div>

    <div class="row r-4">
      <router-link v-for="p in packLinks" :key="p.id" class="card" :to="`/t/${slug}/insights/${p.route.replace('insights-', '')}`">
        <div class="chead">
          <div><h3>Pack {{ p.number }} · {{ p.name }}</h3></div>
          <span class="pill p-est">Open</span>
        </div>
        <p style="color:var(--ink-2);font-size:14.5px;line-height:1.6">{{ packQuestions[p.id] }}</p>
      </router-link>
    </div>
  </TenantShell>
</template>
