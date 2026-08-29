<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ArrowLeft, Send } from 'lucide-vue-next'
import LeaderSidebar from '../components/layout/LeaderSidebar.vue'
import CustomSelect from '../components/ui/CustomSelect.vue'
import { postAnnouncement } from '../api/announcements'
import { toast } from '../composables/useToast'
import { useFormValidation } from '../composables/useFormValidation'
import { useClubsStore } from '../stores/clubs'
import { invalidateCache } from '../utils/apiCache'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { allFieldsFilled } = useFormValidation()

const isSubmitting = ref(false)

const clubName = ref('')
const clubId = ref(null)
const clubsStore = useClubsStore()

const announcementTitle = ref('')
const announcementCategory = ref('')
const announcementBody = ref('')
const isPinned = ref(false)

const categoryOptions = [
  { value: 'GENERAL', label: 'General' },
  { value: 'EVENT_UPDATE', label: 'Event Update' },
  { value: 'RESOURCE', label: 'Resource / Lab' },
  { value: 'ACHIEVEMENT', label: 'Achievement' },
  { value: 'URGENT', label: 'Urgent' }
]

const guideSteps = [
  {
    num: '1',
    text: 'Keep the title under 10 words. Members scan titles first before reading the body.'
  },
  {
    num: '2',
    text: 'State the who, what, when, and where in the first two sentences.'
  },
  {
    num: '3',
    text: 'Use the correct category so students can filter by topic in their feed.'
  },
  {
    num: '4',
    text: 'Pin only when the information is time-sensitive. Over-pinning reduces impact.'
  },
  {
    num: '5',
    text: 'All members of your club will see this in their Announcements feed immediately.'
  },
  {
    num: '!',
    text: 'Announcements cannot be edited after posting. Delete and re-post if corrections are needed.',
    warn: true
  }
]

function togglePinned() {
  isPinned.value = !isPinned.value
}

function goBackToFeed() {
  router.push(`/${route.params.slug}/leader/announcements`)
}

async function handlePostAnnouncement() {
  if (isSubmitting.value) return

  if (!clubId.value) {
    toast.error('No club selected.')
    return
  }

  const title = announcementTitle.value.trim()
  const body = announcementBody.value.trim()

  const fields = {
    title,
    category: announcementCategory.value,
    body
  }

  if (!allFieldsFilled(fields)) {
    toast.error('Please fill in all fields before posting.')
    return
  }

  if (title.length < 3 || title.length > 150) {
    toast.error('Title must be between 3 and 150 characters.')
    return
  }

  if (body.length < 5 || body.length > 5000) {
    toast.error('Message must be between 5 and 5000 characters.')
    return
  }

  isSubmitting.value = true
  try {
    await postAnnouncement({
      club_id: clubId.value,
      title,
      body,
      category: announcementCategory.value,
      is_pinned: isPinned.value
    })

    // The leader list this redirects to must not serve a copy without it.
    invalidateCache(`leader-announcements:${clubId.value}`)

    toast.success(
      isPinned.value
        ? 'Announcement posted and pinned successfully.'
        : 'Announcement posted successfully.'
    )

    // The leader feed and the student feed both cache this club's announcements -
    // both would otherwise miss the one just posted until their TTL expires.
    invalidateCache(`leader-announcements-${clubId.value}`)
    invalidateCache('student-announcements')

    router.push(`/${route.params.slug}/leader/announcements`)
  } catch (error) {
    toast.error(error.message)
  } finally {
    isSubmitting.value = false
  }
}

onMounted(async () => {
  try {
    await clubsStore.loadLeaderClubs()

    if (!clubsStore.selectedLeaderClub) {
      toast.error('No active club selected.')
      router.push(`/${route.params.slug}/leader/club`)
      return
    }

    clubId.value = clubsStore.selectedLeaderClub.id
    clubName.value = clubsStore.selectedLeaderClub.name

  } catch (error) {
    toast.error(error.message)
  }
})

</script>

<template>
  <LeaderSidebar />

  <div class="main-content">

    <header class="topbar">
      <button class="btn-secondary" @click="goBackToFeed">
        <ArrowLeft /> Feed
      </button>
      <div class="title-block">
        <h1 class="page-title">Post Announcement</h1>
        <p class="page-sub">{{ clubName }}</p>
      </div>
      <div class="topbar-spacer"></div>
    </header>

    <main class="content-body custom-scrollbar">

      <div class="form-guide-grid">

        <div class="form-card">
          <p class="form-card-title">Announcement Details</p>

          <div class="form-group">
            <label>Club</label>
            <input type="text" class="input-field" :value="clubName" readonly>
          </div>

          <div class="form-group">
            <label for="ann-title">Title</label>
            <input type="text" id="ann-title" v-model="announcementTitle" class="input-field" placeholder="Short, clear subject line" maxlength="150">
          </div>

          <div class="form-group">
            <label for="ann-category">Category</label>
            <CustomSelect v-model="announcementCategory" :options="categoryOptions" placeholder="Select category" />
          </div>

          <div class="form-group">
            <label for="ann-body">Message</label>
            <textarea id="ann-body" v-model="announcementBody" class="textarea-field" rows="5" placeholder="Write your announcement here. Be clear and specific so members know exactly what to do or expect." maxlength="5000"></textarea>
          </div>

          <div class="toggle-row">
            <div class="toggle-label-block">
              <p class="toggle-label">Pin this announcement</p>
              <p class="toggle-desc">Pinned announcements appear at the top of the feed with a highlighted border.</p>
            </div>
            <div class="toggle-switch" :class="{ on: isPinned }" @click="togglePinned"></div>
          </div>

          <button class="btn-primary" @click="handlePostAnnouncement" :disabled="isSubmitting">
            <span v-if="isSubmitting" class="btn-spinner"></span>
            <template v-else><Send /> Post Announcement</template>
          </button>
        </div>

        <div class="guide-card">
          <p class="guide-card-title">Writing good announcements</p>
          <div v-for="step in guideSteps" :key="step.text" class="guide-step">
            <span class="guide-step-num" :class="{ 'guide-step-warn': step.warn }">{{ step.num }}</span>
            <span>{{ step.text }}</span>
          </div>
        </div>

      </div>

    </main>

  </div>
</template>
