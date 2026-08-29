<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { tenantBySlug, demoTenantList } from '../../fixtures/tenants'
import { coreNav, insightNav, adminNav } from '../../fixtures/nav'
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
  asOf: { type: String, default: '' }
})

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))

const nav = computed(() => [
  ...coreNav(slug.value),
  ...insightNav(slug.value, tenant.value),
  ...adminNav(slug.value)
])

function isActive(item) {
  return route.path === item.to || route.path.startsWith(item.to + '/')
}

function switchTenant(nextSlug) {
  if (nextSlug === slug.value) return
  const target = route.name ? { name: route.name, params: { ...route.params, slug: nextSlug } } : `/t/${nextSlug}/dashboard`
  router.push(target).catch(() => router.push(`/t/${nextSlug}/dashboard`))
}

// design/samples/quorum/dashboard.html's overlayScroll(target) pair: one
// bound to the window, one bound to the sidebar, both drawn with the same
// short-thumb mechanism (useOverlayScrollbar).
const sideRef = ref(null)
useOverlayScrollbar()
useOverlayScrollbar(sideRef)
</script>

<template>
  <div class="app">
    <aside ref="sideRef" class="side scroll-none">
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
        <button
          v-for="t in demoTenantList" :key="t.slug"
          class="tn" :class="{ on: t.slug === slug }"
          @click="switchTenant(t.slug)"
        >
          <span class="dot" :style="{ background: t.dotColor }">{{ t.dot }}</span>
          <span><span class="nm">{{ t.name }}</span><br /><span class="sub">{{ t.tagline }}</span></span>
        </button>
      </div>

      <div class="navgrp" v-for="(group, gi) in nav" :key="gi">
        <span v-if="group.label" class="lbl">{{ group.label }}</span>
        <router-link
          v-for="item in group.items" :key="item.name"
          class="ni" :class="{ on: isActive(item) }"
          :to="item.to"
        >{{ item.label }}</router-link>
      </div>

      <div class="side-foot navgrp">
        <router-link class="ni" to="/methods">Method cards</router-link>
        <router-link class="ni" to="/workspace">Switch tenant</router-link>
        <router-link class="ni" :to="`/t/${slug}/profile`">{{ auth.user.name || 'Profile' }}</router-link>
      </div>
    </aside>

    <div class="main">
      <div class="topbar">
        <div>
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
