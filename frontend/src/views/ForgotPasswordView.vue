<script setup>
import { ref } from 'vue'
import AuthShell from '../components/layout/AuthShell.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { forgotPassword } from '../api/auth'
import { NetworkError } from '../api/client'

// Real POST /api/auth/forgot-password (app/api/auth.py). The backend always
// returns success regardless of whether the address matches an account
// (app/services/user.py), so this never has an error state to show beyond
// a real network failure.

const { isValidEmail } = useFormValidation()
const email = ref('')
const sent = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

async function submit() {
  if (!isValidEmail(email.value)) {
    errorMessage.value = 'Enter a valid email address.'
    return
  }
  errorMessage.value = ''
  submitting.value = true
  try {
    await forgotPassword(email.value)
    sent.value = true
  } catch (err) {
    errorMessage.value = err instanceof NetworkError ? err.message : 'Something went wrong. Try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell title="Reset your password" subtitle="We will send a reset link if the address matches an account.">
    <form v-if="!sent" class="form" @submit.prevent="submit">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
      <div class="field">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" autocomplete="email" />
      </div>
      <button type="submit" class="btn btn-primary" :disabled="submitting" style="width:100%">
        <span>{{ submitting ? 'Sending…' : 'Send reset link' }}</span>
      </button>
    </form>

    <p v-else class="form-success">If {{ email }} matches an account, a reset link is on its way.</p>

    <p class="auth-foot"><router-link to="/login">Back to sign in</router-link></p>
  </AuthShell>
</template>
