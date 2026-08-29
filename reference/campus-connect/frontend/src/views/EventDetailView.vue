<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Calendar, Clock, MapPin, Users, CheckCircle2, XCircle, Award } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import { useEventsStore } from '../stores/events'
import { registerForEvent, unregisterFromEvent, getMyResults } from '../api/events'
import { cachedFetch, invalidateCache } from '../utils/apiCache'
import { toast } from '../composables/useToast'
import { useNotificationsStore } from '../stores/notifications'   // add


const route = useRoute()
const router = useRouter()
const eventsStore = useEventsStore()
const notificationsStore = useNotificationsStore()  

const submitting = ref(false)
const myResult = ref(null)

const event = computed(() => eventsStore.currentEvent)

// Neon's connection latency means the fetch can take a few seconds, and
// currentEvent starts out null before the first load - so a plain v-if on
// event showed "Event not found" as the FIRST thing on screen, then swapped
// to the real page once the request finished. hasLoaded distinguishes
// "we don't have it yet" from "we asked, and there genuinely isn't one".
const hasLoaded = ref(false)

const seatsRemaining = computed(function calcSeats() {
  if (!event.value) return null
  return event.value.seats_left
})

// The backend refuses a registration once the event has started or if it is not published.
const registrationOpen = computed(function isOpen() {
  if (!event.value) return false
  return event.value.lifecycle === 'PUBLISHED' && new Date(event.value.starts_at) > new Date()
})

const resultLabels = {
  WINNER: 'Winner',
  RUNNER_UP: 'Runner-up',
  PARTICIPANT: 'Participant'
}

const resultClasses = {
  WINNER: 'winner',
  RUNNER_UP: 'runner-up',
  PARTICIPANT: 'participant'
}

async function reloadEvent() {
  try {
    await eventsStore.loadEvent(route.params.id)
    await eventsStore.loadMyRegistrations()
    eventsStore.loaded = false
  } catch (error) {
    toast.error(error?.message || 'Failed to refresh event.')
  }
}

async function handleRegister() {
  submitting.value = true

  try {
    const confirmation = await registerForEvent(route.params.id)
    await reloadEvent()
    invalidateCache('my-results')
    await loadMyResult()
    await notificationsStore.fetchUnreadCount() 
    toast.success(confirmation.message)
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  } finally {
    submitting.value = false
  }
}

async function handleUnregister() {
  submitting.value = true

  try {
    const result = await unregisterFromEvent(route.params.id)
    await reloadEvent()
    invalidateCache('my-results')
    await loadMyResult()
    toast.success(result.message)
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  } finally {
    submitting.value = false
  }
}

async function loadMyResult() {
  try {
    const results = await cachedFetch('my-results', getMyResults)

    myResult.value =
      results.find(
        r => r.event_id === Number(route.params.id)
      ) || null

  } catch (error) {
    console.error(error)

    myResult.value = null

    toast.error(
      "Unable to load your event result."
    )
  }
}

function goBackToEvents() {
  router.push(`/${route.params.slug}/events`)
}

onMounted(async function loadDetail() {
  try {
    await eventsStore.loadEvent(route.params.id)
    await loadMyResult()
  } catch (error) {
    toast.error(error?.message || 'Failed to load event.')
  } finally {
    hasLoaded.value = true
  }
})
</script>

<template>
  <StudentSidebar />

  <div class="main-content" v-if="event">

    <header class="topbar">
      <button class="btn-secondary" @click="goBackToEvents">
        <ArrowLeft /> Events
      </button>

      <div class="title-block">
        <h1 class="page-title">Event Detail</h1>
        <router-link :to="`/${route.params.slug}/clubs/${event.club_id}`" class="page-sub event-detail-club-link">
          {{ event.club }}
        </router-link>
      </div>

      <div class="topbar-spacer"></div>
    </header>

    <main class="content-body custom-scrollbar">

      <div>
        <div class="event-hero-banner" :class="event.accent">
          <div class="club-card-circle-1"></div>
          <div class="club-card-circle-2"></div>
          <div class="club-card-circle-3"></div>
          <div class="event-hero-overlay"></div>
          <div class="event-hero-text">
            <p class="event-hero-title">{{ event.title }}</p>
            <p class="event-hero-sub">{{ event.club }} · {{ event.dateLong }}</p>
          </div>
        </div>

        <div class="club-profile-meta">
          <div class="event-detail-grid">

            <div>
              <p class="section-heading">About this Event</p>
              <p class="body-text">{{ event.description }}</p>

              <div class="event-meta-list mt-20">
                <div class="event-meta-item">
                  <Calendar />
                  <span><span class="event-meta-label">Date</span> &nbsp; {{ event.dateLong }}</span>
                </div>
                <div class="event-meta-item">
                  <Clock />
                  <span><span class="event-meta-label">Time</span> &nbsp; {{ event.timeLong }}</span>
                </div>
                <div class="event-meta-item">
                  <MapPin />
                  <span><span class="event-meta-label">Venue</span> &nbsp; {{ event.venue }}</span>
                </div>
                <div class="event-meta-item">
                  <Users />
                  <span v-if="event.capacity">
                    <span class="event-meta-label">Capacity</span> &nbsp; {{ event.capacity }} participants ({{ event.registered }} registered)
                  </span>
                  <span v-else>
                    <span class="event-meta-label">Capacity</span> &nbsp; Unlimited ({{ event.registered }} registered)
                  </span>
                </div>
              </div>
            </div>

            <div class="reg-panel">

              <div v-if="!event.is_registered">
                <p class="reg-panel-title">Register for this Event</p>
                <div class="reg-capacity-row" v-if="seatsRemaining !== null">
                  <span>Seats remaining</span>
                  <span class="reg-capacity-num">{{ seatsRemaining }}</span>
                </div>
                <p class="text-note">
                  Registration closes when the event starts on {{ event.dateLong }}. Only approved
                  members of {{ event.club }} can register.
                </p>
                <button
                  class="btn-auth-submit"
                  :disabled="submitting || !registrationOpen"
                  @click="handleRegister"
                >
                  <span v-if="submitting" class="btn-spinner"></span>
                  <template v-else>
                    <CheckCircle2 /> {{ registrationOpen ? 'Register Now' : 'Registration Closed' }}
                  </template>
                </button>
              </div>

              <div v-else>
                <p class="reg-panel-title">You are Registered!</p>
                <div class="reg-id-box">
                  <p class="reg-id-label">Registration ID</p>
                  <p class="reg-id-value">#{{ event.my_registration_id }}</p>
                </div>
                <p class="text-note">Show this ID at the event gate.</p>

                <button
                  v-if="registrationOpen"
                  class="btn-secondary"
                  :disabled="submitting"
                  @click="handleUnregister"
                >
                  <span v-if="submitting" class="btn-spinner"></span>
                  <template v-else><XCircle /> Cancel Registration</template>
                </button>

                <div v-if="myResult">
                  <p class="reg-panel-title">Your Result</p>
                  <div class="result-badge" :class="resultClasses[myResult.result]">
                    <Award /> {{ resultLabels[myResult.result] }}
                  </div>
                </div>
              </div>

            </div>

          </div>
        </div>
      </div>

    </main>

  </div>
  <div v-else-if="!hasLoaded" class="main-content page-loading-state">
    <div class="empty-state">
      <p>Loading event...</p>
    </div>
  </div>
  <div v-else class="main-content page-loading-state">
    <div class="empty-state">
      <p>Event not found.</p>
    </div>
  </div>
</template>
