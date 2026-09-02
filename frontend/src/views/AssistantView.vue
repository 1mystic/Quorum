<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Send, Sparkles, ShieldCheck, ShieldOff, Wifi } from 'lucide-vue-next'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { chat } from '../api/ai'
import { ApiError, NetworkError } from '../api/client'
import { toast } from '../composables/useToast'

// Real POST /api/t/{slug}/ai/chat (app/api/ai.py, card... AI module has no
// frontend yet as of this session). The client owns the transcript and
// replays it every turn - the backend keeps no server-side session
// (app/agent/loop.py). `degraded`/`offline` are two independent, real
// states the assistant can be in and this view shows both plainly, the
// same posture as `insufficient_data` elsewhere: nothing here hides a
// worse answer behind a clean-looking bubble.

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))

const suggestions = [
  'What groups match my interests?',
  "What's happening this week?",
  'Anything popular I should know about?'
]

// The side panel's honest scope statement - what the bounded tool-calling
// agent (app/agent/loop.py) actually does, and the one boundary that
// matters most given docs/RULES.md rule 5: it narrates Evidence, it never
// computes or invents one.
const canDo = [
  'Find groups and events that match what you describe',
  'Summarise what is happening this week or recently',
  'Point you at the Evidence and Method Card behind a real figure'
]
const cannotDo = [
  'Invent or recompute a statistic - every number it mentions came from an insight_run',
  'See other members\' private data or act on your behalf (no RSVP, no payments)',
  'Promise a live model reply when it is running degraded or offline'
]
const statusTags = [
  { label: 'Degraded', body: 'a deterministic keyword match answered instead of the model' },
  { label: 'Offline', body: 'sample data stood in, not this tenant\'s live data' }
]
const aboutOpen = ref(false)

const STORAGE_KEY = computed(() => `quorum-assistant-${slug.value}`)

function loadThread() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY.value)
    const turns = raw ? JSON.parse(raw) : []
    // A turn left mid-request by navigating away comes back as a spinner
    // that never resolves without this - nothing is actually in flight on
    // a fresh mount.
    for (const turn of turns) {
      if (turn.pending) {
        turn.pending = false
        turn.failed = true
      }
    }
    return turns
  } catch {
    return []
  }
}

const thread = ref(loadThread())
const draft = ref('')
const sending = ref(false)
const scrollAreaRef = ref(null)
const composerRef = ref(null)

watch(thread, (turns) => {
  try {
    sessionStorage.setItem(STORAGE_KEY.value, JSON.stringify(turns))
  } catch {
    // Private browsing or a full quota: the chat still works for this
    // session, it just will not persist across a reload. Not worth
    // surfacing as an error.
  }
}, { deep: true })

const hasHistory = computed(() => thread.value.length > 0)

function scrollToBottom() {
  const el = scrollAreaRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function autoGrow() {
  const el = composerRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 140) + 'px'
}

function toApiMessages() {
  // Everything before the turn currently being sent, oldest first - the
  // pending turn's own query is passed separately as interest_text
  // (app/schemas/ai.py's AgentChatRequest shape).
  const messages = []
  for (const turn of thread.value) {
    if (turn.pending || turn.failed) continue
    messages.push({ role: 'user', content: turn.query })
    if (turn.message) messages.push({ role: 'assistant', content: turn.message })
  }
  return messages
}

let nextId = Date.now()

