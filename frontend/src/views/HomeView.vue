<script setup>
import { ref } from 'vue'
import { useRevealOnMount } from '../composables/useRevealOnMount'
import { useOverlayScrollbar } from '../composables/useOverlayScrollbar'
import LandingNav from '../components/landing/LandingNav.vue'
import LandingHero from '../components/landing/LandingHero.vue'
import LandingSpine from '../components/landing/LandingSpine.vue'
import LandingUncertainty from '../components/landing/LandingUncertainty.vue'
import LandingPacks from '../components/landing/LandingPacks.vue'
import LandingHow from '../components/landing/LandingHow.vue'
import LandingMetrics from '../components/landing/LandingMetrics.vue'
import LandingCta from '../components/landing/LandingCta.vue'
import LandingFooter from '../components/landing/LandingFooter.vue'

// Faithful port of design/samples/quorum/landing.html, split into
// per-section components rather than one inline template (see
// components/landing/*). useRevealOnMount replays the sample's staggered
// .rv reveal across the whole page in one observer; useOverlayScrollbar
// ports its short-thumb document scrollbar.

const root = ref(null)
useRevealOnMount(root)
useOverlayScrollbar()
</script>

<template>
  <div ref="root">
    <LandingNav />
    <LandingHero />
    <LandingSpine />
    <LandingUncertainty />
    <LandingPacks />
    <LandingHow />
    <LandingMetrics />
    <LandingCta />
    <LandingFooter />
  </div>
</template>
