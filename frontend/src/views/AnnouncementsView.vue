<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { announcementsFor } from '../fixtures/announcements'

// TODO(frontend): still fixture-backed. GET /api/t/{slug}/announcements is
// real (app/api/announcement.py); out of this session's scope, see
// RequestsView.vue/LedgerView.vue for the pages that were swapped.
const route = useRoute()
const slug = computed(() => route.params.slug)
const list = computed(() => announcementsFor(slug.value).slice().sort((a, b) => (b.pinned - a.pinned) || (new Date(b.posted_at) - new Date(a.posted_at))))

function fmt(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <TenantShell title="Announcements" :subtitle="`${list.length} posted`">
    <div v-for="a in list" :key="a.id" class="card">
      <div class="chead">
        <div>
          <h3>{{ a.title }}<span v-if="a.pinned" class="flag" style="margin-left:10px">Pinned</span></h3>
          <div class="sub">{{ a.posted_by }} · {{ fmt(a.posted_at) }} · {{ a.category }}</div>
        </div>
      </div>
      <p style="font-size:14.5px;line-height:1.65;color:var(--ink-2)">{{ a.body }}</p>
    </div>
  </TenantShell>
</template>
