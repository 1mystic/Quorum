<script setup>
import { computed } from 'vue'
import StatusPill from './StatusPill.vue'
import ClubIcon from './ClubIcon.vue'
import { bannerColourFor, iconNameFor } from '../../utils/clubVisuals'

const props = defineProps({
  proposals: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

// Club status as the API reports it, mapped onto the approval-card states
// that already exist, so these rows look like the admin's approval queue
// rather than a second visual language for the same idea.
const STATUS_META = {
  PENDING: { state: 'pending', label: 'Pending approval' },
  ACTIVE: { state: 'approved', label: 'Approved' },
  REJECTED: { state: 'rejected', label: 'Not approved' },
  ARCHIVED: { state: 'rejected', label: 'Archived' }
}

function metaFor(status) {
  return STATUS_META[String(status || '').toUpperCase()] || STATUS_META.PENDING
}

function formatDate(value) {
  if (!value) return ''

  return new Date(value).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

function metaLine(proposal) {
  const parts = [proposal.category]

  if (proposal.type) {
    parts.push(proposal.type)
  }

  if (proposal.member_count !== undefined && proposal.member_count !== null) {
    parts.push(`${proposal.member_count} members`)
  }

  if (proposal.created_at) {
    parts.push(`Submitted ${formatDate(proposal.created_at)}`)
  }

  return parts.filter(Boolean).join(' · ')
}

const hasProposals = computed(function checkAny() {
  return props.proposals.length > 0
})
</script>

<template>
  <section class="proposal-stack">
    <div class="issue-feed-header">
      <h2 class="clubs-section-title">Your club proposals</h2>
      <StatusPill
        v-if="hasProposals"
        status="pending"
        :label="proposals.length + ' submitted'"
      />
    </div>

    <p v-if="loading" class="text-note">Loading your proposals...</p>

    <p v-else-if="!hasProposals" class="text-note">
      You have not proposed a club yet. Once you submit the form above, it will
      appear here with its approval status.
    </p>

    <div v-else class="approval-list">
      <div
        v-for="proposal in proposals"
        :key="proposal.id"
        class="approval-card"
        :class="{
          approved: metaFor(proposal.status).state === 'approved',
          rejected: metaFor(proposal.status).state === 'rejected'
        }"
      >
        <div class="approval-club-icon" :class="bannerColourFor(proposal)">
          <ClubIcon :name="iconNameFor(proposal)" />
        </div>

        <div class="approval-info">
          <p class="approval-club-name">{{ proposal.name }}</p>
          <p class="approval-meta">{{ metaLine(proposal) }}</p>
        </div>

        <div class="approval-actions">
          <StatusPill
            :status="metaFor(proposal.status).state"
            :label="metaFor(proposal.status).label"
          />
        </div>
      </div>
    </div>
  </section>
</template>
