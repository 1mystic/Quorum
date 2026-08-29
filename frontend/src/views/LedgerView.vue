<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import StatTile from '../components/evidence/StatTile.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { ledgerFor, formatMinor } from '../fixtures/ledger'
import { toast } from '../composables/useToast'

// docs/VERTICALS.md rwa_society: verification lag and receipt-collection gap
// are headline statistics here, each a survival curve / Wilson interval over
// a censored duration, not an average - see the two StatTiles below. The
// ledger stream has no Campus Connect analogue; this view is built fresh
// against docs/DATA_SPINE.md §3.

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const ledger = computed(() => ledgerFor(slug.value))

const markedPaid = ref(new Set())

function markPaid(entry) {
  markedPaid.value.add(entry.entry_ref)
  toast.success(`${entry.entry_ref} marked paid, pending treasurer verification. UI stub until the ledger write path lands.`)
}

function statusBadge(status) {
  const map = { settled: 'badge-resolved', pending: 'badge-pending', expected: 'badge-open', failed: 'badge-escalated', reversed: 'badge-escalated', written_off: 'badge-pending' }
  return 'badge ' + (map[status] || 'badge-pending')
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
      <div class="chead"><div><h3>Entries</h3><div class="sub">signed money movement, most recent first</div></div></div>
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
                  :disabled="markedPaid.has(e.entry_ref)"
                  @click="markPaid(e)"
                >{{ markedPaid.has(e.entry_ref) ? 'Marked' : 'Mark paid' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </TenantShell>
</template>
