<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, UserPlus, UserMinus, Clock, MapPin, Users } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import ClubIcon from '../components/ui/ClubIcon.vue'
import { useClubsStore } from '../stores/clubs'
import { useEventsStore } from '../stores/events'
import { requestToJoinClub, leaveClub } from '../api/clubs'
import { registerForEvent, unregisterFromEvent } from '../api/events'
import { toast } from '../composables/useToast'
import { bannerColourFor } from '../utils/clubVisuals'

const route = useRoute()
const router = useRouter()
const clubsStore = useClubsStore()
const eventsStore = useEventsStore()

const joinState = ref('none')

const club = computed(() => clubsStore.currentClub)

// The visitor's own membership in this exact club, if any - drives whether
// the header button reads "Request to Join", "Request Sent" or "Leave Club".
const myMembership = computed(() => {
  if (!club.value) return null
  return clubsStore.joinedClubs.find((c) => c.id === club.value.id) || null
})

const isMyLedClub = computed(() => myMembership.value?.membership_role === 'LEADER')

function syncJoinStateFromMembership() {
  const status = myMembership.value?.membership_status
  if (status === 'APPROVED') {
    joinState.value = 'joined'
  } else if (status === 'PENDING') {
    joinState.value = 'pending'
  } else {
    joinState.value = 'none'
  }
}

// member_count from the API counts every APPROVED membership, and the club
// leader has one of those too - created automatically when the club was
// proposed. "Members" here means the people the leader is leading, not a
// headcount that includes the leader. Same correction as LeaderClubView.
const regularMemberCount = computed(() => {
  if (!club.value) return 0
  return Math.max(club.value.member_count - 1, 0)
})

const clubEvents = computed(function eventsForThisClub() {
  if (!club.value) return []
  return eventsStore.events.filter(function belongsToClub(event) {
    return event.club_id === club.value.id && event.status !== 'past'
  })
})

const pastClubEvents = computed(function pastEventsForThisClub() {
  if (!club.value) return []
  return eventsStore.events.filter(function belongsToClub(event) {
    return event.club_id === club.value.id && event.status === 'past'
  })
})

// "Events Run" was reading clubEvents.length alone, but clubEvents excludes
// past events by design (it only feeds the Upcoming Events list) - a club
// whose only event had already happened showed 0 events run.
const totalClubEvents = computed(() => clubEvents.value.length + pastClubEvents.value.length)

watch(
  () => route.params.id,
  async (id) => {
    try {
      await clubsStore.loadClub(id)
      syncJoinStateFromMembership()
    } catch (error) {
      toast.error(error?.message || 'Failed to load club.')
    }
  }
)

const isJoining = ref(false)

async function handleJoinRequest() {
  if (joinState.value === 'pending' || isJoining.value) return

  isJoining.value = true

  try {
    await requestToJoinClub(route.params.id)
    joinState.value = 'pending'
    toast.success('Join request sent successfully.')
  } catch (error) {
    toast.error(error?.message || 'Failed to send join request.')
  } finally {
    isJoining.value = false
  }
}

async function handleLeaveClub() {
  if (isJoining.value) return

  const confirmed = window.confirm(
    `Leave ${club.value.name}? You will need to send a new request to rejoin.`
  )
  if (!confirmed) return

  isJoining.value = true

  try {
    await leaveClub(route.params.id)
    joinState.value = 'none'
    await clubsStore.refreshClubs()
    toast.success('You have left the club.')
  } catch (error) {
    toast.error(error?.message || 'Failed to leave the club.')
  } finally {
    isJoining.value = false
  }
}

function goBackToClubs() {
  router.push(`/${route.params.slug}/clubs`)
}

// Registration only stays open until the event actually starts - same rule
// EventDetailView enforces, kept in sync here so the button never claims an
// already-started event is still open.
function isRegistrationOpen(event) {
  return event.lifecycle === 'PUBLISHED' && new Date(event.starts_at) > new Date()
}

// Several event rows can be on screen at once, so "in flight" is tracked per
// event id rather than one flag for the whole page.
const busyEventIds = ref(new Set())

function isEventBusy(eventId) {
  return busyEventIds.value.has(eventId)
}

async function toggleEventRegistration(event) {
  busyEventIds.value.add(event.id)

  try {
    if (event.is_registered) {
      await unregisterFromEvent(event.id)
      toast.success('Registration cancelled.')
    } else {
      await registerForEvent(event.id)
      toast.success('You are registered for this event.')
    }

    // Refresh from the server rather than flipping a local flag - seats_left
    // and is_registered both need to reflect what the backend now has.
    await eventsStore.loadEvents(true)
  } catch (error) {
    toast.error(error?.message || 'Could not update your registration.')
  } finally {
    busyEventIds.value.delete(event.id)
  }
}

function categoryIcon(category) {
  const map = {
    tech: "laptop",
    arts: "palette",
    culture: "drama",
    sports: "sports",
    music: "music",
    business: "briefcase",
    science: "microscope",
  }

  return map[(category || "").toLowerCase()] || "robot"
}

// currentClub starts out null, and the fetch can take a few seconds - so a
// plain v-if="club" showed "Unable to load club details" as the FIRST thing
// on screen before flipping to the real page. Same fix as EventDetailView.
const hasLoaded = ref(false)

onMounted(async function loadProfile() {
  try {
    await Promise.all([
      clubsStore.loadClub(route.params.id),
      clubsStore.loadClubs(),
      eventsStore.loadEvents()
    ])
    syncJoinStateFromMembership()
  } catch (error) {
    toast.error(error?.message || 'Failed to load club details.')
  } finally {
    hasLoaded.value = true
  }
})
</script>

