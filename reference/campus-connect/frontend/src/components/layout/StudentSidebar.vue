<script setup>
import { onMounted, computed } from 'vue'
import { useAnnouncementsStore } from '../../stores/announcements'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { GraduationCap, Compass, CalendarDays, Megaphone, Trophy, Sparkles, CircleUserRound, Briefcase, LifeBuoy } from 'lucide-vue-next'
import MobileNav from './MobileNav.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const slug = computed(() => auth.user.collegeSlug)

const announcementsStore = useAnnouncementsStore()
onMounted(() => announcementsStore.fetchUnreadCount())

// The "Manage Clubs" entry only appears for a member who also leads a club.
const manageClubsItem = computed(() => ({
  label: 'Manage Clubs',
  to: `/${slug.value}/leader/club`,
  icon: Briefcase
}))

const menuItems = computed(function buildMenu() {
  const base = [
  { label: 'Clubs', to: `/${slug.value}/clubs`, icon: Compass },
  { label: 'Propose Club', to: `/${slug.value}/clubs/propose`, icon: Briefcase },
  { label: 'Events', to: `/${slug.value}/events`, icon: CalendarDays },
  { label: 'Announcements', to: `/${slug.value}/announcements`, icon: Megaphone },
  { label: 'Leaderboard', to: `/${slug.value}/leaderboard`, icon: Trophy },
  { label: 'AI Finder', to: `/${slug.value}/find-clubs`, icon: Sparkles },
  // The issues page and its route already existed but nothing linked to it,
  // so members had no way to reach the "raise a query" form.
  { label: 'Help & Issues', to: `/${slug.value}/issues`, icon: LifeBuoy }
]
  if (auth.canManageClubs) {
    base.push(manageClubsItem.value)
  }
  return base
})

const mobileItems = computed(function buildMobileMenu() {
  const base = [
    { label: 'Clubs', to: `/${slug.value}/clubs`, icon: Compass },
    { label: 'Events', to: `/${slug.value}/events`, icon: CalendarDays },
    { label: 'News', to: `/${slug.value}/announcements`, icon: Megaphone },
    { label: 'Ranks', to: `/${slug.value}/leaderboard`, icon: Trophy },
    { label: 'Finder', to: `/${slug.value}/find-clubs`, icon: Sparkles },
    { label: 'Profile', to: `/${slug.value}/profile`, icon: CircleUserRound },
    { label: 'Propose', to: `/${slug.value}/clubs/propose`, icon: Briefcase }
  ]
  if (auth.canManageClubs) {
    base.push({ label: 'Manage', to: `/${slug.value}/leader/club`, icon: Briefcase })
  }
  return base
})

// Among every menu item whose path is a prefix of the current route, only
// the longest one should be treated as active. Without this, being on
// "/clubs/propose" would light up both "Clubs" and "Propose Club" at once,
// since "/clubs/propose" also starts with "/clubs/".
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
  // The Manage Clubs entry stays highlighted across every leader page, not
  // just its own exact route, so it needs its own rule instead of the
  // longest-match one above.
  if (itemPath.endsWith('/leader/club')) {
    return route.path.startsWith(`/${slug.value}/leader/`)
  }
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

    <p class="nav-label">Menu</p>

    <nav class="sidebar-menu">
      <router-link
        v-for="item in menuItems"
        :key="item.to"
        :to="item.to"
        class="sidebar-item"
        :class="{ active: isActive(item.to), student: isActive(item.to) }"
      >
        <component :is="item.icon" /> {{ item.label }}
        <span v-if="item.label === 'Announcements' && announcementsStore.unreadCount > 0" class="nav-badge">
          {{ announcementsStore.unreadCount > 99 ? '99+' : announcementsStore.unreadCount }}
        </span>
      </router-link>
    </nav>

    <div class="sidebar-spacer"></div>

  <div>
    <router-link v-if="slug" :to="`/${slug}/profile`" class="user-card">
      <div class="user-avatar student-av">{{ auth.user.initials }}</div>
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

  <MobileNav :items="mobileItems" role-class="student" />
</template>
