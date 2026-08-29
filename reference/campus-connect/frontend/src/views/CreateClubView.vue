<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, Send, FileText } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import CustomSelect from '../components/ui/CustomSelect.vue'
import ClubProposalList from '../components/ui/ClubProposalList.vue'
import { createClub, getMyClubs } from '../api/clubs'
import { useAuthStore } from '../stores/auth'
import { useClubsStore } from '../stores/clubs'
import { toast } from '../composables/useToast'
import { useFormValidation } from '../composables/useFormValidation'
import { useGuidelinesStore } from '../stores/guidelines'
import { cachedFetch, invalidateCache } from '../utils/apiCache'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const clubsStore = useClubsStore()
const { allFieldsFilled, isValidEmail } = useFormValidation()
const guidelines = useGuidelinesStore()

// Clubs this student proposed, in every state. role=LEADER returns the ones
// they created, including PENDING ones the admin has not reviewed yet, which
// is exactly what the status stack below the form needs.
const proposals = ref([])
const loadingProposals = ref(true)

async function loadProposals() {
  loadingProposals.value = true

  try {
    proposals.value = await cachedFetch('my-clubs:LEADER', () => getMyClubs({ role: 'LEADER' }))
  } catch (error) {
    proposals.value = []
  } finally {
    loadingProposals.value = false
  }
}

onMounted(loadProposals)

const clubName = ref('')
const clubCategory = ref('')
const clubTagline = ref('')
const clubAbout = ref('')
const applicationLink = ref('')

function clearForm() {
  clubName.value = ''
  clubCategory.value = ''
  clubTagline.value = ''
  clubAbout.value = ''
  applicationLink.value = ''
}

const categoryOptions = [
  'Tech',
  'Arts',
  'Culture',
  'Sports',
  'Music',
  'Business',
  'Science',
  'Other'
]

const guideSteps = [
  {
    num: '1',
    text: 'Fill in your club details and submit this form.'
  },
  {
    num: '2',
    text: 'Your request goes to the Campus Council Admin for review.'
  },
  {
    num: '3',
    text: 'Admin approves or rejects within 2 to 3 working days and provides a written reason.'
  },
  {
    num: '4',
    text: 'Once approved, your club appears in the directory and students can request to join.'
  },
  {
    num: '!',
    text: 'Make sure your college email address is verified before submitting.',
    warn: true
  }
]

function goBack() {
  router.back()
}

function openTemplate() {
  window.open(guidelines.templateLink, '_blank', 'noopener')
}

const isSubmittingProposal = ref(false)

async function handleSubmit() {
  if (isSubmittingProposal.value) return

  const fields = {
    name: clubName.value,
    category: clubCategory.value,
    tagline: clubTagline.value,
    about: clubAbout.value,
    applicationLink: applicationLink.value
  }

  if (!allFieldsFilled(fields)) {
    toast.error('Please fill in all fields before submitting.')
    return
  }

  if (!/^https?:\/\//i.test(applicationLink.value.trim())) {
    toast.error(
      'Please paste a valid application document link (it should start with http).'
    )
    return
  }

  isSubmittingProposal.value = true

  try {
    const response = await createClub({
      name: clubName.value.trim(),
      description: clubAbout.value.trim(),
      category: clubCategory.value,
      type: 'OFFICIAL',
      links: [
        {
          label: 'Application Document',
          url: applicationLink.value.trim()
        }
      ]
    })

    // Not auth.setClubLeader(true) here - this form only ever creates an
    // OFFICIAL club, which always starts PENDING (see ClubService.create()).
    // There's nothing to manage until an admin approves it, so the nav item
    // should stay hidden until then, not unlock on submission.

    await clubsStore.refreshClubs()

    toast.success(response.message)

    // Stay on the page rather than redirecting: the proposal stack below now
    // shows the submission with its "Pending approval" status, which is the
    // answer to "what happened to my request?" that the redirect used to hide.
    clearForm()
    invalidateCache('my-clubs:LEADER')
    await loadProposals()

  } catch (error) {
    toast.error(error.message)
  } finally {
    isSubmittingProposal.value = false
  }
}
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <header class="topbar">
      <button class="btn-secondary" @click="goBack">
        <ArrowLeft /> Back
      </button>
      <div class="title-block">
        <h1 class="page-title">Propose a New Club</h1>
        <p class="page-sub">Submit your request for admin approval</p>
      </div>
      <div class="topbar-spacer"></div>
    </header>

    <main class="content-body custom-scrollbar">

      <div class="form-guide-grid propose-grid">

        <div class="propose-main">

        <div class="form-card">
          <p class="form-card-title">Club Details</p>

          <div class="form-group">
            <label for="club-name">Club Name</label>
            <input type="text" id="club-name" v-model="clubName" class="input-field" placeholder="e.g. Campus Gaming Club">
          </div>

          <div class="form-group">
            <label for="club-category">Category</label>
            <CustomSelect v-model="clubCategory" :options="categoryOptions" placeholder="Select a category" />
          </div>

          <div class="form-group">
            <label for="club-tagline">Tagline</label>
            <input type="text" id="club-tagline" v-model="clubTagline" class="input-field" placeholder="One sentence about your club (shown on the directory card)">
          </div>

          <div class="form-group">
            <label for="club-about">About the Club</label>
            <textarea id="club-about" v-model="clubAbout" class="textarea-field" rows="5" placeholder="Describe your club's mission, activities, and what members can expect..."></textarea>
          </div>

          <div class="form-group">
            <label for="club-app-link">Application Document Link</label>
            <input type="url" id="club-app-link" v-model="applicationLink" class="input-field" placeholder="https://drive.google.com/file/d/.../view">
            <p class="text-note">
              Copy the Google Docs template, fill it in, then paste the shareable
              Google Drive link of your completed application here.
            </p>
          </div>

          <button class="btn-primary" :disabled="isSubmittingProposal" @click="handleSubmit">
            <span v-if="isSubmittingProposal" class="btn-spinner"></span>
            <template v-else><Send /> Submit for Approval</template>
          </button>
        </div>

        <ClubProposalList :proposals="proposals" :loading="loadingProposals" />

        </div>

        <div class="guide-card">
          <p class="guide-card-title">What happens next</p>
          <div v-for="step in guideSteps" :key="step.text" class="guide-step">
            <span class="guide-step-num" :class="{ 'guide-step-warn': step.warn }">{{ step.num }}</span>
            <span>{{ step.text }}</span>
          </div>

          <button class="btn-secondary guide-template-btn" @click="openTemplate">
            <FileText /> Open application template
          </button>

          <div class="guide-glines">
            <p class="guide-card-title">Campus club guidelines</p>
            <div
              v-for="section in guidelines.sectionsList"
              :key="section"
              class="guide-glines-section"
            >
              <p class="guide-glines-heading">{{ section }}</p>
              <div
                v-for="item in guidelines.itemsBySection(section)"
                :key="item.id"
                class="guide-gline-item"
              >
                <span class="guide-gline-dot"></span>
                <span>{{ item.text }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>

    </main>

  </div>
</template>
