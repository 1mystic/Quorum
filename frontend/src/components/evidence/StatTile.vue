<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots } from 'vue'
import { X } from 'lucide-vue-next'
import EvidenceValue from './EvidenceValue.vue'
import AuditLine from './AuditLine.vue'
import { renderState, qualifyingChecks, RENDER_STATES } from '../../utils/evidence'

// The KPI card: big tabular number, meta strip, and a "Why this reading"
// trigger that opens a real modal - a backdrop, a centred dialog and an
// explicit close button, teleported to <body> the same way SelectField.vue
// teleports its popover. Matches design/samples/quorum/dashboard.html's
// content, not its <details> mechanics: review feedback was that a
// same-column overlay stranded the trigger at an arbitrary height once a
// row's siblings stretched it, and that dismiss-by-clicking-away-only was
// not an explicit enough affordance. The Evidence contract still requires
// the explanation to exist and to be closed by default.

const props = defineProps({
  evidence: {
    type: Object,
    default: null
  },
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  display: {
    type: String,
    default: 'scalar'
  },
  whySummary: {
    type: String,
    default: 'Why this reading'
  },
  muted: {
    type: Boolean,
    default: false
  }
})

const slots = useSlots()

const state = computed(() => renderState(props.evidence))

const pillLabel = {
  [RENDER_STATES.ESTIMATE]: 'Estimate',
  [RENDER_STATES.QUALIFIED]: 'Qualified',
  [RENDER_STATES.NOT_INTERPRETABLE]: 'Withheld',
  [RENDER_STATES.INSUFFICIENT_DATA]: 'Waiting'
}

const pillClass = {
  [RENDER_STATES.ESTIMATE]: 'p-est',
  [RENDER_STATES.QUALIFIED]: 'p-qual',
  [RENDER_STATES.NOT_INTERPRETABLE]: 'p-hold',
  [RENDER_STATES.INSUFFICIENT_DATA]: 'p-wait'
}

// The qualifying-check explanation that used to render inline, always-on, in
// EvidenceValue.vue: it moved here so it can live inside the modal instead,
// ahead of any custom #why slot content a page provides, rather than being
// lost. StatTile receives `evidence` directly so it computes the same
// qualifiers independently, with the same pure util.
const qualifiers = computed(() => qualifyingChecks(props.evidence))
const hasWhySlot = computed(() => Boolean(slots.why))
const showWhy = computed(() => hasWhySlot.value || qualifiers.value.length > 0)
const showFoot = computed(() => showWhy.value || Boolean(props.evidence && props.evidence.method))

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
</script>

<template>
  <div class="card" :class="{ muted: muted || state === RENDER_STATES.INSUFFICIENT_DATA }">
    <div class="chead">
      <div>
        <h3>{{ title }}</h3>
        <div v-if="subtitle" class="sub">{{ subtitle }}</div>
      </div>
      <span class="pill" :class="pillClass[state]">{{ pillLabel[state] }}</span>
    </div>

    <EvidenceValue :evidence="evidence" :display="display" />

    <div v-if="showFoot" class="tile-foot">
      <div v-if="showWhy" class="why-row">
        <button
          ref="triggerRef" type="button" class="why-trigger"
          :aria-expanded="open"
          @click="openModal"
        >{{ whySummary }}</button>
      </div>
      <AuditLine v-if="evidence && evidence.method" :evidence="evidence" />
    </div>

    <Teleport to="body">
      <Transition name="why-modal">
        <div v-if="open" class="why-modal-backdrop" @click="closeModal">
          <div
            class="why-modal" role="dialog" aria-modal="true"
            :aria-label="whySummary"
            @click.stop
          >
            <div class="why-modal-head">
              <h4>{{ whySummary }}</h4>
              <button
                ref="closeBtnRef" type="button" class="why-modal-close"
                aria-label="Close" @click="closeModal"
              ><X :size="16" /></button>
            </div>
            <div class="why-modal-body">
              <p v-for="c in qualifiers" :key="c.id || c.label" class="check-detail">
                {{ c.detail || c.label }}
              </p>
              <slot name="why" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
