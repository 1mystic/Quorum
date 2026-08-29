<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sparkles, CalendarSearch, Flame, CloudOff, Play, Pause, Volume2, Trash2 } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import ClubCard from '../components/ui/ClubCard.vue'
import EventCard from '../components/ui/EventCard.vue'
import { askAssistant } from '../api/ai'
import { normalizeEvent } from '../api/events'
import { toast } from '../composables/useToast'
import { renderMarkdown, stripMarkdown } from '../utils/markdown'
import { useNarrator } from '../composables/useNarrator'

const STORAGE_KEY = 'cc_finder_conversation'

const router = useRouter()
// openClub() below needs the current college slug to build the club-detail
// route, the same way every other student page does.
const route = useRoute()
const narrator = useNarrator()

const interestsText = ref('')
const isSearching = ref(false)
const composerInput = ref(null)
const scrollArea = ref(null)

// The whole session's chat: each turn is one user prompt plus the assistant's
// answer (message + cards). New prompts append here instead of replacing, and
// the array is mirrored to sessionStorage so the history survives navigating
// away and back within the same tab.
const conversation = ref(loadConversation())

// Which turn the narrator is currently reading, so each turn's Listen button
// reflects its own state.
const activeNarrationId = ref(null)

function loadConversation() {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    const turns = saved ? JSON.parse(saved) : []

    // A turn left mid-request when the student navigated away would otherwise
    // come back as a spinner that never resolves. Nothing is in flight on a
    // fresh mount, so mark any of those as failed instead.
    for (const turn of turns) {
      if (turn.pending) {
        turn.pending = false
        turn.failed = true
      }
    }

    return turns
  } catch (error) {
    return []
  }
}

watch(conversation, function persist(turns) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(turns))
  } catch (error) {
    // sessionStorage can be unavailable (private mode / quota) - the chat
    // still works in-memory, it just will not persist.
  }
}, { deep: true })

// When narration ends on its own, drop the active-turn highlight.
watch(() => narrator.isSpeaking.value, function onSpeakingChange(speaking) {
  if (!speaking) activeNarrationId.value = null
})

const hasHistory = computed(function checkHistory() {
  return conversation.value.length > 0
})


const suggestions = [
  'I love building robots and electronics',
  'Photography and film on weekends',
  'Debating, writing, and public speaking',
  'Startups, coding, and product design'
]

// Quick follow-up replies shown under the latest answer. One tap sends the
// message so the student can keep the conversation going without typing.
const followUpsByKind = {
  clubs: [
    'Show me a few more clubs like these',
    'Any events I could go to?',
    'Something more creative'
  ],
  event_fallback: [
    'Show me clubs instead',
    'Any tech or coding options?',
    'Something more hands-on'
  ],
  popularity: [
    'I am into arts and culture',
    'Show me tech and coding clubs',
    'Any events happening soon?'
  ]
}

const latestFollowUps = computed(function currentFollowUps() {
  if (!hasHistory.value) return []

  const lastTurn = conversation.value[conversation.value.length - 1]

  // Nothing useful to follow up on until the turn has actually answered.
  if (lastTurn.pending || lastTurn.failed) return []

  return followUpsByKind[lastTurn.kind] || followUpsByKind.clubs
})

// Every item the backend returns is tagged with what it is, because one answer
// can reference both a club and an event.
function turnClubs(turn) {
  return (turn.items || []).filter((item) => item.entity_kind !== 'event')
}

// The AI module sends raw event rows (starts_at, venue, club_name...) since
// that's what the backend service layer returns - never run through
// normalizeEvent() the way every other event list in the app already is.
// EventCard expects the normalized shape (.day, .time, .club, .status,
// .registered, .capacity), so without this every AI-surfaced event card
// rendered with blank date/time/venue/member-count fields.
function turnEvents(turn) {
  return (turn.items || [])
    .filter((item) => item.entity_kind === 'event')
    .map((item) => normalizeEvent(item))
}

function renderTurnMessage(turn) {
  const fallback = 'Here are the clubs that best match your interests.'
  return renderMarkdown(turn.message || fallback)
}

function narrateLabel(turn) {
  if (activeNarrationId.value !== turn.id || !narrator.isSpeaking.value) return 'Listen'
  return narrator.isPaused.value ? 'Resume' : 'Pause'
}

