<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import SelectField from '../components/ui/SelectField.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { useAuthSession } from '../composables/useAuthSession'
import { signup as signupRequest, onboardTenant } from '../api/auth'
import { ApiError, NetworkError } from '../api/client'
import { toast } from '../composables/useToast'

// Join an existing tenant by slug, or start a new one by naming a vertical.
// "Join" has no real lookup: there is no public "does this tenant exist"
// endpoint (app/api/tenant.py's only route is onboarding, TENANT_ADMIN-only),
// so this hands off to the real SignupView with the slug prefilled and lets
// the backend be the one to say the slug does not exist.
// "Create" is real end to end: sign up as TENANT_ADMIN (no tenant yet), then
// POST /api/tenant/onboarding while authenticated with that token, per
// app/api/tenant.py's Security(scopes=["TENANT_ADMIN"]).
// The seven verticals ship in docs/VERTICALS.md; only the two demo-seedable
// ones (rwa_society, campus_club) have adapters wired to real statistics.

const router = useRouter()
const { completeSignIn } = useAuthSession()
const { isValidEmail, isStrongEnough } = useFormValidation()
const mode = ref('join')

const joinSlug = ref('')

const adminFullName = ref('')
const adminEmail = ref('')
const adminPassword = ref('')
const newName = ref('')
const newSlug = ref('')
const newDescription = ref('')
const vertical = ref('rwa_society')
const creating = ref(false)
const createError = ref('')

const verticals = [
  { id: 'rwa_society', label: 'Housing society', demo: true },
  { id: 'campus_club', label: 'Campus club', demo: true },
  { id: 'ngo_volunteer', label: 'NGO / volunteer programme', demo: false },
  { id: 'alumni_chapter', label: 'Alumni chapter', demo: false },
  { id: 'housing_coop', label: 'Housing cooperative', demo: false },
  { id: 'sports_club', label: 'Sports club', demo: false },
  { id: 'professional_guild', label: 'Professional guild', demo: false }
]

const verticalOptions = verticals.map((v) => ({ value: v.id, label: v.label + (v.demo ? '' : ' (no demo data yet)') }))

function join() {
  if (!joinSlug.value.trim()) {
    toast.error('Enter the tenant slug you want to join.')
    return
  }
  router.push({ path: '/signup', query: { tenant: joinSlug.value.trim() } })
}

async function create() {
  if (!adminFullName.value.trim() || !adminEmail.value.trim() || !adminPassword.value) {
    createError.value = 'Your name, email and password are required to become this tenant\'s admin.'
    return
  }
  if (!isValidEmail(adminEmail.value)) {
    createError.value = 'Enter a valid email address.'
    return
  }
  if (!isStrongEnough(adminPassword.value)) {
    createError.value = 'Password needs at least 8 characters.'
    return
  }
  if (!newName.value.trim() || !newSlug.value.trim() || !newDescription.value.trim()) {
    createError.value = 'Community name, slug and description are all required.'
    return
  }
  createError.value = ''
  creating.value = true

  try {
    const signupResult = await signupRequest({
      fullName: adminFullName.value,
      email: adminEmail.value,
      password: adminPassword.value,
      confirmPassword: adminPassword.value,
      role: 'TENANT_ADMIN'
    })
    // completeSignIn seeds the auth store from the token; onboardTenant is
    // then called authenticated as that TENANT_ADMIN.
    await completeSignIn(signupResult)
    await onboardTenant({
      name: newName.value.trim(),
      slug: newSlug.value.trim(),
      vertical: vertical.value,
      description: newDescription.value.trim()
    })
    toast.success(`${newName.value} created.`)
    router.push(`/t/${newSlug.value.trim()}/admin`)
  } catch (err) {
    if (err instanceof NetworkError || err instanceof ApiError) {
      createError.value = err.message
    } else {
      createError.value = 'Something went wrong creating the tenant.'
    }
  } finally {
    creating.value = false
  }
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
        <span class="hint">You'll create your account next; the backend checks the slug exists.</span>
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%"><span>Continue</span></button>
    </form>

    <form v-else class="form" @submit.prevent="create">
      <p v-if="createError" class="form-error">{{ createError }}</p>

      <div class="field">
        <label for="admin-name">Your name</label>
        <input id="admin-name" v-model="adminFullName" type="text" autocomplete="name" />
        <span class="hint">You become this tenant's admin.</span>
      </div>
      <div class="field">
        <label for="admin-email">Your email</label>
        <input id="admin-email" v-model="adminEmail" type="email" autocomplete="email" />
      </div>
      <div class="field">
        <label for="admin-password">Password</label>
        <input id="admin-password" v-model="adminPassword" type="password" autocomplete="new-password" />
        <span class="hint">At least 8 characters.</span>
      </div>
      <div class="field">
        <label for="new-name">Community name</label>
        <input id="new-name" v-model="newName" type="text" />
      </div>
      <div class="field">
        <label for="new-slug">Slug</label>
        <input id="new-slug" v-model="newSlug" type="text" placeholder="lower-case-with-dashes" />
      </div>
      <div class="field">
        <label for="new-description">Description</label>
        <textarea id="new-description" v-model="newDescription" placeholder="What is this community?"></textarea>
      </div>
      <div class="field">
        <label for="vertical">Vertical</label>
        <SelectField id="vertical" v-model="vertical" :options="verticalOptions" />
      </div>
      <button type="submit" class="btn btn-primary" :disabled="creating" style="width:100%">
        <span>{{ creating ? 'Creating…' : 'Create tenant' }}</span>
      </button>
    </form>

    <p class="auth-foot"><router-link to="/login">Back to sign in</router-link></p>
  </AuthShell>
</template>
