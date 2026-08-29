<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { GraduationCap, Mail, Shield, Lock, Send, MailCheck, ArrowRight } from 'lucide-vue-next'
import { sendResetLink } from '../api/auth'
import { useFormValidation } from '../composables/useFormValidation'
import { toast } from '../composables/useToast'

const router = useRouter()
const { isValidEmail } = useFormValidation()

function goToHome() {
  router.push('/')
}

const resetEmail = ref('')
const sentEmail = ref('')
const linkSent = ref(false)
const isSending = ref(false)

async function handleSendResetLink() {
  if (!isValidEmail(resetEmail.value)) {
    toast.error('Please enter a valid email address.')
    return
  }

  if (isSending.value) return
  isSending.value = true

  try {
    await sendResetLink(resetEmail.value.trim())
    sentEmail.value = resetEmail.value.trim()
    linkSent.value = true
} catch (error) {
    toast.error(error?.message || 'Unable to send reset link.')
} finally {
    isSending.value = false
}
}

function tryAgain() {
  linkSent.value = false
  resetEmail.value = ''
}
</script>

<template>
  <div class="auth-frame">

    <div class="auth-sidebar orange-auth">
      <div class="auth-sidebar-circle-1"></div>
      <div>
        <div class="logo-row">
          <div class="logo-mark"><GraduationCap /></div>
          <span class="brand">Campus Connect</span>
        </div>
        <p class="auth-sidebar-title">Forgot your password?</p>
        <p class="auth-sidebar-desc">No worries. Enter your registered email and we will send you a secure reset link within a few minutes.</p>
      </div>
      <div class="auth-sidebar-list">
        <div class="auth-sidebar-list-item">
          <Mail /> Reset link sent to your email
        </div>
        <div class="auth-sidebar-list-item">
          <Shield /> Link expires in 15 minutes
        </div>
        <div class="auth-sidebar-list-item">
          <Lock /> Choose a new strong password
        </div>
      </div>
    </div>

    <div class="auth-form-panel">

      <div v-if="!linkSent">

        <div class="auth-form-logo logo-row" @click="goToHome">
          <div class="logo-mark"><GraduationCap /></div>
          <span class="brand">Campus Connect</span>
        </div>

        <h2 class="auth-form-title">Reset your password</h2>
        <p class="auth-form-sub">Enter the email address linked to your account.</p>

        <div class="form-group">
          <label for="reset-email">Registered Email</label>
          <input
            type="email"
            id="reset-email"
            v-model="resetEmail"
            class="input-field"
            placeholder="you@knit.ac.in"
            autocomplete="email"
            @keyup.enter="handleSendResetLink"
          >
        </div>

        <button class="btn-auth-submit" :disabled="isSending" @click="handleSendResetLink">
          <span v-if="isSending" class="btn-spinner"></span>
          <template v-else><Send /> Send Reset Link</template>
        </button>

        <p class="auth-switch-text">
          Remembered it?
          <router-link :to="`/login`" class="auth-switch-link">Back to sign in</router-link>
        </p>

      </div>

      <div v-else>

        <div class="auth-form-logo logo-row" @click="goToHome">
          <div class="logo-mark"><GraduationCap /></div>
          <span class="brand">Campus Connect</span>
        </div>

        <div class="auth-success-block">
          <div class="auth-hero-icon">
            <MailCheck />
          </div>

          <h2 class="auth-form-title">Check your inbox</h2>
          <p class="auth-form-sub">We sent a password reset link to <strong>{{ sentEmail }}</strong>. Open the email and click the link to choose a new password.</p>

          <p class="auth-form-sub">The link expires in 15 minutes. If you do not see it, check your spam folder.</p>

          <router-link to="/login" custom v-slot="{ navigate }">
            <button class="btn-auth-submit" @click="navigate">
              <ArrowRight /> Back to Sign In
            </button>
          </router-link>

          <p class="auth-switch-text">
            Wrong email?
            <span class="auth-switch-link" @click="tryAgain">Try again</span>
          </p>
        </div>

      </div>

    </div>

  </div>
</template>
