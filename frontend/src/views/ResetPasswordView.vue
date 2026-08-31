<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { resetPassword } from '../api/auth'
import { ApiError, NetworkError } from '../api/client'
import { toast } from '../composables/useToast'

// Real POST /api/auth/reset-password (app/api/auth.py), reading the reset
// token app/services/user.py's forgot_password mailed as ?token=... in the
// link (see UserService._reset_url).

const route = useRoute()
const router = useRouter()
const { isStrongEnough } = useFormValidation()
const password = ref('')
const confirm = ref('')
const submitting = ref(false)
const errorMessage = ref('')

async function submit() {
  if (!isStrongEnough(password.value)) {
    errorMessage.value = 'Password needs at least 8 characters.'
    return
  }
  if (password.value !== confirm.value) {
    errorMessage.value = 'Passwords do not match.'
    return
  }
  if (!route.query.token) {
    errorMessage.value = 'This reset link is missing its token. Request a new one.'
    return
  }
  errorMessage.value = ''
  submitting.value = true
  try {
    await resetPassword(route.query.token, password.value, confirm.value)
    toast.success('Password updated. Sign in with your new password.')
    router.push('/login')
  } catch (err) {
    errorMessage.value = (err instanceof NetworkError || err instanceof ApiError) ? err.message : 'Something went wrong.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell title="Set a new password" subtitle="Choose a password with at least 8 characters.">
    <form class="form" @submit.prevent="submit">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
      <div class="field">
        <label for="password">New password</label>
        <input id="password" v-model="password" type="password" autocomplete="new-password" />
      </div>
      <div class="field">
        <label for="confirm">Confirm password</label>
        <input id="confirm" v-model="confirm" type="password" autocomplete="new-password" />
      </div>
      <button type="submit" class="btn btn-primary" :disabled="submitting" style="width:100%">
        <span>{{ submitting ? 'Updating…' : 'Update password' }}</span>
      </button>
    </form>
  </AuthShell>
</template>
