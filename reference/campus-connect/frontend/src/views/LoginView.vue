<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { GraduationCap, Mail, Lock, Eye, EyeOff, Check, ArrowRight, Compass, ShieldCheck } from 'lucide-vue-next'
import { loginUser } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { useFormValidation } from '../composables/useFormValidation'
import { useAuthSession } from '../composables/useAuthSession'
import { useGoogleAuth } from '../composables/useGoogleAuth'
import { toast } from '../composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const route = useRoute()
const { isValidEmail } = useFormValidation()
const { completeSignIn } = useAuthSession()
const { renderButton, isConfigured: googleEnabled } = useGoogleAuth()

const email = ref('')
const password = ref('')
const googleBtn = ref(null)

onMounted(() => {
  renderButton(googleBtn.value, {
    onSuccess: completeSignIn,
    onError: (message) => toast.error(message || 'Google sign-in failed'),
    text: 'signin_with',
    intent: 'login'
  })
})
const rememberChecked = ref(true)
const passwordVisible = ref(false)
const isSigningIn = ref(false)
const errorMessage = ref('')
function toggleRemember() {
  rememberChecked.value = !rememberChecked.value
}

function togglePasswordVisibility() {
  passwordVisible.value = !passwordVisible.value
}

function validateLoginForm() {
  if (!email.value.trim() || !password.value) {
    errorMessage.value = 'Please enter your email and password.'
    return false
  }
  if (!isValidEmail(email.value)) {
    errorMessage.value = 'Please enter a valid email address.'
    return false
  }
  errorMessage.value = ''
  return true
}

async function handleLogin() {
  if (!validateLoginForm()) {
    toast.error(errorMessage.value)
    return
  }

  if (isSigningIn.value) return
  isSigningIn.value = true

  try {
    const result = await loginUser(email.value.trim(), password.value)
    // Read by the router guard: only when this is set does landing on "/"
    // while already signed in skip straight to the dashboard.
    localStorage.setItem('cc_remember', rememberChecked.value ? 'true' : 'false')
    await completeSignIn(result)
  } catch (error) {
    toast.error(error?.message || 'Unable to sign in.')
  } finally {
    isSigningIn.value = false
  }
}
</script>

<template>
  <div class="auth-frame">

    <aside class="auth-sidebar orange-auth">

      <div class="auth-sidebar-logo" @click="router.push('/')">
        <div class="auth-sidebar-logo-mark">
          <GraduationCap />
        </div>
        <span class="brand">Campus Connect</span>
      </div>

      <div>
        <h2 class="auth-sidebar-title">Welcome<br>back.</h2>
        <p class="auth-sidebar-desc">
          Pick up where you left off. Your clubs, events and certificates are all waiting.
        </p>
      </div>

      <div class="auth-sidebar-circle-1"></div>
      <div class="auth-sidebar-circle-2"></div>

      <div class="auth-sidebar-char">
        <svg class="svg-fill" viewBox="0 0 240 240">
          <rect x="6" y="6" width="228" height="228" rx="46" fill="#6E3A2E" />
          <path d="M58 234 Q58 176 120 176 Q182 176 182 234 Z" fill="#C23E3E" />
          <rect x="104" y="148" width="32" height="42" rx="14" fill="#E7B58E" />
          <ellipse cx="120" cy="110" rx="50" ry="54" fill="#E7B58E" />
          <path d="M70 110 Q68 50 120 50 Q172 50 170 110 Q150 80 120 80 Q90 80 70 110 Z" fill="#241712" />
          <path d="M64 112 Q62 44 120 44 Q178 44 176 112" fill="none" stroke="#F2802B" stroke-width="13" stroke-linecap="round" />
          <rect x="50" y="98" width="22" height="46" rx="11" fill="#F2802B" />
          <rect x="168" y="98" width="22" height="46" rx="11" fill="#F2802B" />
          <circle cx="104" cy="113" r="5" fill="#2E1D16" />
          <circle cx="136" cy="113" r="5" fill="#2E1D16" />
          <circle cx="95" cy="129" r="7" fill="#C9603A" opacity=".55" />
          <circle cx="145" cy="129" r="7" fill="#C9603A" opacity=".55" />
          <path d="M104 134 Q120 151 136 134" fill="none" stroke="#2E1D16" stroke-width="5" stroke-linecap="round" />
        </svg>
      </div>

      <div class="auth-sidebar-sticker">Your clubs await</div>

    </aside>

    <section class="auth-form-panel custom-scrollbar">

      <h2>Sign in</h2>
      <p class="auth-form-subtitle">
        New here? <span @click="router.push(`/signup`)">Create an account</span>
      </p>

      
      <div class="form-group">
        <label for="email-input">College Email Address</label>
        <div class="input-icon-wrapper">
          <Mail />
          <input type="email" id="email-input" v-model="email" placeholder="shikha@knit.ac.in">
        </div>
      </div>

      <div class="form-group">
        <label for="password-input">Password</label>
        <div class="input-icon-wrapper login-password-row">
          <div class="input-icon-left">
            <Lock />
            <input
              :type="passwordVisible ? 'text' : 'password'"
              id="password-input"
              v-model="password"
              placeholder="Enter your password"
            >
          </div>
          <component :is="passwordVisible ? EyeOff : Eye" class="icon-clickable" @click="togglePasswordVisibility" />
        </div>
      </div>

      <div class="auth-checkbox-row">
        <div class="auth-checkbox">
          <div
            class="auth-checkbox-box"
            :style="{ opacity: rememberChecked ? 1 : 0.3 }"
            @click="toggleRemember"
          >
            <Check v-show="rememberChecked" />
          </div>
          <span>Remember me</span>
        </div>
        <router-link to="/forgot-password" class="auth-forgot-link">Forgot password?</router-link>
      </div>

      <button class="btn-auth-submit" :disabled="isSigningIn" @click="handleLogin">
        <span v-if="isSigningIn" class="btn-spinner"></span>
        <template v-else><ArrowRight /> Sign in</template>
      </button>

      <div v-show="googleEnabled" class="auth-divider-row">
        <span class="auth-divider-line"></span>
        <span>or</span>
        <span class="auth-divider-line"></span>
      </div>

      <div v-show="googleEnabled" class="auth-sso-stack">
        <div ref="googleBtn" class="google-btn-slot"></div>
      </div>

    </section>

  </div>
</template>
