<script setup>
import { ShieldAlert, X } from 'lucide-vue-next'
import { roleMismatchState, dismissRoleMismatch } from '../../composables/useRoleMismatch'
</script>

<template>
  <div v-if="roleMismatchState.visible" class="role-banner" role="status">
    <ShieldAlert :size="16" />
    <span>{{ roleMismatchState.message }} <span class="role-banner-tag">Demo RBAC, not enforced.</span></span>
    <button type="button" class="role-banner-close" aria-label="Dismiss" @click="dismissRoleMismatch">
      <X :size="14" />
    </button>
  </div>
</template>
