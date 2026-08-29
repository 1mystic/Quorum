<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Award, Crown, Medal } from 'lucide-vue-next'
import LeaderSidebar from '../components/layout/LeaderSidebar.vue'
import {
  getEventParticipants, getEventById, declareResults,
  normalizeEvent, normalizeParticipant
} from '../api/events'
import { toast } from '../composables/useToast'
import { invalidateCache } from '../utils/apiCache'

const route = useRoute()
const router = useRouter()

const event = ref(null)
const participants = ref([])
const saving = ref(false)
const alreadyDeclared = ref(false)

// The API takes exactly one winner and one runner-up in a single call, not a
// result per row - every other checked-in attendee becomes PARTICIPANT on
// the server. The form mirrors that: pick one of each, not a dropdown each.
const winnerId = ref(null)
const runnerUpId = ref(null)

// A result can only be recorded for someone who was checked in at the event.
const attendees = computed(function checkedInOnly() {
  return participants.value.filter((participant) => participant.checked_in)
})

function pickWinner(registrationId) {
  winnerId.value = registrationId
  if (runnerUpId.value === registrationId) {
    runnerUpId.value = null
  }
}

function pickRunnerUp(registrationId) {
  runnerUpId.value = registrationId
  if (winnerId.value === registrationId) {
    winnerId.value = null
  }
}

const canPublish = computed(function checkReady() {
  return Boolean(winnerId.value) && Boolean(runnerUpId.value) && winnerId.value !== runnerUpId.value
})

async function publishResults() {
  if (!canPublish.value) {
    toast.error('Pick a winner and a runner-up before publishing.')
    return
  }

  saving.value = true

  try {
    await declareResults(route.params.id, winnerId.value, runnerUpId.value)
    invalidateCache('leaderboard')
    toast.success('Results published! Every attendee can now see their result on the event page.')
    router.push(`/${route.params.slug}/leader/events`)
  } catch (error) {
    toast.error(error.message || 'Could not publish results.')
  } finally {
    saving.value = false
  }
}

async function loadParticipants() {
  const rows = await getEventParticipants(route.params.id)

  participants.value = rows.map((row) => normalizeParticipant(row))

  // Only a real WINNER/RUNNER_UP means results were declared - PARTICIPANT is
  // just what attendance marking sets on check-in, before any result exists.
  const declared = attendees.value.find(
    (attendee) => attendee.result === 'WINNER' || attendee.result === 'RUNNER_UP'
  )
  alreadyDeclared.value = Boolean(declared)

  const existingWinner = attendees.value.find((attendee) => attendee.result === 'WINNER')
  const existingRunnerUp = attendees.value.find((attendee) => attendee.result === 'RUNNER_UP')

  winnerId.value = existingWinner ? existingWinner.registration_id : null
  runnerUpId.value = existingRunnerUp ? existingRunnerUp.registration_id : null
}

function goBackToAttendance() {
  router.push(`/${route.params.slug}/leader/events/${route.params.id}/attend`)
}

onMounted(async function loadResultsPage() {
  try {
    event.value = normalizeEvent(await getEventById(route.params.id))
    await loadParticipants()
  } catch (error) {
    toast.error(error.message)
  }
})
</script>

<template>
  <LeaderSidebar />

  <div class="main-content">

    <header class="topbar">
      <button class="btn-secondary" @click="goBackToAttendance">
        <ArrowLeft /> Attendance
      </button>
      <div class="title-block">
        <h1 class="page-title">Set Results</h1>
        <p class="page-sub" v-if="event">{{ event.title }} · {{ attendees.length }} attended</p>
      </div>
      <div class="topbar-spacer"></div>
    </header>

    <main class="content-body custom-scrollbar">

      <div class="club-profile-meta">
        <p class="section-heading">Attendees</p>
        <p class="text-note">
          Pick one winner and one runner-up. Everyone else who was checked in is
          automatically recorded as a participant when you publish.
        </p>
        <p v-if="alreadyDeclared" class="text-note">
          Results have already been published for this event. Attendance and
          results are frozen once declared.
        </p>
      </div>

      <div class="participant-list mt-16">
        <div
          v-for="attendee in attendees"
          :key="attendee.registration_id"
          class="participant-row"
        >
          <div class="participant-avatar">{{ attendee.initials }}</div>
          <div class="participant-info">
            <p class="participant-name">{{ attendee.name }}</p>
            <p class="participant-sub">{{ attendee.sub }}</p>
          </div>

          <div class="result-pick-group">
            <button
              type="button"
              class="btn-secondary-sm result-pick-btn"
              :class="{ 'result-pick-winner': winnerId === attendee.registration_id }"
              :disabled="alreadyDeclared"
              @click="pickWinner(attendee.registration_id)"
            >
              <Crown /> Winner
            </button>
            <button
              type="button"
              class="btn-secondary-sm result-pick-btn"
              :class="{ 'result-pick-runner-up': runnerUpId === attendee.registration_id }"
              :disabled="alreadyDeclared"
              @click="pickRunnerUp(attendee.registration_id)"
            >
              <Medal /> Runner-up
            </button>
          </div>
        </div>
      </div>

      <div v-if="attendees.length === 0" class="empty-state empty-state-wide">
        <p>Nobody has been checked in yet. Mark attendance first.</p>
      </div>

      <div class="event-action-bar">
        <p class="text-note">Students see their result on the event page once published.</p>
        <button
          class="btn-primary"
          :disabled="saving || !canPublish || alreadyDeclared"
          @click="publishResults"
        >
          <span v-if="saving" class="btn-spinner"></span>
          <template v-else>
            <Award /> {{ alreadyDeclared ? 'Results Published' : 'Publish Results' }}
          </template>
        </button>
      </div>

    </main>

  </div>
</template>
