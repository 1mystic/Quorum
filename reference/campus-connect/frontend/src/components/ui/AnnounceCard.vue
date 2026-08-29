<script setup>
import { Pin } from 'lucide-vue-next'
import ClubIcon from './ClubIcon.vue'

const props = defineProps({
  announcement: { type: Object, required: true }
})

function formatTime(dateString) {
  return new Date(dateString).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

function labelForCategory(category) {
  switch (category) {
    case 'GENERAL':
    case 'general':
      return 'General'

    case 'EVENT_UPDATE':
    case 'event_update':
      return 'Event Update'

    case 'RESOURCE':
    case 'resource':
      return 'Resource'

    case 'ACHIEVEMENT':
    case 'achievement':
      return 'Achievement'

    case 'URGENT':
    case 'urgent':
      return 'Urgent'

    default:
      return category
  }
}

function iconForCategory(category) {
  switch (category) {
    case 'GENERAL':
    case 'general':
      return 'megaphone'

    case 'EVENT_UPDATE':
    case 'event_update':
      return 'calendar'

    case 'RESOURCE':
    case 'resource':
      return 'book'

    case 'ACHIEVEMENT':
    case 'achievement':
      return 'trophy'

    case 'URGENT':
    case 'urgent':
      return 'alert-circle'

    default:
      return 'megaphone'
  }
}

// Every card used to hardcode the same blue dot regardless of category,
// which made a feed of five different announcement types look identical at
// a glance. One colour per category instead.
function bannerForCategory(category) {
  switch (category) {
    case 'GENERAL':
    case 'general':
      return 'banner-blue'

    case 'EVENT_UPDATE':
    case 'event_update':
      return 'banner-green'

    case 'RESOURCE':
    case 'resource':
      return 'banner-mint'

    case 'ACHIEVEMENT':
    case 'achievement':
      return 'banner-yellow'

    case 'URGENT':
    case 'urgent':
      return 'banner-pink'

    default:
      return 'banner-blue'
  }
}

</script>

<template>
  <div class="announce-card" :class="{ pinned: announcement.pinned }">
    <span v-if="announcement.pinned" class="announce-pin-mark">
      <Pin />
    </span>
    <div v-else-if="announcement.unread" class="announce-unread-dot"></div>
    <div class="announce-club-row">
      <div class="announce-dot" :class="bannerForCategory(announcement.category)">
        <ClubIcon :name="iconForCategory(announcement.category)" />
      </div>
      <div class="announce-club-info">
        <p class="announce-club-name">{{ announcement.club_name }}</p>
        <p class="announce-time">{{ formatTime(announcement.created_at) }}</p>
      </div>
    </div>
    <p class="announce-title">{{ announcement.title }}</p>
    <p class="announce-body">{{ announcement.body }}</p>
    <div class="announce-footer">
      <span class="announce-tag">
        {{ labelForCategory(announcement.category) }}
      </span>
    </div>
    <slot name="actions"></slot>
  </div>
</template>
