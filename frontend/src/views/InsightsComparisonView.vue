<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import AuditLine from '../components/evidence/AuditLine.vue'
import WhyDisclosure from '../components/evidence/WhyDisclosure.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { comparisonPack } from '../fixtures/insights'

// TODO(frontend): still fixture-backed. Pack 2 (bayes_ranking) has no
// implemented statistician services yet at all (CONTEXT.md), so this pack
// specifically has nothing real to call.
const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const board = computed(() => comparisonPack[slug.value].leaderboard)
const rows = computed(() => board.value.evidence.value.rows)

function pct(x) {
  return (x * 100).toFixed(1) + '%'
}
</script>

<template>
  <TenantShell title="Leaderboard" subtitle="Pack 02 · Comparison" as-of="insight_run · contract v1">
    <div class="row" style="grid-template-columns:1fr">
      <div class="card">
        <div class="chead">
          <div><h3>{{ board.title }}</h3><div class="sub">{{ board.subtitle }}</div></div>
          <span class="pill p-est">Beta-binomial</span>
        </div>
        <div class="tbl-scroll">
          <table class="tbl">
            <thead><tr><th></th><th>Vendor</th><th class="r">Raw</th><th class="r">Shrunk</th><th>Posterior 95%</th><th class="r">n</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in rows" :key="r.name">
                <td class="rk">{{ i + 1 }}</td>
                <td class="nm">{{ r.name }}<span v-if="r.flag" class="flag">{{ r.flag }}</span></td>
                <td class="r dim">{{ pct(r.raw) }}</td>
                <td class="r num">{{ pct(r.shrunk) }}</td>
                <td>
                  <div class="shr">
                    <span class="track"></span>
                    <span class="ci" :style="{ left: r.interval[0] * 100 + '%', width: (r.interval[1] - r.interval[0]) * 100 + '%' }"></span>
                    <span class="pt" :style="{ left: r.shrunk * 100 + '%' }"></span>
                    <span class="raw" :style="{ left: r.raw * 100 + '%' }"></span>
                  </div>
                </td>
                <td class="r dim">{{ r.closed }}/{{ r.total }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <WhyDisclosure label="Why the top raw rate is not first">
          <p>{{ board.why }}</p>
        </WhyDisclosure>
        <AuditLine :evidence="board.evidence" />
      </div>
    </div>
  </TenantShell>
</template>
