<script setup>
import { ref, computed, onMounted } from 'vue'
import { Megaphone, CheckCheck } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import AnnounceCard from '../components/ui/AnnounceCard.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import { getAnnouncements } from '../api/announcements'
import { cachedFetch } from '../utils/apiCache'
import { useChipFilter } from '../composables/useChipFilter'
import { toast } from '../composables/useToast'
import { useAnnouncementsStore } from '../stores/announcements'

const announcements = ref([])
const loading = ref(true)

const announcementsStore = useAnnouncementsStore()

const filterChips = [
  { id: 'all', label: 'All' },
  { id: 'pinned', label: 'Pinned' },
  { id: 'general', label: 'General' },
  { id: 'event_update', label: 'Event Updates' },
  { id: 'resource', label: 'Resources' },
  { id: 'achievement', label: 'Achievements' },
  { id: 'urgent', label: 'Urgent' }
]

const announcementsList = computed(() => announcements.value)

const { activeFilter, filteredItems } = useChipFilter(announcementsList, function matchesCategory(announcement, filter) {
  if (filter === 'pinned') return announcement.pinned
  return announcement.category === filter
})

onMounted(async () => {
  loading.value = true

  try {
    const data = await cachedFetch('student-announcements', getAnnouncements)

    announcements.value = data.map(item => ({
      ...item,
      pinned: item.is_pinned,
      category: item.category.toLowerCase()
    }))

    await announcementsStore.markRead()
    
  } catch (error) {
    toast.error(error?.message || 'Failed to load announcements.')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <Topbar title="Announcements" sub="Updates from your clubs">
      <template #actions>
        <button class="btn-secondary-sm" @click="announcementsStore.markRead">
          <CheckCheck /> Mark all as read
        </button>
      </template>
    </Topbar>

    <main class="content-body custom-scrollbar">

      <div class="announce-layout">

        <div>
          <FilterChips :chips="filterChips" v-model="activeFilter" />


            <div v-if="loading" class="empty-state">
              <p>Loading announcements...</p>
            </div>
            <div v-else-if="filteredItems.length === 0" class="empty-state">
              <Megaphone />
                <p>No announcements match this filter.</p>
            </div>
            <div v-else class="announce-feed">
            <AnnounceCard
              v-for="announcement in filteredItems"
              :key="announcement.id"
              :announcement="announcement"
            />
            </div>
          </div>

      </div>

    </main>

  </div>
</template>
