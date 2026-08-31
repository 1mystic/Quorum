<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import AuditLine from '../components/evidence/AuditLine.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { decisionById } from '../fixtures/decisions'

// The mandatory Condorcet-cycle disclosure per docs/STATS_CATALOG.md's
// voting.schulze card: when a cycle exists, it is shown alongside the
// winner, never hidden behind whichever rule broke the tie. There is no
// summary-collapse for this - it is a `callout`, not a `details.why`.
//
// Still fixture-backed, matching DecisionsView.vue: GET
// /api/t/{slug}/decisions/{id} is real, but it returns the raw row, not the
// tabulated Evidence this page exists to show, and there is no seeded
// tenant with real ballots to materialize one from yet.

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const decision = computed(() => decisionById(slug.value, route.params.id))
const value = computed(() => decision.value?.evidence?.value || null)

function cell(a, b) {
  const row = value.value.pairwise.find((p) => (p.a === a && p.b === b) || (p.a === b && p.b === a))
  if (!row) return { text: '-', cls: 'self' }
  if (row.a === a) return { text: `${row.a_votes}-${row.b_votes}`, cls: row.a_votes > row.b_votes ? 'win' : 'lose' }
  return { text: `${row.b_votes}-${row.a_votes}`, cls: row.b_votes > row.a_votes ? 'win' : 'lose' }
}
</script>

<template>
  <TenantShell v-if="decision" :title="decision.title" :subtitle="`${tenant.labels.decision} · ${decision.status}`">
    <div v-if="!decision.evidence" class="card">
      <div class="chead"><div><h3>Ballot still open</h3><div class="sub">turnout {{ decision.turnout }} of {{ decision.eligible }} eligible</div></div></div>
      <p style="font-size:14.5px;color:var(--ink-2)">Results are tabulated once this {{ tenant.labels.decision.toLowerCase() }} closes. Per docs/STATS_API.md, a governance tabulation runs on decision close and is frozen: it is never recomputed once published.</p>
    </div>

    <template v-else>
      <div class="row" style="grid-template-columns:1fr">
        <div class="card">
          <div class="chead">
            <div><h3>Result</h3><div class="sub">voting.schulze · Condorcet-consistent · n {{ decision.evidence.n }}</div></div>
            <span class="pill" :class="value.is_condorcet_winner ? 'p-est' : 'p-qual'">{{ value.is_condorcet_winner ? 'Condorcet winner' : 'Schulze winner' }}</span>
          </div>
          <div class="big" style="font-size:1.8rem">{{ value.winner }}</div>

          <div v-if="value.cycle_disclosed" class="callout callout-warn">
            <span>
              <b>Condorcet cycle present.</b>
              {{ decision.evidence.checks.find((c) => c.id === 'condorcet-cycle-present')?.detail }}
              This is shown here, not hidden behind the winner: {{ value.winner }} is the resolution of a cycle, not the option that beat every other option head to head.
            </span>
          </div>
          <div v-else class="callout callout-info">
            <span><b>{{ value.winner }}</b> beat every other option head to head. No cycle.</span>
          </div>

          <h3 style="margin-top:var(--sp3)">Ranking</h3>
          <ol style="padding-left:1.4em;font-size:14.5px;color:var(--ink-2);display:flex;flex-direction:column;gap:6px">
            <li v-for="opt in value.ranking" :key="opt">{{ opt }}</li>
          </ol>

          <h3 style="margin-top:var(--sp3)">Pairwise matrix</h3>
          <div class="tbl-scroll">
            <table class="matrix">
              <thead><tr><th></th><th v-for="opt in decision.options" :key="'h-' + opt">{{ opt }}</th></tr></thead>
              <tbody>
                <tr v-for="a in decision.options" :key="'r-' + a">
                  <th>{{ a }}</th>
                  <td v-for="b in decision.options" :key="'c-' + a + b" :class="a === b ? 'self' : cell(a, b).cls">
                    {{ a === b ? 'self' : cell(a, b).text }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <AuditLine :evidence="decision.evidence" />
        </div>
      </div>
    </template>
  </TenantShell>

  <TenantShell v-else title="Not found">
    <div class="empty-state"><h3>No such decision</h3><p><router-link :to="`/t/${slug}/decisions`">Back to decisions</router-link></p></div>
  </TenantShell>
</template>
