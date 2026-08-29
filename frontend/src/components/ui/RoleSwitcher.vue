<script setup>
import { computed } from 'vue'
import { UserCog } from 'lucide-vue-next'
import { useDemoRole } from '../../composables/useDemoRole'

const props = defineProps({
  tenant: { type: Object, required: true }
})

const tenantRef = computed(() => props.tenant)
const { roles, currentRoleId, selectRole } = useDemoRole(tenantRef)
</script>

<template>
  <label class="role-switcher" title="Demo role, not enforced by a real backend yet">
    <UserCog :size="14" />
    <select :value="currentRoleId" @change="selectRole($event.target.value)">
      <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.label }}</option>
    </select>
  </label>
</template>
