<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu, X, ChevronRight, ChevronLeft, LogOut } from 'lucide-vue-next'
import { tenantBySlug } from '../../fixtures/tenants'
import { assistantNav, coreNav, insightNav, adminNav } from '../../fixtures/nav'
import { useAuthStore } from '../../stores/auth'
import { useOverlayScrollbar } from '../../composables/useOverlayScrollbar'
import RoleSwitcher from '../ui/RoleSwitcher.vue'
import ThemeToggle from '../ui/ThemeToggle.vue'

// The dashboard shell every tenant-scoped page mounts inside: sidebar with
// tenant switcher and nav groups, topbar with title/subtitle slots, content
// slot. Matches design/samples/quorum/dashboard.html's .app/.side/.main.

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  asOf: { type: String, default: '' },
  // A detail page (a single request, event, decision...) passes this to get
  // a real "back to the list" link in the topbar, not just the browser's
  // own back button, which does not exist as a visible affordance and does
  // the wrong thing if the page was opened directly (a shared link, a new
  // tab) rather than navigated to from the list.
  backTo: { type: String, default: '' },
  backLabel: { type: String, default: 'Back' }
})

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))

const nav = computed(() => [
  ...assistantNav(slug.value),
  ...coreNav(slug.value),
  ...insightNav(slug.value, tenant.value),
  ...adminNav(slug.value)
])

// Sibling routes can share a path prefix (`/admin` and `/admin/approvals`
// are two distinct pages, not parent/child), so a naive per-item prefix
// match highlights both at once. Picking the single longest matching `to`
// across the whole nav resolves it to exactly one active item.
const activeTo = computed(() => {
  const candidates = nav.value
    .flatMap((group) => group.items)
    .filter((item) => route.path === item.to || route.path.startsWith(item.to + '/'))
  if (candidates.length === 0) return null
  return candidates.reduce((best, item) => (item.to.length > best.to.length ? item : best)).to
})

function isActive(item) {
  return item.to === activeTo.value
}

// Collapsible, directory-tree-style groups: each labelled section (Community,
// Insights, Admin) opens and closes independently, state keyed by label and
// kept in localStorage so a collapsed group stays collapsed across visits.
// A group containing the active route always forces itself open on load, so
// navigating here never hides the page you are actually on.
const STORAGE_KEY = 'quorum-nav-collapsed'
function loadCollapsed() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}
const collapsed = ref(loadCollapsed())

function isCollapsed(group) {
  if (!group.label) return false
  if (group.items.some(isActive)) return false
  return Boolean(collapsed.value[group.label])
}

function toggleGroup(group) {
  if (!group.label) return
  const next = { ...collapsed.value, [group.label]: !isCollapsed(group) }
  collapsed.value = next
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    // Private browsing or storage disabled: the toggle still works for this
    // session, it just does not persist. Not worth surfacing as an error.
  }
}

// A real user belongs to at most one tenant (app/models/user.py's
// User.tenant_id is a single nullable FK, not a membership table), so the
// sidebar no longer offers to switch to a different one - a click here used
// to overwrite auth.user.tenantSlug locally while the JWT in auth.token
// still carried the original tenant_slug claim, so every API call after
// "switching" sent a mismatched token and the backend correctly 403'd with
// "Tenant mismatch". The tenant panel is a static label now, sourced from
// the same slug the URL and JWT already agree on.

function logout() {
  auth.logout()
  router.push('/login')
}

// design/samples/quorum/dashboard.html's overlayScroll(target) pair: one
// bound to the window, one bound to the sidebar, both drawn with the same
// short-thumb mechanism (useOverlayScrollbar).
const sideRef = ref(null)
useOverlayScrollbar()
useOverlayScrollbar(sideRef)

// Below 1080px (style.css section 4) `.side` is an off-canvas drawer instead
// of a static column: closed by default so a mobile page load never makes
// you scroll past Community/Insights/Admin/footer before reaching content
// (the bug this replaces). Opens as an overlay, never pushes `.main` down.
const sidebarOpen = ref(false)
const navToggleRef = ref(null)

// Tracks the same 1080px cutoff as style.css section 4. Only used to decide
// whether the closed drawer should be `inert` (untabbable, hidden from
// assistive tech): on a laptop+ viewport `.side` is the normal always-open
// column and must stay reachable regardless of `sidebarOpen`'s value.
const isNarrow = ref(false)
let narrowQuery = null
function onNarrowChange(e) { isNarrow.value = e.matches }

function openSidebar() {
  sidebarOpen.value = true
  nextTick(() => {
    // Focus moves into the drawer on open, onto its own close button - the
    // first element a keyboard/screen-reader user reaches, and an obvious
    // way back out without hunting for Escape.
    const closeBtn = sideRef.value && sideRef.value.querySelector('.side-close')
    if (closeBtn) closeBtn.focus()
  })
}

