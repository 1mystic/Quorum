<script setup>
import { computed } from 'vue'
import {
  renderState,
  blockingCheck,
  qualifyingChecks,
  formatInterval,
  intervalLabel,
  RENDER_STATES
} from '../../utils/evidence'

// The one component allowed to render a figure from an Evidence envelope.
// Takes `evidence: Evidence`, never `value: number` - see docs/EVIDENCE_CONTRACT.md
// section 3, and docs/RULES.md section 4. Handles all four render states; which one applies
// is decided entirely by the data.
//
// `display="range"` shows the interval bounds as the headline figure instead
// of a point value - the shape a conformal or predictive interval takes,
// since there is deliberately no single point being asserted (see the
// dashboard sample's ETA card). Ambiguous in the contract as written; this
// is the frontend's reading of it, flagged in the report.

const props = defineProps({
  evidence: {
    type: Object,
    default: null
  },
  display: {
    type: String,
    default: 'scalar',
    validator: (v) => ['scalar', 'range'].includes(v)
  },
  precision: {
    type: Number,
    default: null
  }
})

const state = computed(() => renderState(props.evidence))
const isEstimate = computed(() => state.value === RENDER_STATES.ESTIMATE)
const isQualified = computed(() => state.value === RENDER_STATES.QUALIFIED)
const isSuppressed = computed(() => state.value === RENDER_STATES.NOT_INTERPRETABLE)
const isInsufficient = computed(() => state.value === RENDER_STATES.INSUFFICIENT_DATA)

const blocking = computed(() => blockingCheck(props.evidence))
const qualifiers = computed(() => qualifyingChecks(props.evidence))

function fmt(v) {
  if (v === null || v === undefined) return ''
  if (props.precision !== null && typeof v === 'number') return v.toFixed(props.precision)
  return v
}

const rangeLow = computed(() => props.evidence?.interval?.[0])
const rangeHigh = computed(() => props.evidence?.interval?.[1])
const interval = computed(() => formatInterval(props.evidence))
const intervalKindLabel = computed(() => intervalLabel(props.evidence?.interval_kind))

const need = computed(() => {
  // The Method Card owns the real min_n per method; this is a calm fallback
  // when the envelope itself does not carry one.
  return props.evidence?.min_n || null
})
</script>

<template>
  <div class="evidence-value" :class="'ev-' + state">
    <!-- insufficient data: calm, deliberate, never an error -->
    <div v-if="isInsufficient" class="stat-tile-empty">
      <div class="wait-num">
        {{ evidence?.n ?? 0 }}<span v-if="need"> / {{ need }} needed</span>
      </div>
      <p>
        Not enough data yet. Quorum needs more observations before this reading is
        trustworthy<span v-if="need">, has {{ evidence?.n ?? 0 }} of {{ need }}</span>.
      </p>
    </div>

    <!-- not interpretable: value suppressed, blocking check explained -->
    <template v-else-if="isSuppressed">
      <div class="withheld">value suppressed</div>
      <p v-if="blocking" class="check-detail">{{ blocking.detail || blocking.label }}</p>
    </template>

    <!-- qualified or estimate: value always shown, qualifiers shown inline -->
    <template v-else>
      <div v-if="display === 'range' && evidence?.interval" class="big range">
        {{ fmt(rangeLow) }}<i></i>{{ fmt(rangeHigh) }}<span v-if="evidence.unit" class="u">{{ evidence.unit }}</span>
      </div>
      <div v-else class="big">
        {{ fmt(evidence?.value) }}<span v-if="evidence?.unit" class="u">{{ evidence.unit }}</span>
      </div>

      <div class="meta">
        <span><b>n</b> {{ evidence?.n }}</span>
        <span v-if="evidence?.interval && display !== 'range'">
          <b>{{ intervalKindLabel || 'interval' }}</b> {{ interval }}
        </span>
        <span v-if="evidence?.n_censored"><b>censored</b> {{ evidence.n_censored }}</span>
        <span v-if="evidence?.n_excluded"><b>excluded</b> {{ evidence.n_excluded }} ({{ evidence.exclusion_reason }})</span>
      </div>

      <p v-if="isQualified" class="check-detail">
        <template v-for="check in qualifiers" :key="check.id">
          {{ check.label }}<template v-if="check.detail">. {{ check.detail }}</template>
        </template>
      </p>
    </template>
  </div>
</template>
