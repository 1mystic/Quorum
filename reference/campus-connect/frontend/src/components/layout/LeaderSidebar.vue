<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { GraduationCap, LayoutDashboard, UsersRound, CalendarDays, Megaphone, TriangleAlert, PlusCircle, Compass } from 'lucide-vue-next'
import MobileNav from './MobileNav.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const slug = computed(() => auth.user?.collegeSlug || '')

const menuItems = computed(() => [
  { label: 'My Club', to: `/${slug.value}/leader/club`, icon: LayoutDashboard },
  { label: 'Members', to: `/${slug.value}/leader/members`, icon: UsersRound },
  { label: 'Events', to: `/${slug.value}/leader/events`, icon: CalendarDays },
  { label: 'Announcements', to: `/${slug.value}/leader/announcements`, icon: Megaphone },
  { label: 'Issues', to: `/${slug.value}/leader/issues`, icon: TriangleAlert },
  { label: 'Create Club', to: `/${slug.value}/clubs/propose`, icon: PlusCircle },
  { label: 'Member Area', to: `/${slug.value}/clubs`, icon: Compass }
])

const mobileItems = computed(() => [
  { label: 'Club', to: `/${slug.value}/leader/club`, icon: LayoutDashboard },
  { label: 'Members', to: `/${slug.value}/leader/members`, icon: UsersRound },
  { label: 'Events', to: `/${slug.value}/leader/events`, icon: CalendarDays },
  { label: 'Posts', to: `/${slug.value}/leader/announcements`, icon: Megaphone },
  { label: 'Issues', to: `/${slug.value}/leader/issues`, icon: TriangleAlert },
  { label: 'Member', to: `/${slug.value}/clubs`, icon: Compass }
])

// Among every menu item whose path is a prefix of the current route, only
// the longest one should be treated as active. Without this, being on
// "/clubs/propose" would light up both "Member Area" and "Create Club" at
// once, since "/clubs/propose" also starts with "/clubs/".
const bestMatchPath = computed(function findBestMatch() {
  const candidatePaths = menuItems.value
    .map(function getPath(item) { return item.to })
    .filter(function matchesCurrentRoute(path) {
      return route.path === path || route.path.startsWith(path + '/')
    })

  if (candidatePaths.length === 0) {
    return null
  }

  return candidatePaths.reduce(function pickLongest(longestSoFar, path) {
    return path.length > longestSoFar.length ? path : longestSoFar
  })
})

function isActive(itemPath) {
  return itemPath === bestMatchPath.value
}

function logout() {
  const collegeSlug = auth.user.collegeSlug

  auth.logout()

  router.push(`/${collegeSlug}/login`)
}

</script>

<template>
  <aside class="sidebar">
    <div class="logo-row">
      <div class="logo-mark">
        <GraduationCap />
      </div>
      <span class="brand">Campus Connect</span>
    </div>

    <p class="nav-label">Leader</p>

    <nav class="sidebar-menu">
      <router-link
        v-for="item in menuItems"
        :key="item.to"
        :to="item.to"
        class="sidebar-item"
        :class="{ active: isActive(item.to), leader: isActive(item.to) }"
      >
        <component :is="item.icon" /> {{ item.label }}
      </router-link>
    </nav>

    <div class="sidebar-spacer"></div>

    <div>
      <router-link :to="`/${slug}/profile`" class="user-card">
        <div class="user-avatar leader-av">{{ auth.user.initials }}</div>
        <div class="user-info">
          <p class="user-name">{{ auth.user.name }}</p>
          <p class="user-sub">{{ auth.user.email }}</p>
        </div>
      </router-link>

      <button class="logout-btn" @click="logout">
        Logout
    </button>

    </div>
  </aside>

  <MobileNav :items="mobileItems" role-class="leader" />
</template>