function closeSidebar() {
  if (!sidebarOpen.value) return
  sidebarOpen.value = false
  // Focus returns to the trigger that opened the drawer, not left stranded
  // on a now-hidden element inside it.
  if (navToggleRef.value) navToggleRef.value.focus()
}

function toggleSidebar() {
  if (sidebarOpen.value) closeSidebar()
  else openSidebar()
}

// A tap on any nav link or the tenant switcher closes the drawer instead of
// leaving it open over the page it just navigated to. Delegated on the
// `<aside>` itself rather than wired onto every link individually.
function onAsideClick(e) {
  if (e.target.closest('a.ni, button.tn')) closeSidebar()
}

function onKeydown(e) {
  if (e.key === 'Escape' && sidebarOpen.value) closeSidebar()
}

// Route changes (including the tenant switcher's router.push, which does
// not pass through onAsideClick's button) always close the drawer, so a
// programmatic navigation can never leave it open over the new page.
watch(() => route.fullPath, () => { sidebarOpen.value = false })

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  if (typeof window !== 'undefined' && window.matchMedia) {
    narrowQuery = window.matchMedia('(max-width: 1080px)')
    isNarrow.value = narrowQuery.matches
    narrowQuery.addEventListener('change', onNarrowChange)
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  if (narrowQuery) narrowQuery.removeEventListener('change', onNarrowChange)
})
</script>

<template>
  <div class="app">
    <div
      class="side-backdrop" :class="{ open: sidebarOpen }"
      aria-hidden="true"
      @click="closeSidebar"
    />
    <aside
      ref="sideRef" class="side scroll-none" :class="{ open: sidebarOpen }"
      :inert="isNarrow && !sidebarOpen"
      @click="onAsideClick"
    >
      <button type="button" class="tgl icon-tgl side-close" aria-label="Close menu" @click="closeSidebar">
        <X :size="18" />
      </button>
      <router-link class="brand" :to="`/t/${slug}/dashboard`">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" stroke-width="2.4" />
          <path d="M4.6 19.6a12.5 12.5 0 0 0 22.8 0Z" fill="var(--brand)" />
          <rect x="0" y="18.3" width="32" height="2.6" rx="1.3" fill="var(--accent)" />
        </svg>
        Quorum
      </router-link>

      <div class="tenant">
        <span class="lbl" style="padding:0 var(--sp4) 4px">Tenant</span>
        <div class="tn on tn-static">
          <span class="dot" :style="{ background: tenant.dotColor }">{{ tenant.dot }}</span>
          <span><span class="nm">{{ tenant.name }}</span><br /><span class="sub">{{ tenant.tagline }}</span></span>
        </div>
      </div>

      <div class="navgrp" v-for="(group, gi) in nav" :key="gi" :class="{ collapsed: isCollapsed(group) }">
        <button
          v-if="group.label" type="button" class="lbl navgrp-toggle"
          :aria-expanded="!isCollapsed(group)"
          @click="toggleGroup(group)"
        >
          <ChevronRight :size="12" class="navgrp-chevron" />
          {{ group.label }}
        </button>
        <div class="navgrp-items" v-show="!isCollapsed(group)">
          <router-link
            v-for="item in group.items" :key="item.name"
            class="ni" :class="{ on: isActive(item) }"
            :to="item.to"
          >{{ item.label }}<span v-if="item.pack" class="c">{{ item.pack }}</span></router-link>
        </div>
      </div>

      <div class="side-foot navgrp">
        <router-link class="ni" to="/methods">Method cards</router-link>
        <router-link class="ni" :to="`/t/${slug}/profile`">{{ auth.user.name || 'Profile' }}</router-link>
        <button type="button" class="ni" @click="logout">
          <LogOut :size="15" />
          Sign out
        </button>
      </div>
    </aside>

    <div class="main">
      <div class="topbar">
        <button
          ref="navToggleRef" type="button" class="tgl icon-tgl nav-toggle"
          aria-label="Open menu" :aria-expanded="sidebarOpen"
          @click="openSidebar"
        >
          <Menu :size="18" />
        </button>
        <div>
          <router-link v-if="backTo" :to="backTo" class="topbar-back">
            <ChevronLeft :size="14" />{{ backLabel }}
          </router-link>
          <h1>{{ title }}</h1>
          <div v-if="subtitle" class="sub">{{ subtitle }}</div>
        </div>
        <div class="right">
          <div v-if="asOf" class="asof">{{ asOf }}</div>
          <slot name="actions" />
          <RoleSwitcher :tenant="tenant" />
          <ThemeToggle />
        </div>
      </div>

      <div class="content">
        <slot />
      </div>
    </div>
  </div>
</template>
