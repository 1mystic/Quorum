<script setup>
import { useLoadingBar } from '../../composables/useLoadingBar'

const { visible, progress } = useLoadingBar()
</script>

<template>
  <div v-show="visible" class="route-progress" aria-hidden="true">
    <div class="route-progress-bar" :style="{ width: progress + '%' }"></div>
  </div>

  <!-- Buffer shown in the content area while a route/component is loading -->
  <div v-show="visible" class="route-buffer" aria-hidden="true">
    <div class="route-buffer-spinner"></div>
  </div>
</template>
