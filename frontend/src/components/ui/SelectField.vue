<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

// Shared dropdown for every choice field in the app (vertical picker, tenant
// picker, request category/priority, role switcher, preferred channel). A
// native <select> cannot be restyled to match the rest of the design system,
// so this reimplements just enough of it: listbox semantics, arrow-key nav,
// enter/escape, outside-click, and the same visual language as
// `.field input` (style.css section 23).
//
// The popover is teleported to <body> and positioned with
// getBoundingClientRect() on the trigger, not CSS position:absolute inside
// the component's own flow: a select field nested inside flex/scroll
// ancestors (the topbar's role switcher, a scrolling sidebar) otherwise
// drifts away from its trigger. Position is recomputed on open and while
// open on resize/scroll (capture, so it also catches a scrolling ancestor).

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true }, // [{ value, label }]
  id: { type: String, default: '' },
  placeholder: { type: String, default: 'Select' },
  ariaLabel: { type: String, default: '' },
  align: { type: String, default: 'left' } // 'left' | 'center', left-aligned to the trigger by default
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const activeIndex = ref(-1)
const root = ref(null)
const triggerRef = ref(null)
const listRef = ref(null)
const listStyle = ref({})

const selected = computed(() => props.options.find((o) => String(o.value) === String(props.modelValue)))
const selectedLabel = computed(() => (selected.value ? selected.value.label : props.placeholder))

const GAP = 6
const MARGIN = 8

function placeList() {
  const trigger = triggerRef.value
  if (!trigger) return
  const rect = trigger.getBoundingClientRect()
  const listEl = listRef.value
  const listWidth = Math.max(rect.width, (listEl && listEl.offsetWidth) || rect.width)

  let left = props.align === 'center' ? rect.left + rect.width / 2 - listWidth / 2 : rect.left
  left = Math.min(left, window.innerWidth - listWidth - MARGIN)
  left = Math.max(MARGIN, left)

  const spaceBelow = window.innerHeight - rect.bottom
  const openUpward = spaceBelow < 180 && rect.top > spaceBelow

  listStyle.value = {
    position: 'fixed',
    left: left + 'px',
    width: Math.max(rect.width, 160) + 'px',
    ...(openUpward
      ? { bottom: window.innerHeight - rect.top + GAP + 'px' }
      : { top: rect.bottom + GAP + 'px' })
  }
}

function onReposition() {
  if (open.value) placeList()
}

function openList() {
  if (props.options.length === 0) return
  open.value = true
  const idx = props.options.findIndex((o) => String(o.value) === String(props.modelValue))
  activeIndex.value = idx >= 0 ? idx : 0
  nextTick(() => {
    placeList()
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
  const insideTrigger = root.value && root.value.contains(e.target)
  const insideList = listRef.value && listRef.value.contains(e.target)
  if (!insideTrigger && !insideList) closeList()
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  window.addEventListener('resize', onReposition)
  window.addEventListener('scroll', onReposition, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onClickOutside)
  window.removeEventListener('resize', onReposition)
  window.removeEventListener('scroll', onReposition, true)
})
</script>

<template>
  <div ref="root" class="select-field" :class="{ open }">
    <button
      :id="id"
      ref="triggerRef"
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
    <Teleport to="body">
      <ul v-if="open" ref="listRef" class="select-list" role="listbox" :style="listStyle">
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
    </Teleport>
  </div>
</template>
