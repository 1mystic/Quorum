<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { GraduationCap, LayoutDashboard, CheckCircle2, Building2, ScrollText, LogOut } from 'lucide-vue-next'
import MobileNav from './MobileNav.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const slug = computed(() => auth.user.collegeSlug)

const menuItems = computed(() => [
  { label: 'Overview', to: `/${slug.value}/admin`, icon: LayoutDashboard },
  { label: 'Approvals', to: `/${slug.value}/admin/approvals`, icon: CheckCircle2 },
  { label: 'Colleges', to: `/${slug.value}/admin/colleges`, icon: Building2 },
  { label: 'Guidelines', to: `/${slug.value}/admin/guidelines`, icon: ScrollText }
])

const mobileItems = computed(() => [
  { label: 'Overview', to: `/${slug.value}/admin`, icon: LayoutDashboard, exact: true },
  { label: 'Approvals', to: `/${slug.value}/admin/approvals`, icon: CheckCircle2 },
  { label: 'Colleges', to: `/${slug.value}/admin/colleges`, icon: Building2 },
  { label: 'Rules', to: `/${slug.value}/admin/guidelines`, icon: ScrollText }
])

function isActive(itemPath) {
  if (itemPath.endsWith('/admin')) {
    return route.path === `/${slug.value}/admin`
  }

  return route.path === itemPath || route.path.startsWith(itemPath + '/')
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

    <p class="nav-label">Admin</p>

    <nav class="sidebar-menu">
      <router-link
        v-for="item in menuItems"
        :key="item.to"
        :to="item.to"
        class="sidebar-item"
        :class="{ active: isActive(item.to), admin: isActive(item.to) }"
      >
        <component :is="item.icon" /> {{ item.label }}
      </router-link>
    </nav>

    <div class="sidebar-spacer"></div>

    <div>
      <div class="user-card">
        <div class="user-avatar admin-av">{{ auth.user.initials }}</div>
        <div class="user-info">
          <p class="user-name">{{ auth.user.name }}</p>
          <p class="user-sub">{{ auth.user.email }}</p>
        </div>
      </div>

      <button class="logout-btn" @click="logout">
        Logout
      </button>
    </div>
  </aside>

  <MobileNav :items="mobileItems" role-class="admin" />

  <!-- The sidebar (with its own logout button) is display:none below 767px and
       MobileNav has no room for a 5th icon, so admins on mobile previously had
       no way to log out at all. Lives outside <aside> on purpose - .sidebar's
       mobile media query would hide it too if it were nested inside. -->
  <button class="admin-mobile-logout" title="Logout" @click="logout">
    <LogOut />
  </button>
</template>
