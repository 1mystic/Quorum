<script setup>
import { ref, computed, onMounted } from 'vue'
import { Users, Clock, ShieldCheck, Check, X, Inbox } from 'lucide-vue-next'

import LeaderSidebar from '../components/layout/LeaderSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import StatCard from '../components/ui/StatCard.vue'
import StatusPill from '../components/ui/StatusPill.vue'
import MemberRow from '../components/ui/MemberRow.vue'
import LeaderClubSwitcher from '../components/ui/LeaderClubSwitcher.vue'

import {
  getClubMembers,
  getPendingRequests,
  handleMembershipRequest,
  removeMember as removeMemberRequest
} from '../api/clubs'

import { useClubsStore } from '../stores/clubs'
import { cachedFetch, invalidateCache } from '../utils/apiCache'
import { toast } from '../composables/useToast'

const clubId = ref(null)

const members = ref([])
const requests = ref([])
const clubsStore = useClubsStore()

const totalMembers = computed(() => members.value.length)

const pendingCount = computed(() =>
  requests.value.filter(request => !request.decision).length
)

const officerCount = computed(() =>
  members.value.filter(member => member.role === 'officer').length
)

// Several requests can sit on screen at once, so "in flight" is tracked per
// request id rather than one flag for the whole page.
const busyRequestIds = ref(new Set())

function isRequestBusy(requestId) {
  return busyRequestIds.value.has(requestId)
}

// Approving, rejecting, or removing moves a student between the two lists,
// so both are stale after any of them.
function invalidateMembers(id) {
  invalidateCache(`club-members:${id}`)
  invalidateCache(`club-requests:${id}`)
}

async function approveRequest(request) {
  busyRequestIds.value.add(request.id)
  try {
    await handleMembershipRequest(
      clubId.value,
      request.id,
      'APPROVED'
    )

    invalidateMembers(clubId.value)
    await loadMembers(clubsStore.selectedLeaderClub)
    toast.success('Request approved.')
  } catch (error) {
    console.error(error)
    toast.error('Failed to approve request.')
  } finally {
    busyRequestIds.value.delete(request.id)
  }
}

async function rejectRequest(request) {
  busyRequestIds.value.add(request.id)
  try {
    await handleMembershipRequest(
      clubId.value,
      request.id,
      'REJECTED'
    )

    invalidateMembers(clubId.value)
    await loadMembers(clubsStore.selectedLeaderClub)
    toast.success('Request rejected.')
  } catch (error) {
    console.error(error)
    toast.error('Failed to reject request.')
  } finally {
    busyRequestIds.value.delete(request.id)
  }
}

async function handleRemoveMember(member) {
  // The club leader's own row is never shown with a working remove action -
  // the backend also refuses it - but guard here too so the confirm dialog
  // never even offers it.
  if (member.role === 'officer') {
    toast.error('The club leader cannot be removed.')
    return
  }

  const confirmed = window.confirm(`Remove ${member.name} from this club?`)
  if (!confirmed) return

  busyMemberIds.value.add(member.id)

  try {
    await removeMemberRequest(clubId.value, member.studentId)
    toast.success(`${member.name} has been removed from the club.`)
    invalidateMembers(clubId.value)
    await loadMembers(clubsStore.selectedLeaderClub)
  } catch (error) {
    toast.error(error?.message || 'Could not remove this member.')
  } finally {
    busyMemberIds.value.delete(member.id)
  }
}

const busyMemberIds = ref(new Set())


async function loadMembers(club) {
  clubId.value = club.id

  const rawMembers = await cachedFetch(`club-members:${club.id}`, () => getClubMembers(club.id))
  const rawRequests = await cachedFetch(`club-requests:${club.id}`, () => getPendingRequests(club.id))

  members.value = rawMembers.map(item => ({
    id: item.id,
    studentId: item.student_id,
    name: item.full_name,
    initials: item.full_name
      .split(' ')
      .map(word => word[0])
      .join('')
      .slice(0, 2)
      .toUpperCase(),
    sub: `Student ID: ${item.student_id}`,
    role: item.role === 'LEADER' ? 'officer' : 'member',
    roleLabel:
      item.role.charAt(0) +
      item.role.slice(1).toLowerCase()
  }))

  requests.value = rawRequests.map(item => ({
    id: item.id,
    name: item.full_name,
    initials: item.full_name
      .split(' ')
      .map(word => word[0])
      .join('')
      .slice(0, 2)
      .toUpperCase(),
    sub: `Student ID: ${item.student_id}`,
    role: item.role,
    status: item.status,
    decision:
      item.status === 'APPROVED'
        ? 'approved'
        : item.status === 'REJECTED'
          ? 'rejected'
          : null
  }))
}

