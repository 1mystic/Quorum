<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import LoadingBar from './components/ui/LoadingBar.vue'
import ToastContainer from './components/ui/ToastContainer.vue'

const route = useRoute()

// style.css keys each page shell off a class that must wrap the page content.
// Leader pages additionally get theme-leader, which recolours primary actions
// and accents to green - the identity the landing page's role cards already
// promised ("Club Leaders") - so the leader dashboard reads as its own space
// rather than a copy of the member one with a different sidebar highlight.
const shellClass = computed(function pickShellClass() {
  const base = route.meta.bodyClass || 'portal-body'
  return route.meta.role === 'leader' ? [base, 'theme-leader'] : base
})
</script>

<template>
  <LoadingBar />
  <ToastContainer />
  <div :class="shellClass">
    <router-view />
  </div>
</template>
