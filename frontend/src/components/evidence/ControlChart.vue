<script setup>
import { computed } from 'vue'
import EvidenceValue from './EvidenceValue.vue'
import AuditLine from './AuditLine.vue'
import { renderState, RENDER_STATES } from '../../utils/evidence'

// An SPC / EWMA control chart. `evidence.value` is the `structure` shape
// from docs/EVIDENCE_CONTRACT.md §4: { points, center, ucl, lcl }, where
// points is [{ x, y, label?, signal? }]. Signalled points (interval_kind
// "control-limits" is a decision boundary, not an estimate) are drawn larger
// and in --accent; everything else is the series colour.

const props = defineProps({
  evidence: {
    type: Object,
    default: null
  },
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  }
})

const W = 760
const H = 260
const L = 48
const R = 16
const T = 18
const B = 38

const state = computed(() => renderState(props.evidence))
const struct = computed(() => props.evidence?.value || null)
const hasChart = computed(() => {
  const s = struct.value
  return !!(s && Array.isArray(s.points) && s.points.length && typeof s.center === 'number')
})

const yDomain = computed(() => {
  const s = struct.value
  const ys = s.points.map((p) => p.y).concat([s.ucl, s.lcl])
  const lo = Math.min(...ys)
  const hi = Math.max(...ys)
  const pad = (hi - lo) * 0.15 || 1
  return [lo - pad, hi + pad]
})

function X(i) {
  const n = struct.value.points.length
  return L + (n <= 1 ? 0 : (i / (n - 1)) * (W - L - R))
}
function Y(v) {
  const [lo, hi] = yDomain.value
  return T + (1 - (v - lo) / (hi - lo)) * (H - T - B)
}

const linePath = computed(() => {
  if (!hasChart.value) return ''
  return struct.value.points.map((p, i) => `${i ? 'L' : 'M'}${X(i)},${Y(p.y)}`).join(' ')
})

const signalledPoints = computed(() => {
  if (!hasChart.value) return []
  const s = struct.value
  const signalIdx = new Set(s.signals || [])
  return s.points
    .map((p, i) => ({ ...p, i, signal: p.signal || signalIdx.has(i) }))
    .filter((p) => p.signal)
})
</script>

<template>
  <div class="card">
    <div class="chead">
      <div>
        <h3>{{ title }}</h3>
        <div v-if="subtitle" class="sub">{{ subtitle }}</div>
      </div>
      <span
        class="pill"
        :class="{
          'p-est': state === 'estimate',
          'p-qual': state === 'qualified',
          'p-hold': state === 'not-interpretable',
          'p-wait': state === 'insufficient-data'
        }"
      >{{ signalledPoints.length ? signalledPoints.length + ' signal' + (signalledPoints.length > 1 ? 's' : '') : (state === 'estimate' ? 'Estimate' : state === 'qualified' ? 'Qualified' : state === 'not-interpretable' ? 'Withheld' : 'Waiting') }}</span>
    </div>

    <template v-if="state === RENDER_STATES.INSUFFICIENT_DATA || state === RENDER_STATES.NOT_INTERPRETABLE || !hasChart">
      <EvidenceValue :evidence="evidence" />
    </template>

    <template v-else>
      <svg class="chart" viewBox="0 0 760 260" preserveAspectRatio="none" role="img"
        :aria-label="title + ' control chart with centre line and control limits'">
        <line :x1="L" :y1="Y(struct.ucl)" :x2="W - R" :y2="Y(struct.ucl)" stroke="var(--limit)" stroke-width="1.6" stroke-dasharray="6 4" />
        <line :x1="L" :y1="Y(struct.lcl)" :x2="W - R" :y2="Y(struct.lcl)" stroke="var(--limit)" stroke-width="1.6" stroke-dasharray="6 4" />
        <line :x1="L" :y1="Y(struct.center)" :x2="W - R" :y2="Y(struct.center)" stroke="var(--ink-4)" stroke-width="1.4" />
        <text :x="W - R" :y="Y(struct.ucl) - 8" text-anchor="end" fill="var(--limit)">UCL {{ struct.ucl }}</text>
        <text :x="W - R" :y="Y(struct.lcl) + 16" text-anchor="end" fill="var(--limit)">LCL {{ struct.lcl }}</text>

        <path :d="linePath" fill="none" stroke="var(--s1)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" />

        <template v-for="(p, i) in struct.points" :key="'pt-' + i">
          <circle
            :cx="X(i)" :cy="Y(p.y)"
            :r="p.signal || (struct.signals || []).includes(i) ? 6 : 3.2"
            :fill="p.signal || (struct.signals || []).includes(i) ? 'var(--accent)' : 'var(--chart)'"
            :stroke="p.signal || (struct.signals || []).includes(i) ? 'var(--accent)' : 'var(--s1)'"
            stroke-width="2"
          />
        </template>

        <text
          v-for="p in signalledPoints" :key="'sig-label-' + p.i"
          :x="X(p.i)" :y="Y(p.y) - 14" text-anchor="middle" fill="var(--ink-2)"
        >{{ p.label || p.y }}</text>
      </svg>

      <div class="legend">
        <span><i style="background:var(--s1)"></i>series</span>
        <span><i style="background:var(--ink-4)"></i>centre {{ struct.center }}</span>
        <span><i style="background:var(--limit)"></i>limits {{ struct.lcl }} / {{ struct.ucl }}</span>
        <span v-if="signalledPoints.length"><i style="background:var(--accent)"></i>signalled</span>
      </div>
    </template>

    <div v-if="evidence && evidence.method" class="tile-foot">
      <AuditLine :evidence="evidence" />
    </div>
  </div>
</template>
