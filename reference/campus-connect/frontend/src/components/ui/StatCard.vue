<script setup>
defineProps({
  num: { type: [String, Number], required: true },
  label: { type: String, required: true },
  icon: { type: [Object, Function], default: null },
  colorClass: { type: String, default: '' }
})
</script>

<template>
  <div class="stat-card" :class="colorClass">
    <div v-if="icon" class="stat-header">
      <div class="stat-icon"><component :is="icon" /></div>
    </div>
    <p class="stat-num">{{ num }}</p>
    <p class="stat-label">{{ label }}</p>
  </div>
</template>
