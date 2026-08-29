<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { toast } from '../composables/useToast'

// Adds the explicit tenant_slug field per CONTEXT.md's decision log: a
// housing society has no email domain to join by, so a member names the
// tenant it wants to join, same as the URL does.

const router = useRouter()
const { isValidEmail, isStrongEnough, allFieldsFilled } = useFormValidation()

const fullName = ref('')
const email = ref('')
const password = ref('')
const tenantSlug = ref('')
const submitting = ref(false)
const errorMessage = ref('')

function submit() {
  if (!allFieldsFilled({ fullName: fullName.value, email: email.value, password: password.value, tenantSlug: tenantSlug.value })) {
    errorMessage.value = 'Fill in every field, including the tenant slug.'
    return
  }
  if (!isValidEmail(email.value)) {
    errorMessage.value = 'Enter a valid email address.'
    return
  }
  if (!isStrongEnough(password.value)) {
    errorMessage.value = 'Password needs at least 8 characters.'
    return
  }
  errorMessage.value = ''
  submitting.value = true

  window.setTimeout(() => {
    submitting.value = false
    toast.success('Account created. Awaiting tenant admin approval.')
    router.push('/login')
  }, 300)
}
</script>

<template>
  <AuthShell title="Create an account" subtitle="Requests, ledger and votes for the community you name below.">
    <form class="form" @submit.prevent="submit">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>

      <div class="field">
        <label for="name">Full name</label>
        <input id="name" v-model="fullName" type="text" autocomplete="name" />
      </div>

      <div class="field">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" autocomplete="email" />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input id="password" v-model="password" type="password" autocomplete="new-password" />
        <span class="hint">At least 8 characters.</span>
      </div>

      <div class="field">
        <label for="tenant-slug">Tenant slug</label>
        <input id="tenant-slug" v-model="tenantSlug" type="text" placeholder="vaikunth-heights" />
        <span class="hint">The community you are joining. Do not know it? <router-link to="/onboard">Look it up here</router-link>.</span>
      </div>

      <button type="submit" class="btn btn-primary" :disabled="submitting" style="width:100%">
        <span>{{ submitting ? 'Creating…' : 'Create account' }}</span>
      </button>
    </form>

    <p class="auth-foot">Already have an account? <router-link to="/login">Sign in</router-link></p>
  </AuthShell>
</template>
