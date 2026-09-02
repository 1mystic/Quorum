<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { X } from 'lucide-vue-next'

// The one "why" trigger + modal implementation in the app: a small button
// that opens a real modal (backdrop, centred dialog, explicit close
// button), teleported to <body> the same way SelectField.vue teleports its
// own popover. StatTile.vue is the main caller, but any card that needs the
// same progressive-disclosure explanation (the leaderboard and isolation
// cards on the governance/comparison pages, which are not StatTiles) uses
// this directly rather than each hand-rolling its own <details>.

const props = defineProps({
  label: {
    type: String,
    default: 'Why this reading'
  }
})

const open = ref(false)
const triggerRef = ref(null)
const closeBtnRef = ref(null)

function openModal() {
  open.value = true
  nextTick(() => {
    if (closeBtnRef.value) closeBtnRef.value.focus()
  })
}

function closeModal() {
  if (!open.value) return
  open.value = false
  nextTick(() => {
    if (triggerRef.value) triggerRef.value.focus()
  })
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) closeModal()
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

defineExpose({ openModal, closeModal })
</script>

<template>
  <div class="why-row">
    <button
      ref="triggerRef" type="button" class="why-trigger"
      :aria-expanded="open"
      @click="openModal"
    >{{ label }}</button>
  </div>

  <Teleport to="body">
    <Transition name="why-modal">
      <div v-if="open" class="why-modal-backdrop" @click="closeModal">
        <div
          class="why-modal" role="dialog" aria-modal="true"
          :aria-label="label"
          @click.stop
        >
          <div class="why-modal-head">
            <h4>{{ label }}</h4>
            <button
              ref="closeBtnRef" type="button" class="why-modal-close"
              aria-label="Close" @click="closeModal"
            ><X :size="16" /></button>
          </div>
          <div class="why-modal-body">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
