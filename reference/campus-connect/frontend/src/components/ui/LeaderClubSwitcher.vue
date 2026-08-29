<script setup>
import { computed } from 'vue'
import CustomSelect from './CustomSelect.vue'
import { useClubsStore } from '../../stores/clubs'

// One dropdown, reused on every leader page that shows content scoped to
// "whichever club is currently selected" (Club, Members, Announcements,
// Events). It updates the shared store directly - every page already reads
// clubsStore.selectedLeaderClub - and also emits "change" so the page hosting
// it can reload whatever it displays for the newly selected club.
// Hidden entirely for a leader with only one club: nothing to switch.
const emit = defineEmits(['change'])

const clubsStore = useClubsStore()

const selectedClubId = computed({
  get: () => clubsStore.selectedLeaderClub?.id ?? null,
  set: (clubId) => {
    clubsStore.selectLeaderClub(clubId)
    emit('change', clubId)
  }
})
</script>

<template>
  <div v-if="clubsStore.leaderClubs.length > 1" class="leader-club-switcher">
    <CustomSelect
      v-model="selectedClubId"
      :options="
        clubsStore.leaderClubs.map((c) => ({ value: c.id, label: c.name }))
      "
      placeholder="Select Club"
    />
  </div>
</template>
