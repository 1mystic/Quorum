<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { GraduationCap, Lock, KeyRound, CheckCircle2 } from 'lucide-vue-next'
import { resetPassword } from '../api/auth'
import { usePasswordStrength } from '../composables/usePasswordStrength'
import { useFormValidation } from '../composables/useFormValidation'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const { strength, updateStrength } = usePasswordStrength()
const { isStrongEnough } = useFormValidation()

// The link from the reset email is /reset-password?token=... - no token
// means someone opened this page directly, not through a real email link.
const token = String(route.query.token || '')

const password = ref('')
const confirmPassword = ref('')
const isSubmitting = ref(false)
const done = ref(false)

function goToHome() {
  router.push('/')
}

function handlePasswordInput() {
  updateStrength(password.value)
}

async function handleReset() {
  if (!token) {
    toast.error('This reset link is invalid. Request a new one.')
    return
  }

  if (!isStrongEnough(password.value)) {
    toast.error('Password must be at least 8 characters.')
    return
  }

  if (password.value !== confirmPassword.value) {
    toast.error('Passwords do not match.')
    return
  }

  if (isSubmitting.value) return
  isSubmitting.value = true

  try {
    await resetPassword(token, password.value, confirmPassword.value)
    done.value = true
  } catch (error) {
    toast.error(error?.message || 'This reset link is invalid or has expired.')
  } finally {
    isSubmitting.value = false
  }
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
        <p class="auth-sidebar-title">Choose a new password</p>
        <p class="auth-sidebar-desc">Pick something strong you have not used before. You will need it the next time you sign in.</p>
      </div>
    </div>

    <div class="auth-form-panel">

      <div v-if="!token">
        <div class="auth-form-logo logo-row" @click="goToHome">
          <div class="logo-mark"><GraduationCap /></div>
          <span class="brand">Campus Connect</span>
        </div>

        <h2 class="auth-form-title">This link is invalid</h2>
        <p class="auth-form-sub">The reset link is missing its token. Request a new one from the sign-in page.</p>

        <router-link to="/forgot-password" custom v-slot="{ navigate }">
          <button class="btn-auth-submit" @click="navigate">Request a new link</button>
        </router-link>
      </div>

      <div v-else-if="!done">
        <div class="auth-form-logo logo-row" @click="goToHome">
          <div class="logo-mark"><GraduationCap /></div>
          <span class="brand">Campus Connect</span>
        </div>

        <h2 class="auth-form-title">Set a new password</h2>
        <p class="auth-form-sub">Enter and confirm your new password below.</p>

        <div class="form-group">
          <label for="new-password-input">New Password</label>
          <input
            type="password"
            id="new-password-input"
            v-model="password"
            placeholder="••••••••"
            class="input-field"
            @input="handlePasswordInput"
            @keyup.enter="handleReset"
          >
        </div>

        <div class="form-group">
          <label for="confirm-password-input">Confirm Password</label>
          <input
            type="password"
            id="confirm-password-input"
            v-model="confirmPassword"
            placeholder="••••••••"
            class="input-field"
            @keyup.enter="handleReset"
          >
        </div>

        <div class="password-strength-row">
          <div
            v-for="barNumber in 4"
            :key="barNumber"
            class="password-strength-bar"
            :class="{ active: barNumber <= strength }"
          ></div>
        </div>

        <button class="btn-auth-submit" :disabled="isSubmitting" @click="handleReset">
          <span v-if="isSubmitting" class="btn-spinner"></span>
          <template v-else><KeyRound /> Reset Password</template>
        </button>
      </div>

      <div v-else>
        <div class="auth-form-logo logo-row" @click="goToHome">
          <div class="logo-mark"><GraduationCap /></div>
          <span class="brand">Campus Connect</span>
        </div>

        <div class="auth-success-block">
          <div class="auth-hero-icon">
            <CheckCircle2 />
          </div>

          <h2 class="auth-form-title">Password reset</h2>
          <p class="auth-form-sub">Your password has been updated. Sign in with your new password.</p>

          <router-link to="/login" custom v-slot="{ navigate }">
            <button class="btn-auth-submit" @click="navigate">
              <Lock /> Back to Sign In
            </button>
          </router-link>
        </div>
      </div>

    </div>

  </div>
</template>
