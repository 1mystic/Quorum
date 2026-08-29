<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, Pin, PinOff, Trash2, Megaphone } from 'lucide-vue-next'
import LeaderSidebar from '../components/layout/LeaderSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import AnnounceCard from '../components/ui/AnnounceCard.vue'
import LeaderClubSwitcher from '../components/ui/LeaderClubSwitcher.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import { getLeaderAnnouncements, togglePin, deleteAnnouncement } from '../api/announcements'
import { toast } from '../composables/useToast'
import { cachedFetch, invalidateCache } from '../utils/apiCache'
import { useClubsStore } from '../stores/clubs'

const router = useRouter()
const route = useRoute()

const posts = ref([])
const clubsStore = useClubsStore()
const activeFilter = ref('all')
const loading = ref(true)

const filterChips = [
  { id: 'all', label: 'All' },
  { id: 'pinned', label: 'Pinned' },
  { id: 'general', label: 'General' },
  { id: 'event_update', label: 'Event Updates' },
  { id: 'resource', label: 'Resources' },
  { id: 'achievement', label: 'Achievements' },
  { id: 'urgent', label: 'Urgent' }
]

const visiblePosts = computed(function filterPosts() {
  return posts.value.filter(function matchesFilter(post) {
    if (activeFilter.value === 'all') {
      return true
    }

    if (activeFilter.value === 'pinned') {
      return post.pinned
    }

    return post.category === activeFilter.value
  })
})

// Several announcements can sit on screen at once, so "in flight" is tracked
// per announcement id rather than one flag for the whole page.
const busyPostIds = ref(new Set())

function isPostBusy(postId) {
  return busyPostIds.value.has(postId)
}

function announcementsCacheKey() {
  return `leader-announcements:${clubsStore.selectedLeaderClub?.id}`
}

async function handleTogglePin(post) {
  busyPostIds.value.add(post.id)
  try {
    const newPinnedState = !post.pinned

    await togglePin(post.id, newPinnedState)

    invalidateCache(announcementsCacheKey())
    await loadAnnouncements()

    toast.success(
      newPinnedState
        ? 'Announcement pinned.'
        : 'Announcement unpinned.'
    )
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  } finally {
    busyPostIds.value.delete(post.id)
  }
}

async function handleDelete(post) {
  const confirmed = window.confirm(
    'Delete this announcement? Members will no longer see it.'
  )

  if (!confirmed) return

  busyPostIds.value.add(post.id)
  try {
    await deleteAnnouncement(post.id)

    invalidateCache(announcementsCacheKey())
    await loadAnnouncements()

    toast.success('Announcement deleted.')
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  } finally {
    busyPostIds.value.delete(post.id)
  }
}

async function loadAnnouncements() {
  if (!clubsStore.selectedLeaderClub) return

  loading.value = true

  try {
    const data = await cachedFetch(
      announcementsCacheKey(),
      () => getLeaderAnnouncements({ club_id: clubsStore.selectedLeaderClub.id })
    )

    posts.value = data.map(post => ({
      ...post,
      pinned: post.is_pinned,
      category: post.category.toLowerCase()
    }))
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  } finally {
    loading.value = false
  }
}

function goToPostAnnouncement() {
  router.push(`/${route.params.slug}/leader/announcements/new`)
}

onMounted(async () => {
  try {
    await clubsStore.loadLeaderClubs()

    if (!clubsStore.selectedLeaderClub) {
      toast.error('No active club selected.')
      router.push(`/${route.params.slug}/leader/club`)
      return
    }

    await loadAnnouncements()
  } catch (error) {
    toast.error(error?.message || 'Something went wrong.')
  }
})

</script>

<template>
  <LeaderSidebar />

  <div class="main-content">

    <Topbar title="Announcements" sub="Create and manage announcements" :show-bell="false">
      <template #actions>
        <LeaderClubSwitcher @change="loadAnnouncements" />
        <button class="btn-primary" @click="goToPostAnnouncement">
          <Plus /> Post Announcement
        </button>
      </template>
    </Topbar>

    <main class="content-body custom-scrollbar">

      <div class="announce-layout">
        <div>

          <FilterChips :chips="filterChips" v-model="activeFilter" />
          
          <div v-if="loading" class="page-loading-state">
            <div class="empty-state">
              <p>Loading announcements...</p>
            </div>
          </div>

          <div v-else-if="visiblePosts.length === 0" class="empty-state empty-state-wide">
            <Megaphone />
              <p>No announcements match this filter.</p>
          </div>

          <div v-else class="announce-feed">
            <AnnounceCard
               v-for="post in visiblePosts"
                :key="post.id"
                :announcement="post"
            >
            <template #actions>
              <div class="announce-manage-row">
                <button class="announce-action-btn" :disabled="isPostBusy(post.id)" @click="handleTogglePin(post)">
                  <span v-if="isPostBusy(post.id)" class="btn-spinner"></span>
                  <template v-else>
                    <PinOff v-if="post.pinned" />
                    <Pin v-else />
                    {{ post.pinned ? 'Unpin' : 'Pin' }}
                  </template>
                </button>

                <button
                  class="announce-action-btn delete"
                  :disabled="isPostBusy(post.id)"
                  @click="handleDelete(post)"
                >
                  <span v-if="isPostBusy(post.id)" class="btn-spinner"></span>
                  <template v-else><Trash2 /> Delete</template>
                </button>
              </div>
            </template>
            </AnnounceCard>
        </div>

        </div>
      </div>

    </main>

  </div>
</template>
