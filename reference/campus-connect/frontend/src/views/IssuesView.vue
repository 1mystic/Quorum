<script setup>
import { ref, computed, onMounted } from 'vue'
import { MessageSquareWarning, Send, Inbox } from 'lucide-vue-next'
import StudentSidebar from '../components/layout/StudentSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import CustomSelect from '../components/ui/CustomSelect.vue'
import IssueCard from '../components/ui/IssueCard.vue'
import StatusPill from '../components/ui/StatusPill.vue'
import { getIssues, raiseIssue } from '../api/issues'
import { getMyClubs } from '../api/clubs'
import { cachedFetch, invalidateCache } from '../utils/apiCache'
import { useFormValidation } from '../composables/useFormValidation'
import { toast } from '../composables/useToast'

const { allFieldsFilled } = useFormValidation()

const issues = ref([])
const clubOptions = ref([])
const isSubmitting = ref(false)

const issueTitle = ref('')
const issueCategory = ref('')
const issueClub = ref('')
const issueDesc = ref('')

const categoryOptions = [
  { value: 'event', label: 'Event' },
  { value: 'club', label: 'Club' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'technical', label: 'Technical' },
  { value: 'general', label: 'General' }
]

const openCount = computed(function countOpenIssues() {
  return issues.value.filter((issue) => issue.status !== 'resolved').length
})

function clearForm() {
  issueTitle.value = ''
  issueCategory.value = ''
  issueClub.value = ''
  issueDesc.value = ''
}

async function submitIssue() {
  if (isSubmitting.value) {
    return
  }

  const fields = {
    title: issueTitle.value,
    category: issueCategory.value,
    club: issueClub.value,
    desc: issueDesc.value
  }

  if (!allFieldsFilled(fields)) {
    toast.error('Please fill in all fields before submitting.')
    return
  }

  // The API validates these lengths too, but catching them here gives a
  // readable message instead of a raw 422.
  if (issueTitle.value.trim().length < 3) {
    toast.error('Please give your issue a slightly longer title.')
    return
  }

  if (issueDesc.value.trim().length < 10) {
    toast.error('Please describe the issue in a little more detail.')
    return
  }

  isSubmitting.value = true

  try {
    await raiseIssue({
      club_id: Number(issueClub.value),
      category: issueCategory.value,
      title: issueTitle.value.trim(),
      description: issueDesc.value.trim()
    })

    toast.success('Issue submitted. The club leader has been notified.')
    clearForm()
    invalidateCache('my-issues')
    await loadIssues()
  } catch (error) {
    toast.error(error?.message || 'Could not submit your issue. Please try again.')
  } finally {
    isSubmitting.value = false
  }
}

async function loadIssues() {
  try {
    issues.value = await cachedFetch('my-issues', getIssues)
  } catch (error) {
    toast.error(error?.message || 'Could not load your issues.')
  }
}

// An issue is always raised against a club, so the picker offers the clubs
// this student actually belongs to rather than every club on campus.
//
// getMyClubs() with no filter returns every membership row regardless of
// status - a still-PENDING join request included - so it is filtered to
// APPROVED here. Otherwise a student could raise an issue "from" a club
// before they were ever actually let in. A club the student leads is an
// APPROVED membership too (see ClubService.create), so this naturally
// includes those without a second call.
async function loadMyClubs() {
  try {
    const myClubs = await getMyClubs()

    clubOptions.value = myClubs
      .filter(function isApprovedMember(club) {
        return club.membership_status === 'APPROVED'
      })
      .map(function toOption(club) {
        return { value: String(club.id), label: club.name }
      })
  } catch (error) {
    clubOptions.value = []
  }
}

onMounted(async function loadPage() {
  await Promise.all([loadIssues(), loadMyClubs()])
})
</script>

<template>
  <StudentSidebar />

  <div class="main-content">

    <Topbar title="Issues" sub="Raise a concern or track your open issues" :show-bell="false" />

    <main class="content-body custom-scrollbar">

      <div class="issues-layout">

        <div class="issue-form-card">
          <p class="issue-form-title">
            <MessageSquareWarning />
            Raise a New Issue
          </p>

          <div class="issue-form-fields">
            <div class="form-group form-group-wide">
              <label for="issue-title">Issue Title</label>
              <input type="text" id="issue-title" v-model="issueTitle" class="input-field" placeholder="Short summary of the problem">
            </div>

            <div class="form-group">
              <label for="issue-category">Category</label>
              <CustomSelect v-model="issueCategory" :options="categoryOptions" placeholder="Select category" />
            </div>

            <div class="form-group">
              <label for="issue-club">Related Club</label>
              <CustomSelect v-model="issueClub" :options="clubOptions" placeholder="Select club" />
              <p v-if="clubOptions.length === 0" class="text-note">
                You can raise an issue once you have joined a club.
              </p>
            </div>

            <div class="form-group form-group-wide">
              <label for="issue-desc">Description</label>
              <textarea id="issue-desc" v-model="issueDesc" class="textarea-field" rows="4" placeholder="Describe the issue in detail so the club leader can help you."></textarea>
            </div>
          </div>

          <button
            class="btn-primary"
            :disabled="isSubmitting || clubOptions.length === 0"
            @click="submitIssue"
          >
            <span v-if="isSubmitting" class="btn-spinner"></span>
            <template v-else><Send /> Submit Issue</template>
          </button>

          <p class="text-note">Issues are sent directly to the club leader. Most are resolved within 48 hours.</p>
        </div>

        <div class="issue-feed-section">
          <div class="issue-feed-header">
            <h2 class="clubs-section-title">Your Issues</h2>
            <StatusPill status="open" :label="openCount + ' open'" />
          </div>

          <div v-if="issues.length === 0" class="empty-state empty-state-wide">
            <Inbox />
            <p>You haven't raised any issues yet. Use the form above if something needs a club leader's attention.</p>
          </div>

          <div v-else class="issue-feed">
            <IssueCard
              v-for="issue in issues"
              :key="issue.id"
              :issue="issue"
            />
          </div>
        </div>

      </div>

    </main>

  </div>
</template>
