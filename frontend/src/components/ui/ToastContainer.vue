<script setup>
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-vue-next'
import { useToastState } from '../../composables/useToast'

const { toasts, dismiss } = useToastState()

const iconFor = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info
}
</script>

<template>
  <div class="toast-stack">
    <TransitionGroup name="toast">
      <div
        v-for="item in toasts"
        :key="item.id"
        class="toast"
        :class="'toast-' + item.type"
        role="status"
      >
        <component :is="iconFor[item.type] || Info" class="toast-icon" />
        <p class="toast-msg">{{ item.message }}</p>
        <button class="toast-close" aria-label="Dismiss" @click="dismiss(item.id)">
          <X />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
