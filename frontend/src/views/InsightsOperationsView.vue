<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import SurvivalCurve from '../components/evidence/SurvivalCurve.vue'
import ControlChart from '../components/evidence/ControlChart.vue'
import { operationsPack } from '../fixtures/insights'

// TODO(frontend): still fixture-backed. GET /api/t/{slug}/insights/{pack} is
// real (app/api/insights.py) but there is no seeded tenant yet
// (CONTEXT.md's C.19 seed script is still blocked on Pack 4 landing), so
// every real row would currently read insufficient_data - not a demo worth
// showing over the hand-built fixture. Swap is a one-line change per the
// original breadth-pass note once seed data exists. `pack` is keyed by the
// two demo slugs only, so a real tenant falls back to the calm empty state
// below rather than crashing on `pack.tiles`.
const route = useRoute()
const slug = computed(() => route.params.slug)
const pack = computed(() => operationsPack[slug.value] || null)
</script>

<template>
  <TenantShell title="Resolution" :subtitle="`request_flow · Pack 01 Reliability & Service Ops`" as-of="insight_run · contract v1">
    <template v-if="pack">
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
    </template>

    <div v-else class="card empty-state">
      <h3>Not enough data yet</h3>
      <p>This tenant has no materialized reliability insights to show yet.</p>
    </div>
  </TenantShell>
</template>
