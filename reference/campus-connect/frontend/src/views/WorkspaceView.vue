<script setup>
import { useRouter } from 'vue-router'
import { GraduationCap, Compass, Briefcase, ArrowRight } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const firstName = auth.user && auth.user.name ? auth.user.name.split(' ')[0] : 'there'

function enter(path) {
  router.push(path)
}
</script>

<template>
  <div class="workspace-choose">

    <div class="workspace-head">
      <div class="workspace-logo">
        <div class="logo-mark">
          <GraduationCap />
        </div>
        <span class="brand">Campus Connect</span>
      </div>
      <h1 class="workspace-title">Welcome back, {{ firstName }}</h1>
      <p class="workspace-sub">Choose how you would like to continue.</p>
    </div>

    <div class="workspace-cards">
      <button class="workspace-card member-choice" @click="enter('/clubs')">
        <div class="workspace-card-icon">
          <Compass />
        </div>
        <p class="workspace-card-title">Continue as Member</p>
        <p class="workspace-card-desc">
          Discover clubs, register for events, and track your results and certificates.
        </p>
        <span class="workspace-card-go">Enter member area <ArrowRight /></span>
      </button>

      <button
        v-if="auth.canManageClubs"
        class="workspace-card leader-choice"
        @click="enter('/leader/club')"
      >
        <div class="workspace-card-icon">
          <Briefcase />
        </div>
        <p class="workspace-card-title">Manage your Clubs</p>
        <p class="workspace-card-desc">
          Create events, manage members, mark attendance, and issue certificates.
        </p>
        <span class="workspace-card-go">Enter leader tools <ArrowRight /></span>
      </button>
    </div>

  </div>
</template>
