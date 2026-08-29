<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import SelectField from '../components/ui/SelectField.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { useAuthStore } from '../stores/auth'
import { toast } from '../composables/useToast'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const auth = useAuthStore()

const channel = ref('app')
const channelOptions = [
  { value: 'app', label: 'App' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' }
]

function save() {
  toast.success('Profile saved. UI stub until the member write path lands.')
}
</script>

<template>
  <TenantShell title="Profile" :subtitle="tenant.name">
    <div class="row r-32">
      <div class="card">
        <div class="chead"><div><h3>{{ auth.user.name || 'You' }}</h3><div class="sub">{{ auth.user.email || 'no email on file' }}</div></div></div>
        <div class="form">
          <div class="field">
            <label for="name">Display name</label>
            <input id="name" :value="auth.user.name" type="text" />
          </div>
          <div class="field">
            <label for="channel">Preferred channel</label>
            <SelectField id="channel" v-model="channel" :options="channelOptions" />
          </div>
          <button class="btn btn-primary" style="align-self:flex-start" @click="save"><span>Save</span></button>
        </div>
      </div>

      <div class="card">
        <div class="chead"><div><h3>Membership</h3></div></div>
        <div class="meta">
          <span><b>tenant</b> {{ tenant.name }}</span>
          <span><b>role</b> {{ auth.role }}</span>
          <span><b>vertical</b> {{ tenant.vertical }}</span>
        </div>
      </div>
    </div>
  </TenantShell>
</template>
