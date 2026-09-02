<script setup>
import LandingNav from '../components/landing/LandingNav.vue'
import LandingFooter from '../components/landing/LandingFooter.vue'
import { demoTenantList } from '../fixtures/tenants'

// Summarised from docs/VERTICALS.md. A vertical is configuration, not code:
// labels, categories, roles and which packs default on, never a new
// statistical service. Two are demo-seedable today; the other five are
// selectable on /onboard but show "no demo data yet".

const verticals = [
  { id: 'rwa_society', name: 'Housing society', demo: true, tagline: 'Complaints, dues verification and vendor reliability for an apartment society.', packs: 'Operations, Foresight default; Voice, Comparison optional' },
  { id: 'campus_club', name: 'Campus club', demo: true, tagline: 'Issues, elections and engagement segmentation for a student club or chapter.', packs: 'Operations, Voice default; Foresight, Comparison optional' },
  { id: 'ngo_volunteer', name: 'NGO / volunteer programme', demo: false, tagline: 'Case intake with safeguarding priority and volunteer-tier segmentation.', packs: 'Operations, Foresight, Voice default; Comparison optional' },
  { id: 'alumni_chapter', name: 'Alumni chapter', demo: false, tagline: 'Sparse, bursty engagement; the interesting question is always re-engagement.', packs: 'Foresight, Comparison default; Operations, Voice optional' },
  { id: 'housing_coop', name: 'Housing cooperative', demo: false, tagline: 'Formal share ownership and statutory governance, close to a housing society but stricter.', packs: 'Operations, Foresight, Voice default (statutory voting makes Voice mandatory)' },
  { id: 'sports_club', name: 'Sports club', demo: false, tagline: 'Pairwise comparison, ladder play and match results, is the point rather than a corner case.', packs: 'Operations, Comparison default; Foresight, Voice optional' },
  { id: 'professional_guild', name: 'Professional guild', demo: false, tagline: 'A paid annual membership lifecycle; renewal and CPD engagement are what matters.', packs: 'Operations, Foresight, Voice default; Comparison optional' }
]

function demoLink(id) {
  return demoTenantList.find((t) => t.vertical === id)
}
</script>

<template>
  <div>
    <LandingNav />
    <section class="sec">
      <div class="wrap">
        <div class="sec-head">
          <div class="sec-no"><b>·</b> Verticals</div>
          <div>
            <h1 style="font-size:var(--fs-h2)">Seven communities. One codebase.</h1>
            <p style="color:var(--ink-2);margin-top:var(--sp4);max-width:70ch">
              A vertical is configuration, not code: a frozen manifest naming labels, categories, roles and which
              Insight Packs default on. No statistical service knows a vertical exists. Two verticals are seeded
              with enough history to be demo-seedable today; the rest are selectable but not yet backed by fixture
              data.
            </p>
          </div>
        </div>

        <div class="card">
          <div class="list">
            <div v-for="v in verticals" :key="v.id" class="list-row" style="cursor:default">
              <div class="lr-main">
                <div class="lr-title">{{ v.name }}</div>
                <div class="lr-sub">{{ v.tagline }}</div>
                <div class="lr-sub">packs: {{ v.packs }}</div>
              </div>
              <div class="lr-meta">
                <span class="pill" :class="v.demo ? 'p-est' : 'p-wait'">{{ v.demo ? 'Demo seeded' : 'No demo data yet' }}</span>
                <router-link v-if="v.demo" class="tl" :to="`/t/${demoLink(v.id).slug}/dashboard`">Open {{ demoLink(v.id).name }}</router-link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
    <LandingFooter />
  </div>
</template>
