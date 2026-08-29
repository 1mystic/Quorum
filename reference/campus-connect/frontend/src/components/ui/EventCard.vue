<script setup>
import { Clock, MapPin, Users } from 'lucide-vue-next'

defineProps({
  event: { type: Object, required: true }
})

const emit = defineEmits(['open'])

const statusLabels = {
  upcoming: 'Upcoming',
  ongoing: 'Ongoing',
  registered: 'Registered',
  past: 'Past'
}

function openEvent() {
  emit('open')
}

// Unlimited-capacity events have capacity=null, which the template used to
// render as a bare "X /" with nothing after the slash - this matches
// LeaderEventsView's own countText() helper for the same field.
function countText(event) {
  if (event.capacity === null || event.capacity === undefined) {
    return `${event.registered} registered`
  }
  return `${event.registered} / ${event.capacity}`
}
</script>

<template>
  <div class="event-card" @click="openEvent">
    <div class="event-card-accent" :class="event.accent"></div>
    <div class="event-card-date-box">
      <span class="event-date-day">{{ event.day }}</span>
      <span class="event-date-month">{{ event.month }}</span>
    </div>
    <div class="event-card-body">
      <div>
        <p class="event-card-title">{{ event.title }}</p>
        <p class="event-card-club">{{ event.club }}</p>
        <div class="event-card-meta">
          <span><Clock /> {{ event.time }}</span>
          <span><MapPin /> {{ event.venue }}</span>
        </div>
      </div>
      <div class="event-card-footer">
        <span
          class="event-status"
          :class="event.status"
        >{{ statusLabels[event.status] }}</span>
        <span class="club-card-members"><Users /> {{ countText(event) }}</span>
      </div>
    </div>
  </div>
</template>
