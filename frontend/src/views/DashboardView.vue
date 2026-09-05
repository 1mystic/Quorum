<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { PlusCircle, Sparkles, Wallet, CalendarCheck, ClipboardCheck, ListChecks, Settings } from 'lucide-vue-next'
import TenantShell from '../components/layout/TenantShell.vue'
import TenantPending from '../components/layout/TenantPending.vue'
import GettingStartedCard from '../components/layout/GettingStartedCard.vue'
import StatTile from '../components/evidence/StatTile.vue'
import SurvivalCurve from '../components/evidence/SurvivalCurve.vue'
import { useTenant } from '../composables/useTenant'
import { packMeta } from '../fixtures/tenants'
import { operationsPack, forecastPack } from '../fixtures/insights'
import { ledgerSummary } from '../fixtures/ledger'
import { requestsFor } from '../fixtures/requests'
import { eventsFor } from '../fixtures/events'
import { membersFor } from '../fixtures/members'
import { useAuthStore } from '../stores/auth'

// The tenant home: one headline figure per enabled pack (per
// docs/VERTICALS.md's "headline statistics for the tenant home" lists),
// the flagship KM curve, recent activity and a way into every pack. This is
// deliberately not the Pack 1 Operations page again: that page (and its
// control chart) lives at insights/operations.

const route = useRoute()
const auth = useAuthStore()
const slug = computed(() => route.params.slug)
const { tenant, loading: tenantLoading, error: tenantError } = useTenant(slug)

// These three packs are still hand-written fixtures keyed by the two demo
// slugs only (docs/CONTEXT.md's "depth pass" TODO), so a real tenant this
// session onboarded or signed into has no entry here - `|| null` plus the
// template's own v-if is what keeps that a calm "not ready yet" panel
// instead of the exact `ops.value.tiles[3]` crash this bug report named.
const ops = computed(() => operationsPack[slug.value] || null)
const forecast = computed(() => forecastPack[slug.value] || null)
const ledger = computed(() => ledgerSummary[slug.value] || null)

const fourthOpsTile = computed(() => (ops.value ? ops.value.tiles[3] : null))
const recentRequests = computed(() => requestsFor(slug.value).slice(0, 4))

// Role-aware shortcuts to the handful of things a session actually does day
// to day, capped at four so the `.row.r-4` grid it shares with the stat
// tiles below always lays out as one symmetric row, never a lone card
// stranded on a second row. "Raise a request" and "ask the assistant" are
// the stable pair (always relevant, never both inapplicable); dues and RSVP
// only surface when the data says the action is actually live right now.
// Casting a ballot is common enough to matter but not common enough to earn
// one of only four slots, so it stays a sidebar/Decisions-page action, not
// a dashboard shortcut.
const upcomingEvent = computed(() => eventsFor(slug.value).find((e) => e.status === 'upcoming'))
const duesOwed = computed(() => (ledger.value ? ledger.value.duesOwed : null))
const pendingApprovals = computed(() => membersFor(slug.value).filter((m) => m.status === 'pending').length)
const openRequestQueue = computed(() => requestsFor(slug.value).filter((r) => r.status !== 'resolved' && r.status !== 'closed').length)

const memberActions = computed(() => {
  const list = [
    { key: 'request', icon: PlusCircle, title: `Raise a ${tenant.value.labels.request.toLowerCase()}`, meta: 'always open', to: `/t/${slug.value}/requests/new` }
  ]
  if (duesOwed.value && !duesOwed.value.insufficient_data && duesOwed.value.value > 0) {
    list.push({ key: 'dues', icon: Wallet, title: `Pay your ${tenant.value.labels.ledger.toLowerCase()} dues`, meta: 'balance outstanding', to: `/t/${slug.value}/ledger` })
  }
  if (upcomingEvent.value) {
    list.push({ key: 'rsvp', icon: CalendarCheck, title: 'RSVP to an upcoming event', meta: upcomingEvent.value.title, to: `/t/${slug.value}/events/${upcomingEvent.value.id}` })
  }
  list.push({ key: 'assistant', icon: Sparkles, title: 'Ask the assistant', meta: 'groups, events, what\'s new', to: `/t/${slug.value}/assistant` })
  return list
})

const adminActions = computed(() => [
  { key: 'approvals', icon: ClipboardCheck, title: 'Pending approvals', meta: `${pendingApprovals.value} waiting`, to: `/t/${slug.value}/admin/approvals` },
  { key: 'queue', icon: ListChecks, title: `Open ${tenant.value.labels.request.toLowerCase()} queue`, meta: `${openRequestQueue.value} in flight`, to: `/t/${slug.value}/admin` },
  { key: 'settings', icon: Settings, title: 'Tenant settings', meta: 'vertical, packs, labels', to: `/t/${slug.value}/settings` }
])

