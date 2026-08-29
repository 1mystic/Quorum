<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CalendarX } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import EventCard from '../components/ui/EventCard.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import { useEventsStore } from '../stores/events'
import { toast } from '../composables/useToast'
import { useChipFilter } from '../composables/useChipFilter'

const router = useRouter()
const route = useRoute()
const eventsStore = useEventsStore()

const filterChips = [
  { id: 'all', label: 'All Events' },
  { id: 'ongoing', label: 'Ongoing' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'registered', label: 'My Registrations' },
  { id: 'past', label: 'Past' }
]

const eventsList = computed(() => eventsStore.events)

const { activeFilter, filteredItems } = useChipFilter(eventsList, function matchesStatus(event, filter) {
  // A live event the member registered for now reads as 'ongoing', not
  // 'registered', so My Registrations matches the flag rather than the status
  // - otherwise registering for an event would make it vanish from the tab
  // the moment it started.
  if (filter === 'registered') return event.is_registered && event.status !== 'past'
  return event.status === filter
})

function openEvent(eventId) {
  router.push(`/${route.params.slug}/events/${eventId}`)
}

onMounted(async () => {
  try {
    await eventsStore.loadEvents()
  } catch (error) {
    console.error(error)
    toast.error(error?.message || 'Failed to load events.')
  }
})
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <Topbar title="Events" sub="Upcoming events across all your clubs" />

    <main class="content-body custom-scrollbar">

      <FilterChips :chips="filterChips" v-model="activeFilter" />

      <div class="events-grid">
        <EventCard
          v-for="event in filteredItems"
          :key="event.id"
          :event="event"
          @open="openEvent(event.id)"
        />
      </div>

      <div v-if="eventsStore.loading" class="page-loading-state">
        <div class="empty-state">
          <p>Loading events...</p>
        </div>
      </div>

      <div v-else-if="eventsStore.error" class="empty-state empty-state-wide">
        <CalendarX />
        <p>{{ eventsStore.error }}</p>
      </div>

      <div v-else-if="filteredItems.length === 0" class="empty-state empty-state-wide">
        <CalendarX />
        <p>No events match this filter.</p>
      </div>

    </main>

  </div>
</template>

