<script setup>
import { computed } from 'vue'
import { UserCog } from 'lucide-vue-next'
import { useDemoRole } from '../../composables/useDemoRole'
import SelectField from './SelectField.vue'

const props = defineProps({
  tenant: { type: Object, required: true }
})

const tenantRef = computed(() => props.tenant)
const { roles, currentRoleId, selectRole } = useDemoRole(tenantRef)

const options = computed(() => roles.value.map((r) => ({ value: r.id, label: r.label })))
</script>

<template>
  <div class="role-switcher" title="Demo role, not enforced by a real backend yet">
    <SelectField
      :model-value="currentRoleId"
      :options="options"
      aria-label="Demo role"
      @update:model-value="selectRole"
    >
      <template #icon><UserCog :size="14" /></template>
    </SelectField>
  </div>
</template>
