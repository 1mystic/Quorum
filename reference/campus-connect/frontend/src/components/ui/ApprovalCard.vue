<script setup>
import { Check, X, FileText } from 'lucide-vue-next'
import StatusPill from './StatusPill.vue'
import ClubIcon from './ClubIcon.vue'

defineProps({
  approval: { type: Object, required: true },
  metaField: { type: String, default: 'meta' },
  busy: { type: Boolean, default: false }
})

const emit = defineEmits(['approve', 'reject'])

const statusLabels = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected'
}

function approveClub() {
  emit('approve')
}

function rejectClub() {
  emit('reject')
}
</script>

<template>
  <div
    class="approval-card"
    :class="{ approved: approval.status === 'approved', rejected: approval.status === 'rejected' }"
  >
    <div class="approval-club-icon" :class="approval.banner">
      <ClubIcon :name="approval.icon" />
    </div>
    <div class="approval-info">
      <p class="approval-club-name">{{ approval.name }}</p>
      <p class="approval-meta">{{ approval[metaField] }}</p>
    </div>
    <div class="approval-actions">
      <a
        v-if="approval.applicationLink"
        :href="approval.applicationLink"
        target="_blank"
        rel="noopener"
        class="approval-app-link"
      >
        <FileText /> View Application
      </a>
      <template v-if="approval.status === 'pending'">
        <StatusPill status="pending" label="Pending" />
        <button class="btn-success" :disabled="busy" @click="approveClub">
          <span v-if="busy" class="btn-spinner"></span>
          <template v-else><Check /> Approve</template>
        </button>
        <button class="btn-danger" :disabled="busy" @click="rejectClub">
          <span v-if="busy" class="btn-spinner"></span>
          <template v-else><X /> Reject</template>
        </button>
      </template>
      <StatusPill v-else :status="approval.status" :label="statusLabels[approval.status]" />
    </div>
  </div>
</template>
