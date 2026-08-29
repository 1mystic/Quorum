<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ChevronDown, Check } from 'lucide-vue-next'

// Drop-in replacement for a native <select>. Accepts either an array of strings
// or an array of { value, label } objects, and works with v-model.
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Select an option' }
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const root = ref(null)

const normalized = computed(function normalize() {
  return props.options.map(function toOption(option) {
    if (option && typeof option === 'object') {
      return { value: option.value, label: option.label }
    }
    return { value: option, label: String(option) }
  })
})

const selectedLabel = computed(function findLabel() {
  const match = normalized.value.find(function byValue(option) {
    return option.value === props.modelValue
  })
  return match ? match.label : ''
})

function toggle() {
  open.value = !open.value
}

function choose(option) {
  emit('update:modelValue', option.value)
  open.value = false
}

function onDocumentClick(event) {
  if (root.value && !root.value.contains(event.target)) {
    open.value = false
  }
}

function onEscape(event) {
  if (event.key === 'Escape') {
    open.value = false
  }
}

onMounted(function attachListeners() {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onEscape)
})

onBeforeUnmount(function detachListeners() {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onEscape)
})
</script>

<template>
  <div class="cc-select" :class="{ open }" ref="root">
    <button
      type="button"
      class="cc-select-trigger"
      :class="{ 'is-placeholder': !selectedLabel }"
      @click.stop="toggle"
    >
      <span class="cc-select-value">{{ selectedLabel || placeholder }}</span>
      <ChevronDown class="cc-select-caret" />
    </button>

    <transition name="cc-select-pop">
      <div v-if="open" class="cc-select-menu custom-scrollbar">
        <button
          v-for="option in normalized"
          :key="option.value"
          type="button"
          class="cc-select-option"
          :class="{ selected: option.value === modelValue }"
          @click="choose(option)"
        >
          <span>{{ option.label }}</span>
          <Check v-if="option.value === modelValue" class="cc-select-check" />
        </button>
      </div>
    </transition>
  </div>
</template>
