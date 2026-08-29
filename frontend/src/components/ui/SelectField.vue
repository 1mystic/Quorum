<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

// Shared dropdown for every choice field in the app (vertical picker, tenant
// picker, request category/priority, role switcher, preferred channel). A
// native <select> cannot be restyled to match the rest of the design system,
// so this reimplements just enough of it: listbox semantics, arrow-key nav,
// enter/escape, outside-click, and the same visual language as
// `.field input` (style.css section 23).

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true }, // [{ value, label }]
  id: { type: String, default: '' },
  placeholder: { type: String, default: 'Select' },
  ariaLabel: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const activeIndex = ref(-1)
const root = ref(null)
const listRef = ref(null)

const selected = computed(() => props.options.find((o) => String(o.value) === String(props.modelValue)))
const selectedLabel = computed(() => (selected.value ? selected.value.label : props.placeholder))

function openList() {
  if (props.options.length === 0) return
  open.value = true
  const idx = props.options.findIndex((o) => String(o.value) === String(props.modelValue))
  activeIndex.value = idx >= 0 ? idx : 0
  nextTick(() => {
    const el = listRef.value && listRef.value.querySelector('[data-active="true"]')
    if (el) el.scrollIntoView({ block: 'nearest' })
  })
}

function closeList() {
  open.value = false
}

function toggle() {
  if (open.value) closeList()
  else openList()
}

function choose(option) {
  emit('update:modelValue', option.value)
  closeList()
}

function onKeydown(e) {
  if (!open.value) {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openList()
    }
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(props.options.length - 1, activeIndex.value + 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    if (props.options[activeIndex.value]) choose(props.options[activeIndex.value])
  } else if (e.key === 'Escape') {
    e.preventDefault()
    closeList()
  } else if (e.key === 'Tab') {
    closeList()
  }
}

function onClickOutside(e) {
  if (root.value && !root.value.contains(e.target)) closeList()
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onClickOutside))
</script>

<template>
  <div ref="root" class="select-field" :class="{ open }">
    <button
      :id="id"
      type="button"
      class="select-trigger"
      :aria-expanded="open"
      :aria-label="ariaLabel || undefined"
      role="combobox"
      aria-haspopup="listbox"
      @click="toggle"
      @keydown="onKeydown"
    >
      <span :class="{ placeholder: !selected }">{{ selectedLabel }}</span>
      <ChevronDown :size="16" class="select-chevron" />
    </button>
    <ul v-if="open" ref="listRef" class="select-list" role="listbox">
      <li
        v-for="(o, i) in options" :key="o.value"
        role="option"
        :aria-selected="String(o.value) === String(modelValue)"
        :data-active="i === activeIndex"
        class="select-option"
        :class="{ active: i === activeIndex, selected: String(o.value) === String(modelValue) }"
        @mouseenter="activeIndex = i"
        @click="choose(o)"
      >{{ o.label }}</li>
    </ul>
  </div>
</template>