async function changeClub(clubId) {
  clubsStore.selectLeaderClub(clubId)

  if (!clubsStore.selectedLeaderClub) return
  await loadMembers(clubsStore.selectedLeaderClub)
}

onMounted(async () => {
  try {
    await clubsStore.loadLeaderClubs()

    if (!clubsStore.selectedLeaderClub) {
      toast.error('No active club selected.')
      return
    }

    await loadMembers(clubsStore.selectedLeaderClub)

  } catch (error) {
    console.error(error)
    toast.error('Failed to load members.')
  }
})

</script>

<template>
  <LeaderSidebar />

  <div class="main-content">

    <Topbar
      title="Members"
      :show-bell="false"
    >
      <template #actions>
        <LeaderClubSwitcher @change="changeClub" />
      </template>
    </Topbar>

    <main class="content-body custom-scrollbar">

      <div class="stats-grid">
        <StatCard
          :num="totalMembers"
          label="Total Members"
          :icon="Users"
          color-class="green-stat"
        />

        <StatCard
          :num="pendingCount"
          label="Pending Requests"
          :icon="Clock"
          color-class="blue-stat"
        />

        <StatCard
          :num="officerCount"
          label="Officers"
          :icon="ShieldCheck"
          color-class="pink-stat"
        />
      </div>

      <div>
        <div class="clubs-section-header">
          <h2 class="clubs-section-title">
            Pending Join Requests
          </h2>

          <StatusPill
            status="pending"
            :label="pendingCount + ' pending'"
          />
        </div>

        <div v-if="requests.length === 0" class="empty-state empty-state-wide">
          <Inbox />
          <p>No join requests yet. They'll show up here as students apply.</p>
        </div>

        <div v-else class="approval-list">

          <div
            v-for="request in requests"
            :key="request.id"
            class="member-request-card"
            :class="{
              'approved-member': request.decision === 'approved',
              'rejected-member': request.decision === 'rejected'
            }"
          >

            <div class="member-req-avatar">
              {{ request.initials }}
            </div>

            <div class="member-req-info">
              <p class="member-req-name">
                {{ request.name }}
              </p>

              <p class="member-req-sub">
                {{ request.sub }}
              </p>
            </div>

            <div class="member-req-actions">

              <template v-if="!request.decision">

                <StatusPill
                  status="pending"
                  label="Pending"
                />

                <button
                  class="btn-success"
                  :disabled="isRequestBusy(request.id)"
                  @click="approveRequest(request)"
                >
                  <span v-if="isRequestBusy(request.id)" class="btn-spinner"></span>
                  <template v-else><Check /> Approve</template>
                </button>

                <button
                  class="btn-danger"
                  :disabled="isRequestBusy(request.id)"
                  @click="rejectRequest(request)"
                >
                  <span v-if="isRequestBusy(request.id)" class="btn-spinner"></span>
                  <template v-else><X /> Reject</template>
                </button>

              </template>

              <StatusPill
                v-else-if="request.decision === 'approved'"
                status="approved"
                label="Approved"
              />

              <StatusPill
                v-else
                status="rejected"
                label="Rejected"
              />

            </div>

          </div>

        </div>
      </div>

      <div>

        <div class="clubs-section-header">

          <h2 class="clubs-section-title">
            Active Members
          </h2>

          <span class="clubs-count-text">
            Showing {{ members.length }} of {{ totalMembers }}
          </span>

        </div>

        <div v-if="members.length === 0" class="empty-state empty-state-wide">
          <Users />
          <p>No approved members yet. Approve a join request above to get started.</p>
        </div>

        <div v-else class="member-list">

          <MemberRow
            v-for="member in members"
            :key="member.id"
            :member="member"
            :busy="busyMemberIds.has(member.id)"
            @remove="handleRemoveMember(member)"
          />

        </div>

      </div>

    </main>

  </div>
</template>