async function send(text) {
  const input = (text || draft.value).trim()
  if (!input || sending.value) return

  sending.value = true
  draft.value = ''
  await nextTick()
  autoGrow()

  const history = toApiMessages()
  const id = ++nextId
  thread.value.push({
    id,
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
    return thread.value.find((t) => t.id === id)
  }

  try {
    const result = await chat(slug.value, { messages: history, interestText: input })
    const turn = findTurn()
    if (turn) {
      turn.pending = false
      turn.kind = result.kind || 'chat'
      turn.message = result.reply || ''
      turn.items = result.items || []
      turn.offline = Boolean(result.offline)
      turn.degraded = Boolean(result.degraded)
    }
  } catch (err) {
    const turn = findTurn()
    if (turn) {
      turn.pending = false
      turn.failed = true
    }
    toast.error(err instanceof NetworkError || err instanceof ApiError ? err.message : 'Could not reach the assistant.')
  } finally {
    sending.value = false
  }
  await nextTick()
  scrollToBottom()
}

function useSuggestion(text) {
  send(text)
}

function itemTitle(item) {
  return item.name || item.title || 'Untitled'
}

function itemSubtitle(item) {
  if (item.entity_kind === 'event') {
    return [item.group_name, item.venue].filter(Boolean).join(' · ') || 'Event'
  }
  return item.category ? item.category.replace(/_/g, ' ') : 'Group'
}

function itemMeta(item) {
  if (item.entity_kind === 'event') {
    const when = item.starts_at ? new Date(item.starts_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''
    const seats = item.seats_left != null ? `${item.seats_left} seats left` : ''
    return [when, seats].filter(Boolean).join(' · ')
  }
  return item.member_count != null ? `${item.member_count} members` : ''
}

function openItem(item) {
  if (item.entity_kind === 'event' && item.id != null) {
    router.push(`/t/${slug.value}/events/${item.id}`)
  }
}

onMounted(() => {
  if (hasHistory.value) nextTick(scrollToBottom)
})
</script>

<template>
  <TenantShell title="Assistant" :subtitle="`ask ${tenant.name} anything about groups and events`">
    <div class="row r-32 assistant-layout">
      <div class="card assistant-card">
        <div ref="scrollAreaRef" class="assistant-scroll" :class="{ 'is-empty': !hasHistory }">
          <div v-if="!hasHistory" class="assistant-empty">
            <div class="assistant-empty-icon"><Sparkles :size="22" /></div>
            <h3>Ask Quorum</h3>
            <p>Describe what you are looking for, in plain language - the assistant narrates real numbers and finds groups or events for you, it never invents a statistic of its own.</p>
            <div class="chips">
              <button v-for="s in suggestions" :key="s" class="chip" @click="useSuggestion(s)">{{ s }}</button>
            </div>
          </div>

          <div v-else class="assistant-thread">
            <div v-for="turn in thread" :key="turn.id" class="assistant-turn">
              <div class="assistant-msg is-user">{{ turn.query }}</div>

              <div v-if="turn.pending" class="assistant-msg is-assistant is-pending">
                <span class="assistant-dots"><span></span><span></span><span></span></span>
                Thinking
              </div>

              <div v-else-if="turn.failed" class="assistant-msg is-assistant is-failed">
                Something went wrong reaching the assistant. Try asking again.
              </div>

              <template v-else>
                <div class="assistant-msg is-assistant">
                  <div class="assistant-tags">
                    <span v-if="turn.degraded" class="assistant-tag is-degraded">Degraded · deterministic match, not the model</span>
                    <span v-if="turn.offline" class="assistant-tag is-offline">Offline · sample data, not this tenant's live data</span>
                  </div>
                  {{ turn.message }}
                </div>

                <div v-if="turn.items && turn.items.length" class="assistant-items">
                  <div
                    v-for="item in turn.items" :key="item.entity_kind + '-' + item.id"
                    class="assistant-item" :class="{ 'is-clickable': item.entity_kind === 'event' }"
                    @click="openItem(item)"
                  >
                    <div class="lr-title">{{ itemTitle(item) }}</div>
                    <div class="lr-sub">{{ itemSubtitle(item) }}</div>
                    <div v-if="itemMeta(item)" class="assistant-item-meta">{{ itemMeta(item) }}</div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <div v-if="hasHistory" class="assistant-more-chips">
          <button v-for="s in suggestions" :key="s" class="chip" @click="useSuggestion(s)">{{ s }}</button>
        </div>

        <form class="assistant-composer" @submit.prevent="send()">
          <div class="field assistant-field">
            <textarea
              ref="composerRef" v-model="draft" rows="1" class="assistant-textarea"
              placeholder="Ask about groups, events, or what's new..."
              :disabled="sending"
              @input="autoGrow"
              @keydown.enter.exact.prevent="send()"
            ></textarea>
          </div>
          <button type="submit" class="btn btn-primary" :disabled="sending || !draft.trim()">
            <span>{{ sending ? 'Sending…' : 'Send' }}</span>
            <Send :size="15" />
          </button>
        </form>
      </div>

      <div class="assistant-side">
        <div class="card assistant-about">
          <div class="chead"><div><h3>About this assistant</h3></div></div>
          <p class="assistant-about-lead">Narrates real Evidence and finds groups or events for you - it never invents a statistic of its own.</p>
          <button type="button" class="tgl assistant-about-toggle" :aria-expanded="aboutOpen" @click="aboutOpen = !aboutOpen">
            {{ aboutOpen ? 'Hide details' : 'What it can and can\'t do' }}
          </button>
          <div v-if="aboutOpen" class="assistant-about-detail">
            <div class="assistant-about-group">
              <div class="assistant-about-label">Can</div>
              <ul class="assistant-scope">
                <li v-for="c in canDo" :key="c"><ShieldCheck :size="14" />{{ c }}</li>
              </ul>
            </div>
            <div class="assistant-about-group">
              <div class="assistant-about-label">Can't</div>
              <ul class="assistant-scope is-limit">
                <li v-for="c in cannotDo" :key="c"><ShieldOff :size="14" />{{ c }}</li>
              </ul>
            </div>
            <div class="assistant-about-group">
              <div class="assistant-about-label">Status tags</div>
              <ul class="assistant-scope">
                <li v-for="t in statusTags" :key="t.label"><Wifi :size="14" /><span><strong>{{ t.label }}</strong> - {{ t.body }}</span></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </TenantShell>
</template>
