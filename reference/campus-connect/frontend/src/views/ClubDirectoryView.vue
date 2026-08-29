<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, SearchX, Users, Sparkles } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import ClubCard from '../components/ui/ClubCard.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import { useClubsStore } from '../stores/clubs'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const clubsStore = useClubsStore()

const searchText = ref('')
const activeCategory = ref('all')

const categoryChips = [
  { id: 'all', label: 'All' },
  { id: 'Tech', label: 'Tech' },
  { id: 'Arts', label: 'Arts' },
  { id: 'Culture', label: 'Culture' },
  { id: 'Sports', label: 'Sports' },
  { id: 'Music', label: 'Music' },
  { id: 'Business', label: 'Business' },
  { id: 'Science', label: 'Science' }
]

// A club this student leads already has its own dedicated space (the Leader
// pages) and shows up in "My Clubs" below - listing it again here, in the
// directory meant for discovering clubs to join, is just noise.
const ledClubIds = computed(() =>
  new Set(
    clubsStore.joinedClubs
      .filter((club) => club.membership_role === 'LEADER')
      .map((club) => club.id)
  )
)

const visibleClubs = computed(function filterClubs() {
  const search = searchText.value.toLowerCase().trim()

  return clubsStore.clubs.filter(function matchesClub(club) {
    if (ledClubIds.value.has(club.id)) return false

    const categoryMatch = activeCategory.value === 'all' || (club.category || '').toLowerCase() === activeCategory.value.toLowerCase()

    const searchMatch = search === '' || club.name.toLowerCase().includes(search) || (club.category || '').toLowerCase().includes(search)
      return categoryMatch && searchMatch})
})

const myClubs = computed(() => clubsStore.joinedClubs)

function openClub(clubId) {
  router.push(`/${route.params.slug}/clubs/${clubId}`)
}

// clubsStore.clubs/joinedClubs both start empty, and the fetch can take a
// few seconds - so "No clubs match your search" and "you haven't joined any
// clubs yet" both appeared as the FIRST thing on screen before the real list
// arrived. isLoading distinguishes "nothing fetched yet" from "fetched, and
// there genuinely isn't anything".
const isLoading = ref(true)

onMounted(async function loadDirectory() {
  try {
    await clubsStore.loadClubs()
  } catch (error) {
    toast.error(error?.message || 'Failed to load clubs.')
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <Topbar title="Discover Clubs" :sub="clubsStore.clubs.length + ' active clubs at your college'" />

    <main class="content-body clubs-content custom-scrollbar">

      <div>
        <div class="clubs-section-header">
          <h2 class="clubs-section-title">Recommended for You</h2>
        </div>

        <div v-if="isLoading" class="page-loading-state">
          <div class="empty-state">
            <p>Finding recommendations...</p>
          </div>
        </div>

        <div v-else-if="clubsStore.recommendedClubs.length" class="clubs-grid">
          <ClubCard
            v-for="club in clubsStore.recommendedClubs"
            :key="club.id"
            :club="club"
            badge="Recommended"
            @open="openClub(club.id)"
          />
        </div>

        <div v-else class="empty-state empty-state-wide">
          <Sparkles />
          <p>
            You're already in every active club here. Check "All Clubs" below for
            anything new, or use the AI Finder to discover clubs on other topics.
          </p>
        </div>
      </div>

      <div>
  <div class="clubs-section-header">
    <h2 class="clubs-section-title">My Clubs</h2>
  </div>

  <div v-if="myClubs.length" class="clubs-grid">
    <ClubCard
      v-for="club in myClubs"
      :key="club.id"
      :club="club"
      @open="openClub(club.id)"
    />
  </div>

  <div v-else-if="isLoading" class="page-loading-state">
    <div class="empty-state">
      <p>Loading your clubs...</p>
    </div>
  </div>

  <div v-else class="empty-state">
    <Users />
    <p>You haven't joined any clubs yet. Explore clubs below and send a join request.</p>
  </div>
</div>


      <div>
        <div class="clubs-section-header">
          <h2 class="clubs-section-title">All Clubs</h2>
          <span class="clubs-count-text">{{ visibleClubs.length }} clubs</span>
        </div>

        <div class="search-pill search-pill-wide">
          <Search />
          <input
            type="text"
            v-model="searchText"
            placeholder="Search by name or category..."
          >
        </div>

        <FilterChips :chips="categoryChips" v-model="activeCategory" />

        <div class="clubs-grid">
          <ClubCard
            v-for="club in visibleClubs"
            :key="club.id"
            :club="club"
            @open="openClub(club.id)"
          />
        </div>

        <div v-if="isLoading" class="page-loading-state">
          <div class="empty-state">
            <p>Loading clubs...</p>
          </div>
        </div>

        <div v-else-if="visibleClubs.length === 0" class="empty-state empty-state-wide">
          <SearchX />
          <p>No clubs match your search. Try a different keyword or category.</p>
        </div>

      </div>

    </main>

  </div>
</template>