const quickActions = computed(() => (auth.role === 'admin' ? adminActions.value : memberActions.value))

function has(packId) {
  return tenant.value.enabled_packs.includes(packId) || tenant.value.optional_packs.includes(packId)
}

const packLinks = computed(() => Object.values(packMeta).filter((p) => has(p.id)))

const packQuestions = {
  reliability_ops: 'Is this getting better or worse?',
  forecast_risk: 'What is coming, and how sure are we?',
  bayes_ranking: 'Is the new vendor actually better?',
  governance_insight: 'What does the community actually want?'
}

function badgeClass(status) {
  return 'badge badge-' + status.replace('_', '-').replace('in-progress', 'progress')
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <template v-if="tenant">
  <TenantShell title="Overview" :subtitle="`${tenant.name} · ${tenant.tagline}`" as-of="insight_run · contract v1">
    <GettingStartedCard :slug="slug" :request-label="tenant.labels.request" />

    <div class="row r-4">
      <router-link v-for="a in quickActions" :key="a.key" class="card qa-card" :to="a.to">
        <div class="qa-icon"><component :is="a.icon" :size="17" /></div>
        <div class="qa-body">
          <div class="qa-title">{{ a.title }}</div>
          <div class="qa-meta">{{ a.meta }}</div>
        </div>
      </router-link>
    </div>

    <template v-if="ops && forecast && ledger">
      <div class="row r-4">
        <StatTile :title="ops.tiles[0].title" :subtitle="ops.tiles[0].subtitle" :evidence="ops.tiles[0].evidence">
          <template v-if="ops.tiles[0].why" #why><p>{{ ops.tiles[0].why }}</p></template>
        </StatTile>
        <StatTile :title="`${tenant.labels.ledger} receipt gap`" subtitle="share of receipts never collected" :evidence="ledger.receiptGap">
          <template #why><p>Payment is bank transfer, WhatsApp screenshot and manual treasurer verification, so a receipt issued is not always a receipt collected. This is the honest share that goes uncollected, with a Wilson interval, not an average.</p></template>
        </StatTile>
        <StatTile :title="fourthOpsTile.title" :subtitle="fourthOpsTile.subtitle" :evidence="fourthOpsTile.evidence">
          <template v-if="fourthOpsTile.why" #why><p>{{ fourthOpsTile.why }}</p></template>
        </StatTile>
        <StatTile :title="forecast.calibration.title" :subtitle="forecast.calibration.subtitle" :evidence="forecast.calibration.evidence">
          <template #why><p>{{ forecast.calibration.why }}</p></template>
        </StatTile>
      </div>

      <div class="row r-32">
        <SurvivalCurve :title="ops.survival.title" :subtitle="ops.survival.subtitle" :evidence="ops.survival.evidence" />

        <div class="card">
          <div class="chead">
            <div><h3>Recent {{ tenant.labels.request.toLowerCase() }}s</h3><div class="sub">latest activity, request_flow</div></div>
          </div>
          <div class="list">
            <router-link v-for="r in recentRequests" :key="r.ref" class="list-row" :to="`/t/${slug}/requests/${r.ref}`">
              <div class="lr-main">
                <div class="lr-title">{{ r.title }}</div>
                <div class="lr-sub">{{ r.ref }} · {{ r.category.replace(/_/g, ' ') }} · opened {{ fmtDate(r.opened_at) }}</div>
              </div>
              <div class="lr-meta">
                <span :class="badgeClass(r.status)">{{ r.status.replace('_', ' ') }}</span>
              </div>
            </router-link>
          </div>
          <router-link class="tl" :to="`/t/${slug}/requests`">All {{ tenant.labels.request.toLowerCase() }}s</router-link>
        </div>
      </div>
    </template>

    <div v-else class="card empty-state">
      <h3>Not enough data yet</h3>
      <p>This tenant has no materialized insights to show on the overview yet. Headline figures appear here once enough activity has been recorded.</p>
    </div>

    <div class="row r-4">
      <router-link v-for="p in packLinks" :key="p.id" class="card" :to="`/t/${slug}/insights/${p.route.replace('insights-', '')}`">
        <div class="chead">
          <div><h3>Pack {{ p.number }} · {{ p.name }}</h3></div>
          <span class="pill p-est">Open</span>
        </div>
        <p style="color:var(--ink-2);font-size:14.5px;line-height:1.6">{{ packQuestions[p.id] }}</p>
      </router-link>
    </div>
  </TenantShell>
  </template>
  <TenantPending v-else :loading="tenantLoading" :error="tenantError" />
</template>

