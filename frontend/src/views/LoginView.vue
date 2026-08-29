<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import SelectField from '../components/ui/SelectField.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { useAuthStore } from '../stores/auth'
import { demoTenantList } from '../fixtures/tenants'
import { toast } from '../composables/useToast'

const tenantOptions = demoTenantList.map((t) => ({ value: t.slug, label: t.name }))

// No backend yet (docs/STATS_API.md is a read surface only). This signs a
// demo session into whichever fixture tenant is selected, per the OnboardView
// pattern - the form shape matches what useAuthSession expects once
// POST /api/auth/login exists.

const router = useRouter()
const auth = useAuthStore()
const { isValidEmail } = useFormValidation()

const email = ref('')
const password = ref('')
const tenantSlug = ref(demoTenantList[0].slug)
const passwordVisible = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

function submit() {
  if (!email.value.trim() || !password.value) {
    errorMessage.value = 'Enter your email and password.'
    return
  }
  if (!isValidEmail(email.value)) {
    errorMessage.value = 'Enter a valid email address.'
    return
  }
  errorMessage.value = ''
  submitting.value = true

  window.setTimeout(() => {
    const tenant = demoTenantList.find((t) => t.slug === tenantSlug.value)
    auth.setToken('demo-token')
    auth.setUser({
      name: email.value.split('@')[0],
      email: email.value,
      tenantSlug: tenant.slug,
      tenantName: tenant.name,
      initials: email.value.slice(0, 2).toUpperCase()
    })
    auth.setRole('member')
    submitting.value = false
    toast.success(`Signed in to ${tenant.name}`)
    router.push(`/t/${tenant.slug}/dashboard`)
  }, 300)
}
</script>

<template>
  <AuthShell title="Sign in" subtitle="Pick up where you left off.">
    <form class="form" @submit.prevent="submit">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>

      <div class="field">
        <label for="tenant">Tenant</label>
        <SelectField id="tenant" v-model="tenantSlug" :options="tenantOptions" />
      </div>

      <div class="field">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" placeholder="you@example.com" autocomplete="email" />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          v-model="password"
          :type="passwordVisible ? 'text' : 'password'"
          placeholder="Enter your password"
          autocomplete="current-password"
        />
        <button type="button" class="hint" style="align-self:flex-start;background:none;border:0;cursor:pointer;color:var(--brand)" @click="passwordVisible = !passwordVisible">
          {{ passwordVisible ? 'Hide password' : 'Show password' }}
        </button>
      </div>

      <div style="display:flex;justify-content:flex-end">
        <router-link to="/forgot-password" class="hint">Forgot password?</router-link>
      </div>

      <button type="submit" class="btn btn-primary" :disabled="submitting" style="width:100%">
        <span>{{ submitting ? 'Signing in…' : 'Sign in' }}</span>
      </button>

      <div class="auth-divider">or</div>

      <button type="button" class="btn-google" @click="toast.info('Google sign-in is a UI stub until app.core.auth ships OAuth.')">
        Continue with Google
      </button>
    </form>

    <p class="auth-foot">New here? <router-link to="/onboard">Join or create a tenant</router-link></p>
  </AuthShell>
</template>
