<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, CheckCheck, Save } from 'lucide-vue-next'
import LeaderSidebar from '../components/layout/LeaderSidebar.vue'
import {
  getEventParticipants, getEventById, markAttendance,
  normalizeEvent, normalizeParticipant
} from '../api/events'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()

const event = ref(null)
const participants = ref([])
const presentIds = ref([])
const saving = ref(false)

const presentCount = computed(() => presentIds.value.length)

// The API rejects attendance until the event has started.
const attendanceOpen = computed(function isOpen() {
  if (!event.value) return false
  return new Date(event.value.starts_at) <= new Date()
})

function togglePresent(registrationId) {
  if (presentIds.value.includes(registrationId)) {
    presentIds.value = presentIds.value.filter((id) => id !== registrationId)
  } else {
    presentIds.value.push(registrationId)
  }
}

function markAllPresent() {
  presentIds.value = participants.value.map((participant) => participant.registration_id)
}

// Attendance is a PATCH per registration, so only the rows that actually changed are sent.
function changedRows() {
  return participants.value.filter(function hasChanged(participant) {
    return presentIds.value.includes(participant.registration_id) !== participant.checked_in
  })
}

async function submitAttendance() {
  if (!attendanceOpen.value) {
    toast.error('Attendance can only be marked once the event has started.')
    return
  }

  const changed = changedRows()

  if (!changed.length) {
    toast.info('No attendance changes to save.')
    return
  }

  saving.value = true

  const outcomes = await Promise.allSettled(
    changed.map(function saveRow(participant) {
      return markAttendance(
        route.params.id,
        participant.registration_id,
        presentIds.value.includes(participant.registration_id)
      )
    })
  )

  saving.value = false

  const failed = outcomes.filter((outcome) => outcome.status === 'rejected')

  if (failed.length) {
    toast.error(`${failed.length} of ${changed.length} updates failed: ${failed[0].reason.message}`)
    await loadParticipants()
    return
  }

  toast.success(`Attendance saved for ${presentCount.value} participants. Now set results on the Results page.`)
  router.push(`/${route.params.slug}/leader/events/${route.params.id}/results`)
}

async function loadParticipants() {
  const rows = await getEventParticipants(route.params.id)

  participants.value = rows.map((row) => normalizeParticipant(row))
  presentIds.value = participants.value
    .filter((participant) => participant.checked_in)
    .map((participant) => participant.registration_id)
}

function goBackToEvents() {
  router.push(`/${route.params.slug}/leader/events`)
}

onMounted(async function loadAttendancePage() {
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
      <button class="btn-secondary" @click="goBackToEvents">
        <ArrowLeft /> Events
      </button>
      <div class="title-block">
        <h1 class="page-title">Mark Attendance</h1>
        <p class="page-sub" v-if="event">{{ event.title }} · {{ event.dateLong }}</p>
      </div>
      <div class="topbar-spacer"></div>
      <button class="btn-secondary" @click="markAllPresent">
        <CheckCheck /> Mark All Present
      </button>
    </header>

    <main class="content-body custom-scrollbar">

      <div class="club-profile-meta">
        <p class="section-heading">Registered Participants</p>
        <p class="text-note" v-if="event && attendanceOpen">
          {{ event.registration_count }} registered · Check each student who was physically present at the event.
        </p>
        <p class="text-note" v-else-if="event">
          This event starts on {{ event.dateLong }} at {{ event.time }}. Attendance can only be
          marked once it has started.
        </p>
      </div>

      <div class="participant-list mt-16">
        <div v-for="participant in participants" :key="participant.registration_id" class="participant-row">
          <input
            type="checkbox"
            class="attend-checkbox"
            :id="'att-' + participant.registration_id"
            :checked="presentIds.includes(participant.registration_id)"
            :disabled="!attendanceOpen"
            @change="togglePresent(participant.registration_id)"
          >
          <label :for="'att-' + participant.registration_id" class="participant-avatar">{{ participant.initials }}</label>
          <div class="participant-info">
            <p class="participant-name">{{ participant.name }}</p>
            <p class="participant-sub">{{ participant.sub }} · {{ participant.regId }}</p>
          </div>
        </div>
      </div>

      <div v-if="participants.length === 0" class="empty-state empty-state-wide">
        <p>Nobody has registered for this event yet.</p>
      </div>

      <div class="event-action-bar">
        <p class="text-note">{{ presentCount }} of {{ participants.length }} marked present</p>
        <button class="btn-primary" :disabled="saving || !attendanceOpen" @click="submitAttendance">
          <span v-if="saving" class="btn-spinner"></span>
          <template v-else><Save /> Save Attendance</template>
        </button>
      </div>

    </main>

  </div>
</template>
