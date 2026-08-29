<script setup>
import { computed } from 'vue'
import EvidenceValue from './EvidenceValue.vue'
import AuditLine from './AuditLine.vue'
import { renderState, RENDER_STATES } from '../../utils/evidence'

// The KPI card: big tabular number, meta strip, and the long explanation
// behind a closed <details> disclosure. Matches design/samples/quorum/dashboard.html
// exactly - the disclosure is deliberate, review feedback was that always-on
// prose read as clutter, but the Evidence contract still requires the
// explanation to be present (docs/EVIDENCE_CONTRACT.md, obligations by layer).

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
  display: {
    type: String,
    default: 'scalar'
  },
  whySummary: {
    type: String,
    default: 'Why this reading'
  },
  muted: {
    type: Boolean,
    default: false
  }
})

const state = computed(() => renderState(props.evidence))

const pillLabel = {
  [RENDER_STATES.ESTIMATE]: 'Estimate',
  [RENDER_STATES.QUALIFIED]: 'Qualified',
  [RENDER_STATES.NOT_INTERPRETABLE]: 'Withheld',
  [RENDER_STATES.INSUFFICIENT_DATA]: 'Waiting'
}

const pillClass = {
  [RENDER_STATES.ESTIMATE]: 'p-est',
  [RENDER_STATES.QUALIFIED]: 'p-qual',
  [RENDER_STATES.NOT_INTERPRETABLE]: 'p-hold',
  [RENDER_STATES.INSUFFICIENT_DATA]: 'p-wait'
}
</script>

<template>
  <div class="card" :class="{ muted: muted || state === RENDER_STATES.INSUFFICIENT_DATA }">
    <div class="chead">
      <div>
        <h3>{{ title }}</h3>
        <div v-if="subtitle" class="sub">{{ subtitle }}</div>
      </div>
      <span class="pill" :class="pillClass[state]">{{ pillLabel[state] }}</span>
    </div>

    <EvidenceValue :evidence="evidence" :display="display" />

    <details v-if="$slots.why" class="why">
      <summary>{{ whySummary }}</summary>
      <div class="body">
        <slot name="why" />
      </div>
    </details>

    <AuditLine v-if="evidence && evidence.method" :evidence="evidence" />
  </div>
</template>
