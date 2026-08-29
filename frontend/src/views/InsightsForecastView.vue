<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import AuditLine from '../components/evidence/AuditLine.vue'
import { renderState } from '../utils/evidence'
import { tenantBySlug } from '../fixtures/tenants'
import { forecastPack } from '../fixtures/insights'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const pack = computed(() => forecastPack[slug.value])

const forecastEvidence = computed(() => pack.value.forecast.evidence)
const forecastState = computed(() => renderState(forecastEvidence.value))
const history = computed(() => forecastEvidence.value.value?.history || [])
const forecastPoint = computed(() => forecastEvidence.value.value?.forecast?.[0])

const buckets = computed(() => pack.value.etaDistribution.evidence.value?.buckets || [])
const maxBucket = computed(() => Math.max(1, ...buckets.value.map((b) => b.n)))
</script>

<template>
  <TenantShell title="Forecast" subtitle="Pack 03 · Foresight" as-of="insight_run · contract v1">
    <div class="row r-32">
      <div class="card">
        <div class="chead">
          <div><h3>{{ pack.forecast.title }}</h3><div class="sub">{{ pack.forecast.subtitle }}</div></div>
          <span class="pill" :class="forecastState === 'estimate' ? 'p-est' : forecastState === 'qualified' ? 'p-qual' : 'p-wait'">
            {{ forecastState === 'estimate' ? 'Estimate' : forecastState === 'qualified' ? 'Qualified' : 'Waiting' }}
          </span>
        </div>

        <template v-if="forecastState !== 'insufficient-data'">
          <div class="big">{{ forecastPoint }}<span class="u">{{ forecastEvidence.unit }}</span></div>
          <div class="meta">
            <span><b>n</b> {{ forecastEvidence.n }} periods</span>
            <span><b>predictive 80</b> {{ forecastEvidence.interval?.[0] }}–{{ forecastEvidence.interval?.[1] }}</span>
          </div>
          <div class="legend" style="margin-top:var(--sp2)">
            <span v-for="(h, i) in history" :key="i" class="mono" style="min-width:20px;text-align:center">{{ h }}</span>
          </div>
          <p v-if="forecastEvidence.checks.length" class="check-detail">{{ forecastEvidence.checks[0].label }}. {{ forecastEvidence.checks[0].detail }}</p>
          <AuditLine :evidence="forecastEvidence" />
        </template>
        <div v-else class="stat-tile-empty">
          <div class="wait-num">{{ forecastEvidence.n }}<span> / {{ forecastEvidence.min_n }} needed</span></div>
          <p>Not enough seasonal cycles yet to forecast.</p>
        </div>
      </div>

      <StatTile :title="pack.calibration.title" :subtitle="pack.calibration.subtitle" :evidence="pack.calibration.evidence">
        <template #why><p>{{ pack.calibration.why }}</p></template>
      </StatTile>
    </div>

    <div class="card">
      <div class="chead"><div><h3>{{ pack.etaDistribution.title }}</h3><div class="sub">{{ pack.etaDistribution.subtitle }}</div></div></div>
      <div style="display:flex;align-items:flex-end;gap:var(--sp4);height:140px">
        <div v-for="b in buckets" :key="b.label" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;justify-content:flex-end;height:100%">
          <div class="mono" style="font-size:12px">{{ b.n }}</div>
          <div :style="{ width: '100%', height: (b.n / maxBucket * 100) + '%', background: 'var(--s1)', borderRadius: '4px 4px 0 0', minHeight: '4px' }"></div>
          <div class="mono" style="font-size:11px;color:var(--ink-3)">{{ b.label }}</div>
        </div>
      </div>
      <AuditLine :evidence="pack.etaDistribution.evidence" />
    </div>
  </TenantShell>
</template>
