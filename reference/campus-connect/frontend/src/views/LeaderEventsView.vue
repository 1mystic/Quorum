<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { Plus, Clock, MapPin, Users, CalendarX, ClipboardCheck, Trophy, Send, Ban } from 'lucide-vue-next'
import LeaderSidebar from '../components/layout/LeaderSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import LeaderClubSwitcher from '../components/ui/LeaderClubSwitcher.vue'
import { getEvents, publishEvent, cancelEvent, normalizeEvent } from '../api/events'
import { useClubsStore } from '../stores/clubs'
import { cachedFetch, invalidateCache } from '../utils/apiCache'
import { toast } from '../composables/useToast'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const clubsStore = useClubsStore()

const club = ref(null)
const events = ref([])
const loading = ref(true)
const activeFilter = ref('all')

const filterChips = [
  { id: 'all', label: 'All Events' },
  { id: 'draft', label: 'Drafts' },
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'past', label: 'Past' },
  { id: 'cancelled', label: 'Cancelled' }
]

const statusLabels = {
  draft: 'Draft',
  upcoming: 'Upcoming',
  registered: 'Upcoming',
  past: 'Completed',
  cancelled: 'Cancelled'
}

const visibleEvents = computed(function filterEvents() {
  return events.value.filter(function matchesFilter(event) {
    if (activeFilter.value === 'all') return true
    if (activeFilter.value === 'upcoming') {
      return event.status === 'upcoming' || event.status === 'registered' || event.status === 'ongoing'
    }
    return event.status === activeFilter.value
  })
})

function statusPillClass(event) {
  if (event.isOngoing) return 'ongoing'
  if (event.status === 'registered') return 'upcoming'
  return event.status
}

function statusPillLabel(event) {
  return event.isOngoing ? 'Ongoing' : statusLabels[event.status]
}

function countText(event) {
  if (event.capacity === null || event.capacity === undefined) {
    return `${event.registered} registered`
  }
  return `${event.registered} / ${event.capacity}`
}

// Attendance opens once the event has started; results need attendance taken first.
function hasStarted(event) {
  return new Date(event.starts_at) <= new Date()
}

function canTakeAttendance(event) {
  return event.lifecycle === 'PUBLISHED' && hasStarted(event)
}

function canSetResults(event) {
  return event.lifecycle === 'PUBLISHED' && event.status === 'past'
}

// Both buttons stay clickable either way - a leader can still open either
// page once the event is done, just to look rather than change anything (a
// leader can no longer edit attendance/results at that point anyway). The
// label swap is what keeps that from reading as an offer to make changes.
function attendanceButtonLabel(event) {
  return event.status === 'past' ? 'View Attendance' : 'Take Attendance'
}

function resultsButtonLabel(event) {
  return event.results_declared ? 'View Results' : 'Set Results'
}

function goToAttendance(event) {
  router.push(`/${route.params.slug}/leader/events/${event.id}/attend`)
}

function goToResults(event) {
  router.push(`/${route.params.slug}/leader/events/${event.id}/results`)
}

function goToCreateEvent() {
  router.push(`/${route.params.slug}/leader/events/new`)
}

function goToEditEvent(event) {
  router.push(`/${route.params.slug}/leader/events/${event.id}/edit`)
}

// A club's two event lists go stale together: this page caches the whole
// list, LeaderClubView caches the upcoming-only slice under its own key,
// and CreateEventView drops both after it creates or edits an event.
function invalidateClubEvents(clubId) {
  invalidateCache(`leader-events:${clubId}`)
  invalidateCache(`club-upcoming-events:${clubId}`)
}

async function publish(event) {
  if (!event?.id) return
  try {
    const result = await publishEvent(event.id)
    toast.success(result.message)
    invalidateClubEvents(club.value.id)
    await loadEvents()
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  }
}

async function cancel(event) {
  if (!event?.id) return
  const confirmed = window.confirm(
    `Cancel "${event.title}"?\n\nRegistered members keep their registration but the event is closed.`
  )

  if (!confirmed) return

  try {
    const result = await cancelEvent(event.id)
    toast.success(result.message)
    invalidateClubEvents(club.value.id)
    await loadEvents()
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  }
}

function changeClub() {
  club.value = clubsStore.selectedLeaderClub
  loadEvents()
}

async function loadEvents() {
  if (!club.value) return

  loading.value = true

  try {
    const rows = await cachedFetch(
      `leader-events:${club.value.id}`,
      () => getEvents({ club_id: club.value.id })
    )
    events.value = rows.map(row => normalizeEvent(row))
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
    events.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await clubsStore.loadLeaderClubs()

    if (!clubsStore.selectedLeaderClub) {
      toast.error('No active club selected.')
      router.push(`/${auth.user.collegeSlug}/clubs`)
      return
    }

    club.value = clubsStore.selectedLeaderClub

    await loadEvents()

  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
    router.push(`/${auth.user.collegeSlug}/clubs`)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <LeaderSidebar />

  <div class="main-content">

    <Topbar title="Events" :sub="club ? club.name : 'Loading your club...'" :show-bell="false">
      <template #actions>
        <LeaderClubSwitcher @change="changeClub" />
        <button class="btn-primary" @click="goToCreateEvent">
          <Plus /> Create Event
        </button>
      </template>
    </Topbar>

    <main class="content-body custom-scrollbar">

      <FilterChips :chips="filterChips" v-model="activeFilter" />

      <div class="events-grid">
        <div v-for="event in visibleEvents" :key="event.id" class="event-card">
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
              <span class="event-status" :class="statusPillClass(event)">{{ statusPillLabel(event) }}</span>
              <span class="club-card-members"><Users /> {{ countText(event) }}</span>
            </div>

            <div class="event-card-manage-row">
              <button v-if="event.lifecycle !== 'CANCELLED'" class="btn-secondary-sm" @click="goToEditEvent(event)">Edit</button>
              <button
                v-if="event.lifecycle === 'DRAFT'"
                class="btn-secondary-sm"
                @click="publish(event)"
              >
                <Send /> Publish
              </button>
              <button
                v-if="canTakeAttendance(event)"
                class="btn-secondary-sm"
                @click="goToAttendance(event)"
              >
                <ClipboardCheck /> {{ attendanceButtonLabel(event) }}
              </button>
              <button
                v-if="canSetResults(event)"
                class="btn-secondary-sm"
                @click="goToResults(event)"
              >
                <Trophy /> {{ resultsButtonLabel(event) }}
              </button>
              <button
                v-if="event.lifecycle !== 'CANCELLED'"
                class="btn-secondary-sm"
                @click="cancel(event)"
              >
                <Ban /> Cancel
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="page-loading-state">
        <div class="empty-state">
          <p>Loading events...</p>
        </div>
      </div>

      <div v-else-if="visibleEvents.length === 0" class="empty-state empty-state-wide">
        <CalendarX />
        <p>No events match this filter.</p>
      </div>

    </main>

  </div>
</template>
