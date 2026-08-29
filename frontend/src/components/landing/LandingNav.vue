<script setup>
import { ArrowRight } from 'lucide-vue-next'
import ThemeToggle from '../ui/ThemeToggle.vue'
</script>

<template>
  <nav class="landing-nav">
    <div class="wrap landing-nav-in">
      <a class="brand" href="/#top">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" stroke-width="2.4" />
          <path d="M4.6 19.6a12.5 12.5 0 0 0 22.8 0Z" fill="var(--brand)" />
          <rect x="0" y="18.3" width="32" height="2.6" rx="1.3" fill="var(--accent)" />
        </svg>
        Quorum
      </a>
      <div class="landing-navlinks">
        <a class="nl" href="/#spine">Spine</a>
        <a class="nl" href="/#uncertainty">Uncertainty</a>
        <a class="nl" href="/#packs">Packs</a>
        <router-link class="nl" to="/methods">Method cards</router-link>
        <ThemeToggle />
        <router-link class="btn btn-brand sm" to="/login">
          <span>Start</span>
          <span class="arw"><ArrowRight :size="14" /></span>
        </router-link>
      </div>
    </div>
  </nav>
</template>
