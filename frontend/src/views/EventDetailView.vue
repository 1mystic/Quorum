<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { eventById } from '../fixtures/events'
import { formatMinor } from '../fixtures/ledger'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const event = computed(() => eventById(slug.value, route.params.id))

function fmt(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
const noShowRate = computed(() => {
  const e = event.value
  if (!e || e.attended === null || !e.rsvp) return null
  return Math.max(0, ((e.rsvp - e.attended) / e.rsvp) * 100).toFixed(0)
})
</script>

<template>
  <TenantShell
    v-if="event" :title="event.title" :subtitle="`${fmt(event.starts_at)} · ${event.location}`"
    :back-to="`/t/${slug}/events`" back-label="Events"
  >
    <div class="row r-4">
      <div class="card"><div class="chead"><div><h3>RSVP</h3></div></div><div class="big">{{ event.rsvp }}<span class="u">of {{ event.capacity }}</span></div></div>
      <div class="card">
        <div class="chead"><div><h3>Attended</h3></div></div>
        <div class="big">{{ event.attended ?? 'n/a' }}</div>
        <div v-if="noShowRate !== null" class="meta"><span><b>no-show</b> {{ noShowRate }}%</span></div>
      </div>
      <div class="card"><div class="chead"><div><h3>Collected</h3></div></div><div class="big">{{ formatMinor(event.fund.collected_minor, event.fund.currency) }}</div></div>
      <div class="card"><div class="chead"><div><h3>Spent</h3></div></div><div class="big">{{ formatMinor(event.fund.spent_minor, event.fund.currency) }}</div></div>
    </div>

    <div class="card">
      <div class="chead"><div><h3>Fund summary</h3><div class="sub">{{ tenant.labels.ledger }} · campaign entries for this event</div></div></div>
      <div class="meta">
        <span><b>net</b> {{ formatMinor(event.fund.collected_minor - event.fund.spent_minor, event.fund.currency) }}</span>
        <span v-if="event.status === 'upcoming'">Fund is still open; totals will settle after the event closes.</span>
      </div>
    </div>
  </TenantShell>

  <TenantShell v-else title="Not found">
    <div class="empty-state"><h3>No such event</h3><p><router-link :to="`/t/${slug}/events`">Back to events</router-link></p></div>
  </TenantShell>
</template>
