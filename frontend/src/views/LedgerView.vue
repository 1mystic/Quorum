<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { ledgerFor, formatMinor } from '../fixtures/ledger'
import { toast } from '../composables/useToast'
import { myDues, recordPayment } from '../api/ledger'
import { useAsyncData } from '../composables/useAsyncData'

// docs/VERTICALS.md rwa_society: verification lag and receipt-collection gap
// are headline statistics here, each a survival curve / Wilson interval over
// a censored duration (see the two StatTiles below). Those, and the
// tenant-wide "Entries" table, still read `fixtures/ledger.js`: they need
// either a materialized insight_runs row (Pack 1, no seed data yet, see
// CONTEXT.md's C.19) or a "list every ledger entry" endpoint that
// app/api/ledger.py does not have (it only has /dues/me plus one-at-a-time
// write routes). "Your dues" below is real - GET .../ledger/dues/me.

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const ledger = computed(() => ledgerFor(slug.value))

const markedPaid = ref(new Set())
const markedPaidFixture = ref(new Set())

// The fixture "Entries" table's own mark-paid is a UI stub, same as before:
// there is no real entry underneath it to record a payment against.
function markPaidFixtureEntry(entry) {
  markedPaidFixture.value.add(entry.entry_ref)
  toast.success(`${entry.entry_ref} marked paid, pending treasurer verification. UI stub, fixture-backed.`)
}

const { loading: duesLoading, error: duesError, data: duesData, run: runDues } = useAsyncData()
const myDuesList = computed(() => duesData.value || [])

function loadMyDues() {
  runDues(() => myDues(slug.value))
}
onMounted(loadMyDues)

async function markPaid(due) {
  try {
    await recordPayment(slug.value, {
      amount_minor: due.amount_minor,
      category: due.category,
      subcategory: due.subcategory,
      instrument: 'upi',
      at: new Date().toISOString(),
      due_id: due.id,
      currency: due.currency
    })
    markedPaid.value.add(due.id)
    toast.success(`Due #${due.id} marked paid, pending treasurer verification.`)
    loadMyDues()
  } catch (err) {
    toast.error(err.message || 'Could not record the payment.')
  }
}

function statusBadge(status) {
  const map = { settled: 'badge-resolved', pending: 'badge-pending', expected: 'badge-open', failed: 'badge-escalated', reversed: 'badge-escalated', written_off: 'badge-pending' }
  return 'badge ' + (map[status.toLowerCase()] || 'badge-pending')
}
</script>

<template>
  <TenantShell :title="tenant.labels.ledger" :subtitle="`ledger · ${ledger.summary.cycleLabel}`">
    <div class="row r-4">
      <div class="card">
        <div class="chead"><div><h3>Dues owed</h3><div class="sub">{{ ledger.summary.duesOwedCount }} outstanding</div></div></div>
        <div class="big">{{ formatMinor(ledger.summary.duesOwed * 100, ledger.summary.currency) }}</div>
      </div>
      <div class="card">
        <div class="chead"><div><h3>Collected this cycle</h3><div class="sub">{{ ledger.summary.collectedThisCycleCount }} entries</div></div></div>
        <div class="big">{{ formatMinor(ledger.summary.collectedThisCycle * 100, ledger.summary.currency) }}</div>
      </div>
      <StatTile title="Verification lag" subtitle="payment made to treasurer confirmed" :evidence="ledger.summary.verificationLag">
        <template #why>
          <p>Cash and screenshots handed off outside the app mean confirmation is a manual step, not an automatic one. This is a survival curve over a censored duration, not an average, because a handful of payments are still awaiting confirmation.</p>
        </template>
      </StatTile>
      <StatTile title="Receipt collection gap" subtitle="issued receipts never collected" :evidence="ledger.summary.receiptGap">
        <template #why>
          <p>A receipt sitting uncollected at the treasurer's desk is the single most common reconciliation gap the interview evidence found. This is a Wilson interval on a proportion, not a raw percentage.</p>
        </template>
      </StatTile>
    </div>

    <div class="card">
      <div class="chead"><div><h3>Your dues</h3><div class="sub">live · GET .../ledger/dues/me</div></div></div>

      <div v-if="duesLoading" class="empty-state"><h3>Loading…</h3></div>
      <div v-else-if="duesError" class="callout callout-warn"><span>Could not load your dues: {{ duesError }}</span></div>
      <div v-else-if="!myDuesList.length" class="empty-state">
        <h3>Nothing owed</h3>
        <p>No open dues on your account right now.</p>
      </div>
      <div v-else class="tbl-scroll">
        <table class="tbl">
          <thead><tr><th>Due</th><th>Category</th><th class="r">Amount</th><th>Due date</th><th>Status</th><th></th></tr></thead>
          <tbody>
            <tr v-for="d in myDuesList" :key="d.id">
              <td class="dim">#{{ d.id }}</td>
              <td>{{ d.category.replace(/_/g, ' ') }}</td>
              <td class="r num">{{ formatMinor(d.amount_minor, d.currency) }}</td>
              <td class="dim">{{ new Date(d.due_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) }}</td>
              <td><span :class="statusBadge(d.status)">{{ d.status.replace('_', ' ').toLowerCase() }}</span></td>
              <td>
                <button
                  v-if="d.status === 'OPEN' || d.status === 'PARTIAL'"
                  class="btn btn-ghost" style="min-height:32px;padding:8px 12px;font-size:12px"
                  :disabled="markedPaid.has(d.id)"
                  @click="markPaid(d)"
                >{{ markedPaid.has(d.id) ? 'Marked' : 'Mark paid' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="chead"><div><h3>Entries</h3><div class="sub">fixture-backed · signed money movement, most recent first (no list-all endpoint yet, see comment above)</div></div></div>
      <div class="tbl-scroll">
        <table class="tbl">
          <thead>
            <tr><th>Entry</th><th>Category</th><th>Party</th><th>Instrument</th><th class="r">Amount</th><th>Status</th><th>Receipt</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="e in ledger.entries" :key="e.entry_ref">
              <td class="dim">{{ e.entry_ref }}</td>
              <td>{{ e.category.replace(/_/g, ' ') }}</td>
              <td>{{ e.member_ref || e.counterparty_ref || '-' }}</td>
              <td class="dim">{{ e.instrument.replace('_', ' ') }}</td>
              <td class="r num" :style="{ color: e.amount_minor < 0 ? 'var(--stop)' : 'var(--ok)' }">{{ formatMinor(e.amount_minor, e.currency) }}</td>
              <td><span :class="statusBadge(e.status)">{{ e.status.replace('_', ' ') }}</span></td>
              <td class="dim">
                <span v-if="!e.receipt_issued_at">not issued</span>
                <span v-else-if="e.receipt_collected_at">collected</span>
                <span v-else style="color:var(--warn)">issued, uncollected</span>
              </td>
              <td>
                <button
                  v-if="e.status === 'pending' || e.status === 'expected'"
                  class="btn btn-ghost" style="min-height:32px;padding:8px 12px;font-size:12px"
                  :disabled="markedPaidFixture.has(e.entry_ref)"
                  @click="markPaidFixtureEntry(e)"
                >{{ markedPaidFixture.has(e.entry_ref) ? 'Marked' : 'Mark paid' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </TenantShell>
</template>
