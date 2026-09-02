<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import AuditLine from '../components/evidence/AuditLine.vue'
import WhyDisclosure from '../components/evidence/WhyDisclosure.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { governancePack } from '../fixtures/insights'

// TODO(frontend): still fixture-backed, same reason as
// InsightsOperationsView.vue.
const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const pack = computed(() => governancePack[slug.value])
const clusters = computed(() => pack.value.segmentation.evidence.value.clusters)
const rows = computed(() => pack.value.isolation.evidence.value.rows)
</script>

<template>
  <TenantShell title="Segmentation & network" subtitle="Pack 04 · Voice" as-of="insight_run · contract v1">
    <div class="callout callout-info">
      <span>
        <b>k-anonymity floor: 5.</b>
        Every per-stratum figure below is suppressed, not noised, when its cell falls under that count.
        See <router-link :to="`/t/${slug}/decisions`">{{ tenant.labels.decision.toLowerCase() }}s</router-link> for the vote-tabulation side of this pack.
      </span>
    </div>

    <div class="card">
      <div class="chead">
        <div><h3>{{ pack.segmentation.title }}</h3><div class="sub">{{ pack.segmentation.subtitle }}</div></div>
        <span class="pill p-est">Estimate</span>
      </div>
      <div class="tbl-scroll">
        <table class="tbl">
          <thead><tr><th>Segment</th><th class="r">n</th><th class="r">Share</th></tr></thead>
          <tbody>
            <tr v-for="c in clusters" :key="c.label">
              <td class="nm">{{ c.label }}</td>
              <td class="r num">{{ c.n }}</td>
              <td class="r num">{{ (c.share * 100).toFixed(0) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
      <AuditLine :evidence="pack.segmentation.evidence" />
    </div>

    <div class="card">
      <div class="chead">
        <div><h3>{{ pack.isolation.title }}</h3><div class="sub">{{ pack.isolation.subtitle }}</div></div>
        <span class="pill p-qual">Aggregate only</span>
      </div>
      <div class="tbl-scroll">
        <table class="tbl">
          <thead><tr><th></th><th class="r">n</th><th class="r">Isolated share</th></tr></thead>
          <tbody>
            <tr v-for="r in rows" :key="r.stratum">
              <td class="nm">{{ r.stratum }}</td>
              <td class="r num dim">{{ r.n }}</td>
              <td class="r num">
                <span v-if="r.suppressed" class="dim">suppressed, n &lt; 5</span>
                <span v-else>{{ (r.share * 100).toFixed(0) }}%</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <WhyDisclosure label="Why this can never list individuals">
        <p>{{ pack.isolation.privacyNote }}</p>
      </WhyDisclosure>
      <AuditLine :evidence="pack.isolation.evidence" />
    </div>
  </TenantShell>
</template>
