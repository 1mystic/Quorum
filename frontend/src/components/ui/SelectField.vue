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
//
// A single nextTick() only guarantees Vue's own virtual-DOM patch has been
// applied; it does not guarantee the browser has finished an actual
// layout/paint pass, and it does not wait on anything outside Vue's own
// render cycle, such as the webfonts this app loads with `display=swap`
// (index.html) swapping in after first paint and reflowing the trigger.
// So the popover is mounted invisible (off-screen and visibility:hidden),
// measured after nextTick() *and* two animation frames (guaranteeing at
// least one committed layout+paint), and only then revealed at its final
// position - there is never a frame where it is visible in the wrong
// place, on the first open of a session or any other.

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
const ready = ref(false) // true only once the popover has been measured post-layout and positioned; gates visibility
const activeIndex = ref(-1)
const root = ref(null)
const triggerRef = ref(null)
const listRef = ref(null)
const listStyle = ref({})

const selected = computed(() => props.options.find((o) => String(o.value) === String(props.modelValue)))
const selectedLabel = computed(() => (selected.value ? selected.value.label : props.placeholder))

const GAP = 6
const MARGIN = 8
const MIN_WIDTH = 160

// Two rAFs, not one: the first fires before the browser has necessarily
// painted the frame in which our DOM changes landed, the second is
// guaranteed to run after that paint has been committed. This is the
// standard "wait for a real layout" sequence and is what makes the
// subsequent getBoundingClientRect()/offsetWidth reads trustworthy
// regardless of session state. jsdom (the Vitest environment) has no
// requestAnimationFrame, so this falls back to a macrotask there - it
// cannot exercise real paint timing either way, only sequencing.
const raf =
  typeof requestAnimationFrame === 'function' ? requestAnimationFrame : (fn) => setTimeout(fn, 0)

function doubleRaf() {
  return new Promise((resolve) => {
    raf(() => raf(resolve))
  })
}

function placeList() {
  const trigger = triggerRef.value
  const listEl = listRef.value
  if (!trigger || !listEl) return
  const rect = trigger.getBoundingClientRect()
  // listEl.offsetWidth is read only after the double-rAF settle below, so it
  // reflects the popover's *actual* rendered width, including any CSS rule
  // that widens it past this component's own guess (e.g. the role
  // switcher's longer option labels forcing `.role-switcher .select-list`'s
  // min-width in style.css section 42) rather than an assumed constant.
  const listWidth = Math.max(rect.width, listEl.offsetWidth || rect.width, MIN_WIDTH)

  let left = props.align === 'center' ? rect.left + rect.width / 2 - listWidth / 2 : rect.left
  left = Math.min(left, window.innerWidth - listWidth - MARGIN)
  left = Math.max(MARGIN, left)

  const spaceBelow = window.innerHeight - rect.bottom
  const openUpward = spaceBelow < 180 && rect.top > spaceBelow

  listStyle.value = {
    position: 'fixed',
    left: left + 'px',
    width: listWidth + 'px',
    ...(openUpward
      ? { bottom: window.innerHeight - rect.top + GAP + 'px' }
      : { top: rect.bottom + GAP + 'px' })
  }
}

function onReposition() {
  if (open.value && ready.value) placeList()
}

async function revealList() {
  // Parked off-screen and hidden (see the template's :class="{ ready }")
  // until we have measured against a settled layout, so a stale or
  // pre-font-swap rect never gets a visible frame, on the first open of a
  // session or any other.
  await nextTick()
  await doubleRaf()
  if (!open.value) return // closed again before we finished measuring
  placeList()
  ready.value = true
  const el = listRef.value && listRef.value.querySelector('[data-active="true"]')
  // jsdom (Vitest) has no scrollIntoView implementation at all, unlike
  // getBoundingClientRect which it stubs to zeros; guard rather than throw.
  if (el && typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'nearest' })
}

function openList() {
  if (props.options.length === 0) return
  open.value = true
  ready.value = false
  listStyle.value = { position: 'fixed', left: '-9999px', top: '-9999px' }
  const idx = props.options.findIndex((o) => String(o.value) === String(props.modelValue))
  activeIndex.value = idx >= 0 ? idx : 0
  revealList()
  // Defensive third pass: if a webfont is still loading when the two rAFs
  // above run, the trigger/list boxes it measured can still resize once the
  // real font swaps in. document.fonts is undefined in some test/SSR
  // environments, so this stays a no-op there rather than throwing.
  if (typeof document !== 'undefined' && document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      if (open.value) placeList()
    })
  }
}

function closeList() {
  open.value = false
  ready.value = false
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
      <slot name="icon" />
      <span :class="{ placeholder: !selected }">{{ selectedLabel }}</span>
      <ChevronDown :size="16" class="select-chevron" />
    </button>
    <Teleport to="body">
      <ul
        v-if="open" ref="listRef" class="select-list" :class="{ ready }"
        role="listbox" :style="listStyle"
      >
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
