<script setup>
import MethodCardLink from './MethodCardLink.vue'

// The audit line every Evidence-bearing card carries: the method id (linked
// to its Method Card) and the params_hash that makes the figure reproducible
// from a screenshot (docs/EVIDENCE_CONTRACT.md §7).

const props = defineProps({
  evidence: {
    type: Object,
    required: true
  }
})
</script>

<template>
  <div class="audit">
    <MethodCardLink :method="evidence.method" />
    <span v-if="evidence.n_censored">n {{ evidence.n }} · {{ evidence.n_censored }} censored</span>
    <span class="sp">{{ evidence.params_hash || evidence.insufficient_data ? (evidence.params_hash || 'insufficient_data') : '' }}</span>
  </div>
</template>