function isNarrating(turn) {
  return activeNarrationId.value === turn.id && narrator.isSpeaking.value
}

function narrateTurn(turn) {
  if (activeNarrationId.value === turn.id) {
    // Same turn - toggle pause / resume (or restart if it had finished).
    narrator.toggle(stripMarkdown(turn.message))
    return
  }
  // A different turn - start reading this one from the top.
  narrator.speak(stripMarkdown(turn.message))
  activeNarrationId.value = turn.id
}


function useSuggestion(text) {
  interestsText.value = text
  findClubs()
}

function sendFollowUp(text) {
  interestsText.value = text
  findClubs()
}

function clearConversation() {
  narrator.stop()
  conversation.value = []
  activeNarrationId.value = null
}

const COMPOSER_MAX_HEIGHT = 120

function autoGrowComposer() {
  const textarea = composerInput.value
  if (!textarea) return

  textarea.style.height = 'auto'
  textarea.style.height = textarea.scrollHeight + 'px'
  textarea.classList.toggle('is-maxed', textarea.scrollHeight > COMPOSER_MAX_HEIGHT)
}

function scrollToBottom() {
  const area = scrollArea.value
  if (area) area.scrollTop = area.scrollHeight
}

let nextTurnId = Date.now()

async function findClubs() {
  if (isSearching.value) {
    return
  }
  const input = interestsText.value.trim()

  if (!input) {
    toast.error('Please describe your interests before searching.')
    return
  }

  narrator.stop()
  isSearching.value = true
  interestsText.value = ''
  await nextTick()
  autoGrowComposer()

  // The history the assistant is answering against is everything before this
  // question, so it has to be captured before the pending turn is added.
  const history = conversation.value.slice()

  // Show the question straight away with a placeholder answer underneath.
  // Waiting for the response before rendering anything made the app look like
  // it had ignored the message.
  nextTurnId += 1
  const turnId = nextTurnId

  conversation.value.push({
    id: turnId,
    query: input,
    pending: true,
    failed: false,
    kind: '',
    message: '',
    items: [],
    offline: false,
    degraded: false
  })

  await nextTick()
  scrollToBottom()

  function findTurn() {
    return conversation.value.find(function matchId(turn) {
      return turn.id === turnId
    })
  }

  try {
    const result = await askAssistant(input, history)
    const turn = findTurn()

    if (turn) {
      turn.pending = false
      turn.kind = result.kind
      turn.message = result.message
      turn.items = result.items
      turn.offline = result.offline
      turn.degraded = result.degraded
    }
  } catch (error) {
    const turn = findTurn()

    // Keep the question on screen and mark the answer as failed, rather than
    // silently deleting what the student typed.
    if (turn) {
      turn.pending = false
      turn.failed = true
    }

    toast.error(error?.message || 'Failed to find matching clubs.')
  } finally {
    isSearching.value = false
  }

  await nextTick()
  scrollToBottom()
}

onMounted(function scrollOnReturn() {
  if (hasHistory.value) nextTick(scrollToBottom)
})

function openClub(clubId) {
  router.push(`/${route.params.slug}/clubs/${clubId}`)
}

