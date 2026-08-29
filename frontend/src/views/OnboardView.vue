<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import SelectField from '../components/ui/SelectField.vue'
import { demoTenantList } from '../fixtures/tenants'
import { toast } from '../composables/useToast'

// Join an existing tenant by slug, or start a new one by naming a vertical.
// The seven verticals ship in docs/VERTICALS.md; only the two demo-seedable
// ones are wired to real fixture data, the rest are selectable but show the
// "packs available once you enable the stream" state everywhere.

const router = useRouter()
const mode = ref('join')

const joinSlug = ref('')
const newName = ref('')
const newSlug = ref('')
const vertical = ref('rwa_society')

const verticals = [
  { id: 'rwa_society', label: 'RWA / housing society', demo: true },
  { id: 'campus_club', label: 'Campus club', demo: true },
  { id: 'ngo_volunteer', label: 'NGO / volunteer programme', demo: false },
  { id: 'alumni_chapter', label: 'Alumni chapter', demo: false },
  { id: 'housing_coop', label: 'Housing cooperative', demo: false },
  { id: 'sports_club', label: 'Sports club', demo: false },
  { id: 'professional_guild', label: 'Professional guild', demo: false }
]

const verticalOptions = verticals.map((v) => ({ value: v.id, label: v.label + (v.demo ? '' : ' (no demo data yet)') }))

function join() {
  const tenant = demoTenantList.find((t) => t.slug === joinSlug.value.trim())
  if (!tenant) {
    toast.error('No demo tenant with that slug. Try vaikunth-heights or aavartan-robotics.')
    return
  }
  toast.info(`Join request sent to ${tenant.name}. Awaiting admin approval.`)
  router.push('/login')
}

function create() {
  if (!newName.value.trim() || !newSlug.value.trim()) {
    toast.error('Name and slug are both required.')
    return
  }
  toast.success(`${newName.value} created as ${verticals.find((v) => v.id === vertical.value).label}. This is a UI stub until app/verticals wiring lands.`)
  router.push('/login')
}
</script>

<template>
  <AuthShell title="Join or create a tenant" subtitle="A tenant is one community: a society, a club, a chapter.">
    <div class="segmented" style="align-self:flex-start">
      <button :class="{ on: mode === 'join' }" @click="mode = 'join'">Join</button>
      <button :class="{ on: mode === 'create' }" @click="mode = 'create'">Create</button>
    </div>

    <form v-if="mode === 'join'" class="form" @submit.prevent="join">
      <div class="field">
        <label for="join-slug">Tenant slug</label>
        <input id="join-slug" v-model="joinSlug" type="text" placeholder="vaikunth-heights" />
        <span class="hint">Demo tenants: vaikunth-heights, aavartan-robotics.</span>
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%"><span>Request to join</span></button>
    </form>

    <form v-else class="form" @submit.prevent="create">
      <div class="field">
        <label for="new-name">Community name</label>
        <input id="new-name" v-model="newName" type="text" />
      </div>
      <div class="field">
        <label for="new-slug">Slug</label>
        <input id="new-slug" v-model="newSlug" type="text" placeholder="lower-case-with-dashes" />
      </div>
      <div class="field">
        <label for="vertical">Vertical</label>
        <SelectField id="vertical" v-model="vertical" :options="verticalOptions" />
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%"><span>Create tenant</span></button>
    </form>

    <p class="auth-foot"><router-link to="/login">Back to sign in</router-link></p>
  </AuthShell>
</template>
