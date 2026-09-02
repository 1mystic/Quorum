<script setup>
import { computed } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import { useAuthStore } from '../../stores/auth'
import ThemeToggle from '../ui/ThemeToggle.vue'

// The minimal header for every page outside TenantShell/AuthShell/LandingNav
// (Method Cards today: MethodsIndexView, MethodCardView - both deliberately
// public and unauthenticated, docs/STATS_API.md §4, so they cannot assume a
// tenant shell exists). Without this, a page reached by a shared link or a
// deep search result had no logo and no way back into the app at all.
//
// "Back" resolves through the auth store's own homeRoute getter, the same
// one router.beforeEach already trusts: a real dashboard if a session and
// tenant exist, the landing page otherwise. Not a hard-coded "/" - a
// logged-in member clicking "back" from a Method Card should land on their
// own dashboard, not be bounced out to the marketing page.

const auth = useAuthStore()
const backTo = computed(() => auth.homeRoute)
const backLabel = computed(() => (auth.isLoggedIn ? 'Back to dashboard' : 'Back to Quorum'))
</script>

<template>
  <header class="static-header">
    <router-link class="brand" :to="backTo">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" stroke-width="2.4" />
        <path d="M4.6 19.6a12.5 12.5 0 0 0 22.8 0Z" fill="var(--brand)" />
        <rect x="0" y="18.3" width="32" height="2.6" rx="1.3" fill="var(--accent)" />
      </svg>
      Quorum
    </router-link>
    <router-link :to="backTo" class="topbar-back static-header-back">
      <ChevronLeft :size="14" />{{ backLabel }}
    </router-link>
    <ThemeToggle />
  </header>
</template>