function openEvent(eventId) {
  router.push(`/${route.params.slug}/events/${eventId}`)
}
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <Topbar title="AI Club Finder" sub="Describe your interests and find clubs that match" :show-bell="false" />

    <main class="content-body finder-chat">

      <div class="finder-chat-scroll custom-scrollbar" ref="scrollArea">

        <!-- Empty state: centered intro + quick prompts -->
        <div v-if="!hasHistory" class="finder-empty">
          <div class="finder-hero-icon">
            <Sparkles />
          </div>
          <p class="finder-hero-title">What are you into?</p>
          <p class="finder-hero-desc">
            Describe your interests in plain language. The AI will match you with clubs
            at your college, including niche ones with no social media presence.
          </p>

          <div class="finder-suggestions">
            <button
              v-for="prompt in suggestions"
              :key="prompt"
              class="finder-suggestion-chip"
              @click="useSuggestion(prompt)"
            >
              <Sparkles /> {{ prompt }}
            </button>
          </div>
        </div>

        <!-- Conversation: every turn stacked, oldest first -->
        <div v-else class="finder-thread">

          <div class="finder-thread-bar">
            <button class="finder-clear-btn" @click="clearConversation">
              <Trash2 /> Clear chat
            </button>
          </div>

          <div v-for="turn in conversation" :key="turn.id" class="finder-turn">

            <div class="finder-user-msg">{{ turn.query }}</div>

            <div class="finder-assistant">
              <div class="finder-assistant-avatar">
                <Sparkles />
              </div>
              <div class="finder-assistant-body">

                <!-- Waiting on the answer for this turn -->
                <div v-if="turn.pending" class="finder-msg-bubble finder-msg-thinking">
                  <span class="finder-thinking-dots" aria-hidden="true">
                    <i></i><i></i><i></i>
                  </span>
                  <span class="finder-thinking-label">Finding matches...</span>
                </div>

                <!-- The request failed; the question stays on screen -->
                <div v-else-if="turn.failed" class="finder-msg-bubble finder-msg-failed">
                  <span class="finder-msg-tag is-offline">
                    <CloudOff /> Could not answer
                  </span>
                  <div class="finder-msg-md">
                    Something went wrong reaching the assistant. Please try asking again.
                  </div>
                </div>

                <!-- Conversational reply (Markdown), same for every result kind -->
                <div v-else class="finder-msg-bubble">
                  <span v-if="turn.kind === 'event_fallback'" class="finder-msg-tag">
                    <CalendarSearch /> Event suggestion
                  </span>
                  <span v-else-if="turn.kind === 'popularity'" class="finder-msg-tag">
                    <Flame /> Popular on campus
                  </span>
                  <span v-if="turn.offline" class="finder-msg-tag is-offline">
                    <CloudOff /> Sample data
                  </span>

                  <div class="finder-msg-md" v-html="renderTurnMessage(turn)"></div>

                  <button
                    v-if="narrator.isSupported.value"
                    class="finder-narrate-btn"
                    :class="{ 'is-active': isNarrating(turn) }"
                    :aria-label="narrateLabel(turn)"
                    @click="narrateTurn(turn)"
                  >
                    <Pause v-if="isNarrating(turn) && !narrator.isPaused.value" />
                    <Play v-else-if="isNarrating(turn) && narrator.isPaused.value" />
                    <Volume2 v-else />
                    <span>{{ narrateLabel(turn) }}</span>
                  </button>
                </div>

                <!-- Clubs the answer referenced -->
                <div v-if="turnClubs(turn).length" class="clubs-grid finder-result-grid">
                  <div v-for="(match, index) in turnClubs(turn)" :key="match.id" class="finder-result-item">
                    <ClubCard
                      :club="match"
                      :badge="turn.kind === 'popularity' ? 'Popular' : (index === 0 ? 'Top Match' : '')"
                      @open="openClub(match.id)"
                    />
                  </div>
                </div>

                <!-- Events the answer referenced -->
                <div
                  v-if="turnEvents(turn).length"
                  class="events-grid finder-fallback-events finder-result-grid"
                >
                  <div v-for="ev in turnEvents(turn)" :key="ev.id" class="finder-result-item">
                    <EventCard :event="ev" @open="openEvent(ev.id)" />
                  </div>
                </div>

              </div>
            </div>
          </div>

          <!-- Quick follow-up replies for the latest answer only -->
          <div v-if="latestFollowUps.length && !isSearching" class="finder-followups">
            <button
              v-for="chip in latestFollowUps"
              :key="chip"
              class="finder-followup-chip"
              :disabled="isSearching"
              @click="sendFollowUp(chip)"
            >
              {{ chip }}
            </button>
          </div>

        </div>

      </div>

      <!-- Composer pinned to the bottom, chat style -->
      <div class="finder-composer">
        <div class="finder-composer-inner">
          <textarea
            ref="composerInput"
            v-model="interestsText"
            class="finder-composer-input"
            rows="1"
            placeholder="Describe your interests, e.g. electronics, photography, startups..."
            @input="autoGrowComposer"
            @keydown.enter.exact.prevent="findClubs"
          ></textarea>
          <button
            class="finder-send-btn"
            :disabled="isSearching"
            :aria-label="isSearching ? 'Finding clubs' : 'Find clubs'"
            @click="findClubs"
          >
            <Sparkles />
            <span>{{ isSearching ? 'Finding...' : 'Find' }}</span>
          </button>
        </div>
        <p class="finder-composer-hint">
          AI matches you with clubs at your college — press Enter to search.
        </p>
      </div>

    </main>

  </div>
</template>
