<script setup>
import { ref, computed, onMounted } from 'vue'
import { Clock, CheckCircle2, XCircle, ClipboardCheck } from 'lucide-vue-next'
import AdminSidebar from '../components/layout/AdminSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import StatCard from '../components/ui/StatCard.vue'
import StatusPill from '../components/ui/StatusPill.vue'
import ApprovalCard from '../components/ui/ApprovalCard.vue'
import { getClubApprovals, approveClubRequest, rejectClubRequest } from '../api/clubs'
import { cachedFetch, invalidateCache } from '../utils/apiCache'
import { toApprovalCard } from '../utils/clubVisuals'
import { toast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'

const pendingList = ref([])

const approvedTotal = ref(0)
const rejectedTotal = ref(0)

// Stays false until the first load attempt has finished, so the empty-state
// message below only shows once we actually know there is nothing pending -
// not for the brief moment before the page has loaded anything at all.
const hasLoaded = ref(false)

const auth = useAuthStore()

const pendingCount = computed(() => pendingList.value.length)

// Multiple cards can sit on screen at once, so "in flight" is tracked per
// club id rather than one flag for the whole page - approving one club must
// not grey out the button on every other pending card.
const busyIds = ref(new Set())

function isBusy(id) {
  return busyIds.value.has(id)
}

// A decision moves the club from PENDING into ACTIVE or REJECTED, so every
// cached bucket is stale at once - including the ACTIVE list that
// AdminCollegesView reads under the same key.
function invalidateApprovals() {
  invalidateCache('club-approvals:PENDING')
  invalidateCache('club-approvals:ACTIVE')
  invalidateCache('club-approvals:REJECTED')
}

async function handleApprove(approval) {
  busyIds.value.add(approval.id)
  try {
    await approveClubRequest(approval.id)
    approval.status = 'approved'
    invalidateApprovals()
  } finally {
    busyIds.value.delete(approval.id)
  }
}

const collegeSubtitle = computed(() => {
  return `${auth.user.collegeName || auth.user.collegeSlug} · Campus Connect`
})

async function handleReject(approval) {
  const reason = window.prompt('Enter a short reason for rejection (shown to the club leader):')
  if (reason === null) {
    return
  }

  busyIds.value.add(approval.id)
  try {
    await rejectClubRequest(approval.id, reason)
    approval.status = 'rejected'
    invalidateApprovals()
  } finally {
    busyIds.value.delete(approval.id)
  }
}

// Each status is fetched independently, on purpose. The three calls used to
// run through a single Promise.all(), so if any one of them failed the whole
// dashboard was left showing zeroes and an empty list with no explanation -
// which is exactly what issue #46 reported as "completely empty". Loading
// them separately means one failing call only blanks its own number.
async function loadPending() {
  try {
    const rows = await cachedFetch('club-approvals:PENDING', () => getClubApprovals("PENDING"))
    pendingList.value = rows.map(toApprovalCard)
  } catch (error) {
    toast.error('Could not load pending approvals: ' + error.message)
  }
}

async function loadApprovedTotal() {
  try {
    const active = await cachedFetch('club-approvals:ACTIVE', () => getClubApprovals("ACTIVE"))
    approvedTotal.value = active.length
  } catch (error) {
    toast.error('Could not load approved clubs: ' + error.message)
  }
}

async function loadRejectedTotal() {
  try {
    const rejected = await cachedFetch('club-approvals:REJECTED', () => getClubApprovals("REJECTED"))
    rejectedTotal.value = rejected.length
  } catch (error) {
    toast.error('Could not load rejected clubs: ' + error.message)
  }
}

onMounted(async () => {
  await Promise.all([loadPending(), loadApprovedTotal(), loadRejectedTotal()])
  hasLoaded.value = true
})
</script>

<template>
  <AdminSidebar />

  <div class="main-content">

    <Topbar title="Admin Dashboard" :sub="collegeSubtitle" :show-bell="false"/>

    <main class="content-body custom-scrollbar">

      <div class="stats-grid">
        <StatCard :num="pendingCount" label="Pending Approvals" :icon="Clock" color-class="blue-stat" />
        <StatCard :num="approvedTotal" label="Clubs Approved" :icon="CheckCircle2" color-class="green-stat" />
        <StatCard :num="rejectedTotal" label="Clubs Rejected" :icon="XCircle" color-class="pink-stat" />
      </div>

      <div>
        <div class="clubs-section-header">
          <h2 class="clubs-section-title">Pending Club Approvals</h2>
          <StatusPill status="pending" :label="pendingCount + ' pending'" />
        </div>

        <div v-if="hasLoaded && pendingList.length === 0" class="empty-state empty-state-wide">
          <ClipboardCheck />
          <p>No club approvals are waiting on you right now.</p>
        </div>

        <div v-else class="approval-list">
          <ApprovalCard
            v-for="approval in pendingList"
            :key="approval.id"
            :approval="approval"
            :busy="isBusy(approval.id)"
            @approve="handleApprove(approval)"
            @reject="handleReject(approval)"
          />
        </div>
      </div>

    </main>

  </div>
</template>
