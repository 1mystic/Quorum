<script setup>
defineProps({
  status: { type: String, required: true },
  label: { type: String, required: true }
})
</script>

<template>
  <span class="status-pill" :class="status">{{ label }}</span>
</template>
