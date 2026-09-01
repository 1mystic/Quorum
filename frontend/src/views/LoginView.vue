<script setup>
import { ref } from 'vue'
import { useFormValidation } from '../composables/useFormValidation'
import { useAuthSession } from '../composables/useAuthSession'
import { login as loginRequest } from '../api/auth'
import { ApiError, NetworkError } from '../api/client'
import AuthShell from '../components/layout/AuthShell.vue'
import { toast } from '../composables/useToast'

// Real POST /api/auth/login (app/api/auth.py). The tenant is not chosen
// here: it rides inside the returned JWT's tenant_slug claim, decoded by
// useAuthSession.completeSignIn, so a login form has no tenant field at all.

const { completeSignIn } = useAuthSession()
const { isValidEmail, isStrongEnough, PASSWORD_MIN_LENGTH } = useFormValidation()

const email = ref('')
const password = ref('')
const passwordVisible = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

// Client-side checks catch the two shapes that used to reach the backend
// and come back as a raw 422 (a malformed email, a too-short password):
// mirrors app/schemas/user.py's LoginRequest constraints so the failure
// shows up here, immediately, instead of after a round trip.
async function submit() {
  if (!email.value.trim() || !password.value) {
    errorMessage.value = 'Enter your email and password.'
    return
  }
  if (!isValidEmail(email.value)) {
    errorMessage.value = 'Enter a valid email address.'
    return
  }
  if (!isStrongEnough(password.value)) {
    errorMessage.value = `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`
    return
  }
  errorMessage.value = ''
  submitting.value = true

  try {
    const result = await loginRequest(email.value, password.value)
    await completeSignIn(result)
    toast.success('Signed in.')
  } catch (err) {
    if (err instanceof NetworkError) {
      errorMessage.value = err.message
    } else if (err instanceof ApiError) {
      errorMessage.value = err.status === 404 || err.status === 401
        ? 'No account matches that email and password.'
        : err.message
    } else {
      errorMessage.value = 'Something went wrong signing in.'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell title="Sign in" subtitle="Pick up where you left off.">
    <form class="form" @submit.prevent="submit">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>

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
          placeholder="At least 8 characters"
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
