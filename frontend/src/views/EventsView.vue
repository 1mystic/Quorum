<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { eventsFor } from '../fixtures/events'

// TODO(frontend): still fixture-backed. GET/POST /api/t/{slug}/events is
// real (app/api/event.py) but was not in this session's scope (task focus
// was auth, requests, ledger, decisions); the response shape does not match
// this fixture's registrations/results fields one-to-one either, so this
// needs its own pass rather than a one-line swap.
const route = useRoute()
const slug = computed(() => route.params.slug)
const list = computed(() => eventsFor(slug.value))

function fmt(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<template>
  <TenantShell title="Events" :subtitle="`participation · ${list.length} total`">
    <div class="card">
      <div v-if="!list.length" class="empty-state">
        <h3>No events yet</h3>
      </div>
      <div v-else class="list">
        <router-link v-for="e in list" :key="e.id" class="list-row" :to="`/t/${slug}/events/${e.id}`">
          <div class="lr-main">
            <div class="lr-title">{{ e.title }}</div>
            <div class="lr-sub">{{ fmt(e.starts_at) }} · {{ e.location }} · {{ e.rsvp }} rsvp'd{{ e.attended !== null ? `, ${e.attended} attended` : '' }}</div>
          </div>
          <div class="lr-meta">
            <span class="badge" :class="e.status === 'upcoming' ? 'badge-open' : 'badge-closed'">{{ e.status }}</span>
          </div>
        </router-link>
      </div>
    </div>
  </TenantShell>
</template>
