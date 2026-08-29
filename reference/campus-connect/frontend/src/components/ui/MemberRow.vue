<script setup>
defineProps({
  member: { type: Object, required: true },
  busy: { type: Boolean, default: false }
})

const emit = defineEmits(['remove'])

function removeMember() {
  emit('remove')
}
</script>

<template>
  <div class="member-row">
    <div class="member-avatar">{{ member.initials }}</div>
    <div class="member-info">
      <p class="member-name">{{ member.name }}</p>
      <p class="member-sub">{{ member.sub }}</p>
    </div>
    <span class="member-role-badge" :class="member.role">{{ member.roleLabel }}</span>
    <button
      v-if="member.role !== 'officer'"
      class="member-remove-btn"
      :disabled="busy"
      @click="removeMember"
    >
      <span v-if="busy" class="btn-spinner"></span>
      <template v-else>Remove</template>
    </button>
  </div>
</template>
