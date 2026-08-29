<script setup>
import { CheckCircle2, Clock3, MessageSquare } from 'lucide-vue-next'
import StatusPill from './StatusPill.vue'

defineProps({
  issue: { type: Object, required: true }
})
</script>

<template>
  <div class="issue-card" :class="{ resolved: issue.status === 'resolved' }">
    <div class="issue-top">
      <p class="issue-title">{{ issue.title }}</p>
      <StatusPill :status="issue.status" :label="issue.statusLabel" />
    </div>
    <p class="issue-meta">{{ issue.meta }}</p>

    <!-- The exchange reads top to bottom: what the student asked, then what
         the club leader said back. Before this, a reply appeared as a loose
         block with no sense of who said what. -->
    <div class="issue-thread">
      <div class="issue-bubble issue-bubble-mine">
        <p class="issue-bubble-who">
          <MessageSquare /> You asked
        </p>
        <p class="issue-desc">{{ issue.desc }}</p>
      </div>

      <div v-if="issue.response" class="issue-response">
        <p class="issue-response-label">
          <CheckCircle2 />
          {{ issue.response.by }} replied
          <span v-if="issue.response.atLabel" class="issue-bubble-when">
            · {{ issue.response.atLabel }}
          </span>
        </p>
        <p class="issue-response-text">{{ issue.response.text }}</p>
      </div>

      <p v-else class="issue-awaiting">
        <Clock3 /> Waiting for the club leader to reply.
      </p>
    </div>

    <div class="issue-footer">
      <span v-for="tag in issue.tags" :key="tag" class="announce-tag">{{ tag }}</span>
    </div>
    <slot name="actions"></slot>
  </div>
</template>
