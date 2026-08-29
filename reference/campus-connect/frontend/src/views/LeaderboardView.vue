<script setup>
import { ref, computed, onMounted } from 'vue'
import { Crown, Trophy } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import ClubIcon from '../components/ui/ClubIcon.vue'
import { getLeaderboard } from '../api/leaderboard'
import { cachedFetch } from '../utils/apiCache'
import { bannerColourFor, iconNameFor } from '../utils/clubVisuals'
import { toast } from '../composables/useToast'

const entries = ref([])
const activeFilter = ref('all')
const isLoading = ref(true)

const filterChips = [
  { id: 'all', label: 'All Categories' },
  { id: 'tech', label: 'Tech' },
  { id: 'culture', label: 'Culture' },
  { id: 'arts', label: 'Arts' },
  { id: 'business', label: 'Business' },
  { id: 'sports', label: 'Sports' }
]

const TIER_BY_RANK = { 1: 'gold', 2: 'silver', 3: 'bronze' }
const RANK_WORD = { 1: '1st', 2: '2nd', 3: '3rd' }

function matchesActiveFilter(entry) {
  if (activeFilter.value === 'all') {
    return true
  }

  // Categories are free text set on the club (e.g. "Tech", "tech"), while the
  // filter chip ids are always lower case, so compare case-insensitively.
  return String(entry.category || '').toLowerCase() === activeFilter.value
}

const visibleEntries = computed(function filterEntries() {
  return entries.value.filter(matchesActiveFilter)
})

// Top 3 of the filtered set get the podium treatment; the rest are the list
// below it. Re-deriving this from the filtered entries (rather than always
// using the global top 3) keeps the podium meaningful when a category filter
// is active.
const podium = computed(function buildPodium() {
  return visibleEntries.value.slice(0, 3).map(function toPodiumCard(entry, index) {
    const position = index + 1

    return {
      rank: RANK_WORD[position],
      tier: TIER_BY_RANK[position],
      name: entry.name,
      score: entry.score,
      icon: iconNameFor(entry)
    }
  })
})

const rows = computed(function buildRows() {
  return visibleEntries.value.slice(3).map(function toRow(entry) {
    return {
      rank: entry.rank,
      name: entry.name,
      cat: entry.category,
      score: entry.score,
      dot: bannerColourFor(entry),
      icon: iconNameFor(entry)
    }
  })
})

onMounted(async function loadLeaderboard() {
  try {
    entries.value = await cachedFetch('leaderboard', getLeaderboard)
  } catch (error) {
    toast.error(error.message || 'Could not load the leaderboard.')
    entries.value = []
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <Topbar title="Leaderboard" sub="Clubs ranked by activity score" :show-bell="false" />

    <main class="content-body custom-scrollbar">

      <div class="leaderboard-section">

        <FilterChips :chips="filterChips" v-model="activeFilter" />

        <div v-if="isLoading" class="page-loading-state">
          <div class="empty-state">
            <p>Loading rankings...</p>
          </div>
        </div>

        <template v-else-if="entries.length">

          <div v-if="podium.length">
            <h2 class="clubs-section-title">Top Clubs</h2>
            <div class="podium-container">
              <div
                v-for="entry in podium"
                :key="entry.rank"
                class="podium-card"
                :class="entry.tier"
              >
                <div v-if="entry.tier === 'gold'" class="podium-crown">
                  <Crown />
                </div>
                <p class="podium-rank">{{ entry.rank }}</p>
                <div class="podium-avatar">
                  <ClubIcon :name="entry.icon" />
                </div>
                <p class="podium-name">{{ entry.name }}</p>
                <p class="podium-score">{{ entry.score }}</p>
                <p class="text-note">pts</p>
              </div>
            </div>
          </div>

          <div>
            <div class="clubs-section-header">
              <h2 class="clubs-section-title">Full Rankings</h2>
              <span class="text-note">{{ visibleEntries.length }} clubs ranked</span>
            </div>

            <div class="lb-list">
              <div v-for="row in rows" :key="row.rank" class="lb-row">
                <span class="lb-rank">{{ row.rank }}</span>
                <div class="lb-club-dot" :class="row.dot">
                  <ClubIcon :name="row.icon" />
                </div>
                <div class="lb-info">
                  <p class="lb-club-name">{{ row.name }}</p>
                  <p class="lb-club-cat">{{ row.cat }}</p>
                </div>
                <div class="lb-score-col">
                  <p class="lb-score">{{ row.score }}</p>
                  <p class="lb-score-label">pts</p>
                </div>
              </div>
            </div>

            <div v-if="visibleEntries.length === 0" class="empty-state empty-state-wide">
              <Trophy />
              <p>No clubs in this category yet.</p>
            </div>
          </div>

        </template>

        <div v-else class="empty-state empty-state-wide">
          <Trophy />
          <p>Rankings will appear once clubs start earning activity points.</p>
        </div>

        <div class="club-profile-meta">
          <p class="section-heading">How is the score calculated?</p>
          <p class="body-text">Activity score is calculated from the total number of events held (40 pts each), member count growth (5 pts per new member), average attendance rate (up to 200 pts bonus), and issues resolved (10 pts each).</p>
        </div>

      </div>

    </main>

  </div>
</template>
