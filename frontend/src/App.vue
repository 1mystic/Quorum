<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import LoadingBar from './components/ui/LoadingBar.vue'
import ToastContainer from './components/ui/ToastContainer.vue'

const route = useRoute()

const shellClass = computed(function pickShellClass() {
  return route.meta.bodyClass || 'portal-body'
})
</script>

<template>
  <LoadingBar />
  <ToastContainer />
  <div :class="shellClass">
    <router-view />
  </div>
</template>
