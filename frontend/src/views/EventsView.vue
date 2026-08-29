<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { eventsFor } from '../fixtures/events'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
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
