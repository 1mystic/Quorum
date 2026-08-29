<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { Clock, CheckCircle2, XCircle } from 'lucide-vue-next'
import AdminSidebar from '../components/layout/AdminSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import StatCard from '../components/ui/StatCard.vue'
import ApprovalCard from '../components/ui/ApprovalCard.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import { getClubApprovals, approveClubRequest, rejectClubRequest } from '../api/clubs'
import { toApprovalCard } from '../utils/clubVisuals'

const approvals = ref([])
const activeFilter = ref('all')

const approvedCount = ref(0)
const rejectedCount = ref(0)

const auth = useAuthStore()


const filterChips = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'approved', label: 'Approved' },
  { id: 'rejected', label: 'Rejected' }
]

const visibleApprovals = computed(function filterApprovals() {
  return approvals.value.filter(function matchesFilter(approval) {
    if (activeFilter.value === 'all') {
      return true
    }

    return approval.status === activeFilter.value
  })
})

const collegeTitle = computed(() =>
  auth.user.collegeName || auth.user.collegeSlug
)

const pendingCount = computed(function countPending() {
  return approvals.value.filter(function isPending(approval) {
    return approval.status === 'pending'
  }).length
})

const busyIds = ref(new Set())

function isBusy(id) {
  return busyIds.value.has(id)
}

async function handleApprove(approval) {
  busyIds.value.add(approval.id)
  try {
    await approveClubRequest(approval.id)
    approvals.value = approvals.value.map((item) =>
      item.id === approval.id
        ? { ...item, status: "approved" }
        : item
    )
  } finally {
    busyIds.value.delete(approval.id)
  }
}

async function handleReject(approval) {
  const reason = window.prompt(
    "Enter a short reason for rejection (shown to the club leader):"
  )

  if (reason === null) return

  busyIds.value.add(approval.id)
  try {
    await rejectClubRequest(approval.id)
    approvals.value = approvals.value.map((item) =>
      item.id === approval.id
        ? { ...item, status: "rejected" }
        : item
    )
  } finally {
    busyIds.value.delete(approval.id)
  }
}

onMounted(async () => {
  try {
    const [pending, approved, rejected] = await Promise.all([
      getClubApprovals("PENDING"),
      getClubApprovals("ACTIVE"),
      getClubApprovals("REJECTED")

    ])

    approvals.value = [
      ...pending,
      ...approved,
      ...rejected
    ].map(toApprovalCard)

    approvedCount.value = approved.length
    rejectedCount.value = rejected.length

  } catch (error) {
    console.error(error)

    approvals.value = []
    approvedCount.value = 0
    rejectedCount.value = 0
  }
})

</script>

<template>
  <AdminSidebar />

  <div class="main-content">

    <Topbar title="Club Approvals" :sub="`${collegeTitle} · All club registration requests`" :show-bell="false"/>

    <main class="content-body custom-scrollbar">

      <div class="stats-grid">
        <StatCard :num="pendingCount" label="Pending Review" :icon="Clock" color-class="blue-stat" />
        <StatCard :num="approvedCount" label="Approved" :icon="CheckCircle2" color-class="green-stat"/>
        <StatCard :num="rejectedCount" label="Rejected" :icon="XCircle" color-class="pink-stat"/>
      </div>

      <FilterChips :chips="filterChips" v-model="activeFilter" />

      <div class="approval-list">
        <ApprovalCard
          v-for="approval in visibleApprovals"
          :key="approval.id"
          :approval="approval"
          meta-field="metaFull"
          :busy="isBusy(approval.id)"
          @approve="handleApprove(approval)"
          @reject="handleReject(approval)"
        />
      </div>

      <div v-if="visibleApprovals.length === 0" class="empty-state empty-state-wide">
        <CheckCircle2 />
        <p>No approvals match this filter.</p>
      </div>

    </main>

  </div>
</template>
