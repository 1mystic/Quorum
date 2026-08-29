<script setup>
import { useRoute } from 'vue-router'
import { LayoutDashboard, UsersRound, CalendarDays, Megaphone, TriangleAlert, PlusCircle, Briefcase } from 'lucide-vue-next'

const route = useRoute()

// The club-leader pages used to live in their own left sidebar. They now render
// here as a secondary top nav so the member's own sidebar stays in place.
const navItems = [
  { label: 'My Club', to: '/leader/club', icon: LayoutDashboard },
  { label: 'Members', to: '/leader/members', icon: UsersRound },
  { label: 'Events', to: '/leader/events', icon: CalendarDays },
  { label: 'Announcements', to: '/leader/announcements', icon: Megaphone },
  { label: 'Issues', to: '/leader/issues', icon: TriangleAlert },
  { label: 'Create Club', to: '/clubs/propose', icon: PlusCircle }
]

function isActive(itemPath) {
  return route.path === itemPath || route.path.startsWith(itemPath + '/')
}
</script>

<template>
  <div class="leader-topnav">
    <div class="leader-topnav-context">
      <div class="leader-topnav-badge">
        <Briefcase />
      </div>
      <div class="leader-topnav-context-text">
        <p class="leader-topnav-title">Club Leader Tools</p>
        <p class="leader-topnav-sub">Manage your club, events and members</p>
      </div>
    </div>

    <nav class="leader-topnav-links custom-scrollbar">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="leader-topnav-item"
        :class="{ active: isActive(item.to) }"
      >
        <component :is="item.icon" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
  </div>
</template>
