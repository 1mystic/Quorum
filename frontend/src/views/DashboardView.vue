<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import SurvivalCurve from '../components/evidence/SurvivalCurve.vue'
import ControlChart from '../components/evidence/ControlChart.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { operationsPack } from '../fixtures/insights'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const pack = computed(() => operationsPack[slug.value])
</script>

<template>
  <TenantShell title="Resolution" :subtitle="`request_flow · ${tenant.name}`" as-of="insight_run · contract v1">
    <div class="row r-4">
      <StatTile v-for="(t, i) in pack.tiles" :key="i" :title="t.title" :subtitle="t.subtitle" :evidence="t.evidence" :display="t.display || 'scalar'">
        <template v-if="t.why" #why><p>{{ t.why }}</p></template>
      </StatTile>
    </div>

    <div class="row r-32">
      <SurvivalCurve :title="pack.survival.title" :subtitle="pack.survival.subtitle" :evidence="pack.survival.evidence" />
      <ControlChart :title="pack.controlChart.title" :subtitle="pack.controlChart.subtitle" :evidence="pack.controlChart.evidence" />
    </div>

    <div class="row" style="grid-template-columns:1fr">
      <StatTile :title="pack.withheldTile.title" :subtitle="pack.withheldTile.subtitle" :evidence="pack.withheldTile.evidence">
        <template #why><p>{{ pack.withheldTile.why }}</p></template>
      </StatTile>
    </div>
  </TenantShell>
</template>
