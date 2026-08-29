<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getClubApprovals } from '../api/clubs'
import { cachedFetch } from '../utils/apiCache'

import {
  School,
  Layers,
  Hash,
  CheckCircle2
} from 'lucide-vue-next'

import AdminSidebar from '../components/layout/AdminSidebar.vue'
import Topbar from '../components/layout/Topbar.vue'
import StatCard from '../components/ui/StatCard.vue'
import StatusPill from '../components/ui/StatusPill.vue'

const auth = useAuthStore()

const activeClubCount = ref(0)

const collegeTitle = computed(() =>
  auth.user.collegeName || auth.user.collegeSlug
)

onMounted(async () => {
  try {
    const clubs = await cachedFetch('club-approvals:ACTIVE', () => getClubApprovals('ACTIVE'))
    activeClubCount.value = clubs.length
  } catch {
    activeClubCount.value = 0
  }
})
</script>

<template>
  <AdminSidebar />

  <div class="main-content">

    <Topbar
      title="College"
      :sub="`${collegeTitle} · Campus Connect`"
      :show-bell="false"
    />

    <main class="content-body custom-scrollbar">

      <!-- Summary Cards -->
      <div class="stats-grid">

        <StatCard
          num="Active"
          label="College Status"
          :icon="CheckCircle2"
          color-class="green-stat"
        />

        <StatCard
          :num="auth.user.collegeSlug"
          label="College Slug"
          :icon="Hash"
          color-class="blue-stat"
        />

        <StatCard
          :num="activeClubCount"
          label="Active Clubs"
          :icon="Layers"
          color-class="pink-stat"
        />

      </div>

      <!-- College Information -->
      <section>

        <div class="clubs-section-header">
          <h2 class="clubs-section-title">
            College Information
          </h2>

          <StatusPill
            status="approved"
            label="Active"
          />
        </div>

        <div class="card">

          <div class="approval-card">

            <div class="approval-club-icon banner-blue">
              <School />
            </div>

            <div class="approval-info">

              <p class="approval-club-name">
                {{ auth.user.collegeName || auth.user.collegeSlug }}
              </p>

              <p class="approval-meta">
                <strong>College Slug:</strong>
                {{ auth.user.collegeSlug }}
              </p>

              <p class="approval-meta">
                Manage your institution and monitor club activities from the admin dashboard.
              </p>

            </div>

            <div class="approval-actions">

              <StatusPill
                status="approved"
                label="Active"
              />

            </div>

          </div>

        </div>

      </section>

    </main>

  </div>
</template>