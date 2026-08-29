<script setup>
defineProps({
  chips: { type: Array, required: true },
  modelValue: { type: String, required: true }
})

const emit = defineEmits(['update:modelValue'])

function selectChip(chipId) {
  emit('update:modelValue', chipId)
}
</script>

<template>
  <div class="filter-chips-row">
    <button
      v-for="chip in chips"
      :key="chip.id"
      class="filter-chip"
      :class="{ active: modelValue === chip.id }"
      @click="selectChip(chip.id)"
    >
      {{ chip.label }}
    </button>
  </div>
</template>
