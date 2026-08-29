<script setup>
import { Award, ExternalLink } from 'lucide-vue-next'

defineProps({
  cert: { type: Object, required: true }
})

const RESULT_LABELS = {
  WINNER: 'Winner',
  RUNNER_UP: 'Runner-up',
  PARTICIPANT: 'Participant'
}

function resultLabel(result) {
  return RESULT_LABELS[result] || result
}

function resultClass(result) {
  return String(result || '').toLowerCase().replace('_', '-')
}

function formatDate(value) {
  if (!value) return ''

  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}
</script>

<template>
  <div class="cert-card">
    <p class="cert-event-name">{{ cert.event_title }}</p>
    <p class="cert-club-tag">{{ cert.club_name }} · {{ formatDate(cert.issued_at) }}</p>
    <div class="result-badge" :class="resultClass(cert.result)">
      <Award /> {{ resultLabel(cert.result) }}
    </div>
    <div class="cert-footer">
      <span class="cert-serial">{{ cert.serial }}</span>
      <router-link
        :to="{ name: 'view-cert', params: { serial: cert.serial } }"
        target="_blank"
        class="cert-verify-link"
      >
        View <ExternalLink />
      </router-link>
    </div>
  </div>
</template>
