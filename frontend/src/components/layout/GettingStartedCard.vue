<script setup>
import { computed, ref } from 'vue'
import { PanelLeft, Gauge, Sparkles, PlusCircle, X } from 'lucide-vue-next'

// A dismissible orientation card for a brand new member or admin, not a
// blocking modal and not a spotlight tour that has to know where every
// element on every page sits (fragile across a responsive, multi-role
// layout, and the sidebar itself is already collapsible/off-canvas below
// 1080px - see TenantShell.vue). Four short, concrete orientations rather
// than a generic "welcome": what the sidebar sections mean, what an
// Evidence card is and why it sometimes withholds a number, where the
// assistant lives, and how to raise a request - the four things a first
// session actually needs, per the product brief.
//
// "Seen it" persists in localStorage the same way TenantShell.vue's
// collapsed-nav state does: try/catch fallback, so private browsing or a
// full quota just means it reappears next visit rather than breaking.

const props = defineProps({
  slug: { type: String, required: true },
  requestLabel: { type: String, default: 'request' }
})

const STORAGE_KEY = 'quorum-getting-started-dismissed'

function loadDismissed() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

const dismissed = ref(loadDismissed())

function dismiss() {
  dismissed.value = true
  try {
    localStorage.setItem(STORAGE_KEY, '1')
  } catch {
    // Same posture as TenantShell.vue: the dismissal still works for this
    // session, it just will not persist. Not worth surfacing as an error.
  }
}

const items = computed(() => [
  {
    icon: PanelLeft,
    title: 'The sidebar',
    body: 'Assistant is always at the top. Community holds requests, ledger, events and votes. Insights holds every statistical pack this tenant has enabled. Sections collapse and stay collapsed.'
  },
  {
    icon: Gauge,
    title: 'Evidence cards',
    body: 'Every number on Quorum shows its sample size and interval, and links to the method behind it. "Waiting" is not a bug - it means there is not yet enough data for a trustworthy reading, and it says so plainly rather than guessing.'
  },
  {
    icon: Sparkles,
    title: 'Ask the assistant',
    body: 'The assistant narrates real numbers and finds groups or events for you - it never invents a statistic of its own.',
    to: `/t/${props.slug}/assistant`,
    linkLabel: 'Open the assistant'
  },
  {
    icon: PlusCircle,
    title: `Raise a ${props.requestLabel.toLowerCase()}`,
    body: `Describe the issue, pick a category and a group, and it enters request_flow - the same stream every reliability figure on this tenant is built from.`,
    to: `/t/${props.slug}/requests/new`,
    linkLabel: `Raise a ${props.requestLabel.toLowerCase()}`
  }
])
</script>

<template>
  <div v-if="!dismissed" class="card getting-started">
    <div class="chead">
      <div>
        <h3>New here?</h3>
        <div class="sub">A one-minute orientation to how Quorum is laid out.</div>
      </div>
      <button type="button" class="tgl icon-tgl" aria-label="Dismiss getting-started guide" @click="dismiss">
        <X :size="16" />
      </button>
    </div>

    <div class="getting-started-grid">
      <div v-for="it in items" :key="it.title" class="getting-started-item">
        <div class="getting-started-icon"><component :is="it.icon" :size="17" /></div>
        <div>
          <div class="getting-started-title">{{ it.title }}</div>
          <p class="getting-started-body">{{ it.body }}</p>
          <router-link v-if="it.to" class="getting-started-link" :to="it.to">{{ it.linkLabel }}</router-link>
        </div>
      </div>
    </div>

    <button type="button" class="btn btn-ghost getting-started-done" @click="dismiss"><span>Got it, hide this</span></button>
  </div>
</template>