<template>
  <StudentSidebar />

  <div v-if="club" class="main-content">

    <header class="topbar">
      <button class="btn-secondary" @click="goBackToClubs">
        <ArrowLeft /> Back to Clubs
      </button>

      <div class="title-block">
        <h1 class="page-title">{{ club.name }}</h1>
        <p class="page-sub">{{ club.category }} · {{ club.type }}</p>
      </div>

      <div class="topbar-spacer"></div>

      <button
        v-if="joinState === 'joined'"
        class="btn-join leave"
        :disabled="isJoining"
        @click="handleLeaveClub"
      >
        <span v-if="isJoining" class="btn-spinner"></span>
        <template v-else><UserMinus /> Leave Club</template>
      </button>

      <button
        v-else-if="!isMyLedClub"
        class="btn-join"
        :disabled="joinState === 'pending' || isJoining"
        :class="{ pending: joinState === 'pending' }"
        @click="handleJoinRequest"
      >
        <span v-if="isJoining" class="btn-spinner"></span>
        <template v-else>
          <Clock v-if="joinState === 'pending'" />
          <UserPlus v-else />
          {{ joinState === 'pending' ? 'Request Sent' : 'Request to Join' }}
        </template>
      </button>
    </header>

    <main class="content-body custom-scrollbar">

      <div>
        <div
          class="club-profile-banner"
          :class="{ [bannerColourFor(club)]: !club.image_url }"
          :style="club.image_url ? { backgroundImage: `url(${club.image_url})` } : {}"
        >
          <template v-if="!club.image_url">
            <div class="club-card-circle-1"></div>
            <div class="club-card-circle-2"></div>
            <div class="club-card-circle-3"></div>
          </template>
          <div class="club-profile-icon">
            <ClubIcon :name="categoryIcon(club.category)" />
          </div>
        </div>
        <div class="club-profile-meta">
          <p class="club-profile-name">{{ club.name }}</p>
          <div class="club-profile-sub">
            <span class="cat-chip">{{ club.category }}</span>
            <span><MapPin /> {{ club.type }}</span>
            <span><Users /> {{ regularMemberCount }} members</span>
          </div>
          <p v-if="joinState === 'pending'" class="join-status-text">
            Your join request is pending approval from the club leader.
          </p>
        </div>
      </div>

      <div class="club-stats-row">
        <div class="club-stat-card">
          <p class="club-stat-num">{{ regularMemberCount }}</p>
          <p class="club-stat-label">Members</p>
        </div>
        <div class="club-stat-card">
          <p class="club-stat-num">{{ totalClubEvents }}</p>
          <p class="club-stat-label">Events Run</p>
        </div>
        <div class="club-stat-card">
          <p class="club-stat-num">
            {{ club.created_at ? new Date(club.created_at).getFullYear() : '-' }}
          </p>
          <p class="club-stat-label">Founded</p>
        </div>
      </div>

      <div class="card">
        <p class="section-heading">About</p>
        <p>{{ club.description }}</p>
      </div>

      <div>
        <p class="section-heading">Upcoming Events</p>
        <div class="club-event-list">

          <div v-for="event in clubEvents" :key="event.id" class="club-event-row">
            <div class="club-event-date-box">
              <span class="club-event-date-day">{{ event.day }}</span>
              <span class="club-event-date-month">{{ event.month }}</span>
            </div>
            <div class="club-event-info">
              <p class="club-event-title">{{ event.title }}</p>
              <p class="club-event-sub">{{ event.venue }} · {{ event.time }}</p>
            </div>
            <button
              v-if="event.is_registered"
              class="btn-secondary-sm"
              :disabled="isEventBusy(event.id)"
              @click="toggleEventRegistration(event)"
            >
              <span v-if="isEventBusy(event.id)" class="btn-spinner"></span>
              <template v-else>Registered · Cancel</template>
            </button>
            <button
              v-else
              class="btn-secondary-sm"
              :disabled="isEventBusy(event.id) || !isRegistrationOpen(event)"
              @click="toggleEventRegistration(event)"
            >
              <span v-if="isEventBusy(event.id)" class="btn-spinner"></span>
              <template v-else>{{ isRegistrationOpen(event) ? 'Register' : 'Closed' }}</template>
            </button>
          </div>

          <div v-if="clubEvents.length === 0" class="empty-state empty-state-wide">
            <p>No upcoming events right now.</p>
          </div>

        </div>
      </div>

      <div>
        <p class="section-heading">Past Events</p>
        <div class="club-event-list">

          <div v-for="event in pastClubEvents" :key="event.id" class="club-event-row">
            <div class="club-event-date-box">
              <span class="club-event-date-day">{{ event.day }}</span>
              <span class="club-event-date-month">{{ event.month }}</span>
            </div>
            <div class="club-event-info">
              <p class="club-event-title">{{ event.title }}</p>
              <p class="club-event-sub">{{ event.venue }} · {{ event.time }}</p>
            </div>
            <span class="event-status past">Completed</span>
          </div>

          <div v-if="pastClubEvents.length === 0" class="empty-state empty-state-wide">
            <p>No past events yet.</p>
          </div>

        </div>
      </div>

    </main>

  </div>
  <div v-else-if="!hasLoaded" class="main-content page-loading-state">
    <div class="empty-state">
      <p>Loading club...</p>
    </div>
  </div>
  <div v-else class="main-content page-loading-state">
    <div class="empty-state">
      <Users />
      <p>Unable to load club details.</p>
    </div>
  </div>
</template>
