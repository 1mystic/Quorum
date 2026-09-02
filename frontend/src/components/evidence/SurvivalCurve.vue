<script setup>
import { computed } from 'vue'
import EvidenceValue from './EvidenceValue.vue'
import AuditLine from './AuditLine.vue'
import { renderState, RENDER_STATES } from '../../utils/evidence'

// A Kaplan-Meier step curve with its Greenwood confidence band, censoring
// ticks and median crosshair. Inline SVG, no chart library.
//
// `evidence.value` is the `series` shape from docs/EVIDENCE_CONTRACT.md §4:
// { x, y, lo, hi, censor_x }. A band is not optional - a survival curve
// without one is a lie of omission, so this component refuses to draw the
// step line without matching lo/hi arrays.

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
  },
  xUnit: {
    type: String,
    default: 'd'
  }
})

const W = 760
const H = 300
const L = 54
const R = 16
const T = 14
const B = 40

const state = computed(() => renderState(props.evidence))
const series = computed(() => props.evidence?.value || null)
const hasBand = computed(() => {
  const s = series.value
  return !!(s && Array.isArray(s.x) && Array.isArray(s.y) && Array.isArray(s.lo) && Array.isArray(s.hi))
})

const xMax = computed(() => {
  const s = series.value
  if (!s || !s.x.length) return 1
  return s.x[s.x.length - 1] || 1
})

function X(v) {
  return L + (v / xMax.value) * (W - L - R)
}
function Y(v) {
  return T + (1 - v) * (H - T - B)
}

function stepPath(ys) {
  const s = series.value
  let d = ''
  for (let i = 0; i < s.x.length; i++) {
    if (i) d += ` L${X(s.x[i])},${Y(ys[i - 1])}`
    d += `${i ? ' L' : 'M'}${X(s.x[i])},${Y(ys[i])}`
  }
  return d
}

const linePath = computed(() => (hasBand.value ? stepPath(series.value.y) : ''))

const bandPath = computed(() => {
  if (!hasBand.value) return ''
  const s = series.value
  let up = ''
  let dn = ''
  for (let i = 0; i < s.x.length; i++) {
    if (i) up += ` L${X(s.x[i])},${Y(s.hi[i - 1])}`
    up += `${i ? ' L' : 'M'}${X(s.x[i])},${Y(s.hi[i])}`
  }
  for (let j = s.x.length - 1; j >= 0; j--) {
    dn += ` L${X(s.x[j])},${Y(s.lo[j])}`
    if (j) dn += ` L${X(s.x[j])},${Y(s.lo[j - 1])}`
  }
  return up + dn + ' Z'
})

const gridLines = [1, 0.75, 0.5, 0.25, 0]

const censorTicks = computed(() => {
  const s = series.value
  if (!s || !Array.isArray(s.censor_x)) return []
  return s.censor_x.map((cx) => {
    // survival level at cx: last step at or before cx
    let level = 1
    for (let i = 0; i < s.x.length; i++) {
      if (s.x[i] <= cx) level = s.y[i]
      else break
    }
    return { x: X(cx), y: Y(level) }
  })
})

// median: first x where survival drops to or below 0.5, read off the step
const median = computed(() => {
  const s = series.value
  if (!s) return null
  for (let i = 0; i < s.x.length; i++) {
    if (s.y[i] <= 0.5) return s.x[i]
  }
  return null
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
      >{{ state === 'estimate' ? 'Estimate' : state === 'qualified' ? 'Qualified' : state === 'not-interpretable' ? 'Withheld' : 'Waiting' }}</span>
    </div>

    <template v-if="state === RENDER_STATES.INSUFFICIENT_DATA || state === RENDER_STATES.NOT_INTERPRETABLE || !hasBand">
      <EvidenceValue :evidence="evidence" />
    </template>

    <template v-else>
      <svg class="chart" viewBox="0 0 760 300" preserveAspectRatio="none" role="img"
        :aria-label="title + ' survival curve with confidence band'">
        <g v-for="v in gridLines" :key="'grid-' + v">
          <line :x1="L" :y1="Y(v)" :x2="W - R" :y2="Y(v)" stroke="var(--grid)" stroke-width="1" />
          <text :x="L - 10" :y="Y(v) + 4" text-anchor="end">{{ Math.round(v * 100) }}{{ v === 1 ? '%' : '' }}</text>
        </g>

        <path :d="bandPath" fill="var(--s1)" :fill-opacity="0.16" />
        <path :d="linePath" fill="none" stroke="var(--s1)" stroke-width="2.6" stroke-linejoin="round" />

        <line
          v-for="(tick, i) in censorTicks"
          :key="'censor-' + i"
          :x1="tick.x" :y1="tick.y - 6" :x2="tick.x" :y2="tick.y + 6"
          stroke="var(--ink-4)" stroke-width="1.6"
        />

        <g v-if="median !== null">
          <line :x1="L" :y1="Y(0.5)" :x2="X(median)" :y2="Y(0.5)" stroke="var(--accent)" stroke-width="1.4" stroke-dasharray="4 4" />
          <line :x1="X(median)" :y1="Y(0.5)" :x2="X(median)" :y2="Y(0)" stroke="var(--accent)" stroke-width="1.4" stroke-dasharray="4 4" />
          <circle :cx="X(median)" :cy="Y(0.5)" r="4.5" fill="var(--accent)" />
          <text :x="X(median) + 10" :y="Y(0.5) - 9" fill="var(--ink-2)">median {{ median }} {{ xUnit }}</text>
        </g>
      </svg>

      <div class="legend">
        <span><i style="background:var(--s1)"></i>survival</span>
        <span><i style="background:color-mix(in srgb,var(--s1) 30%,transparent)"></i>95% band</span>
        <span v-if="censorTicks.length"><i style="background:var(--ink-4)"></i>censoring tick</span>
        <span v-if="median !== null"><i style="background:var(--accent)"></i>median {{ median }} {{ xUnit }}</span>
      </div>
    </template>

    <div v-if="evidence && evidence.method" class="tile-foot">
      <AuditLine :evidence="evidence" />
    </div>
  </div>
</template>
