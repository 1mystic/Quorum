<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import SurvivalCurve from '../components/evidence/SurvivalCurve.vue'
import ControlChart from '../components/evidence/ControlChart.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { operationsPack } from '../fixtures/insights'

// TODO(frontend): still fixture-backed. GET /api/t/{slug}/insights/{pack} is
// real (app/api/insights.py) but there is no seeded tenant yet
// (CONTEXT.md's C.19 seed script is still blocked on Pack 4 landing), so
// every real row would currently read insufficient_data - not a demo worth
// showing over the hand-built fixture. Swap is a one-line change per the
// original breadth-pass note once seed data exists.
const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const pack = computed(() => operationsPack[slug.value])
</script>

<template>
  <TenantShell title="Resolution" :subtitle="`request_flow · Pack 01 Reliability & Service Ops`" as-of="insight_run · contract v1">
    <div class="row r-4">
      <StatTile v-for="(t, i) in pack.tiles" :key="i" :title="t.title" :subtitle="t.subtitle" :evidence="t.evidence" :display="t.display || 'scalar'">
        <template v-if="t.why" #why><p>{{ t.why }}</p></template>
      </StatTile>
    </div>

    <div class="row r-32">
      <SurvivalCurve :title="pack.survival.title" :subtitle="pack.survival.subtitle" :evidence="pack.survival.evidence" />
      <StatTile :title="pack.insufficientTile.title" :subtitle="pack.insufficientTile.subtitle" :evidence="pack.insufficientTile.evidence" muted>
        <template #why><p>{{ pack.insufficientTile.why }}</p></template>
      </StatTile>
    </div>

    <div class="row r-32">
      <ControlChart :title="pack.controlChart.title" :subtitle="pack.controlChart.subtitle" :evidence="pack.controlChart.evidence" />
      <StatTile :title="pack.withheldTile.title" :subtitle="pack.withheldTile.subtitle" :evidence="pack.withheldTile.evidence">
        <template #why><p>{{ pack.withheldTile.why }}</p></template>
      </StatTile>
    </div>
  </TenantShell>
</template>
