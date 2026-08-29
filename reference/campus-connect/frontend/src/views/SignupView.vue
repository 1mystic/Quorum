<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRoute } from 'vue-router'
import { GraduationCap, Compass, ShieldCheck, Sparkles, CheckCircle2 } from 'lucide-vue-next'
import { signupUser } from '../api/auth'
import { usePasswordStrength } from '../composables/usePasswordStrength'
import { useFormValidation } from '../composables/useFormValidation'
import { useAuthSession } from '../composables/useAuthSession'
import { useGoogleAuth } from '../composables/useGoogleAuth'
import { toast } from '../composables/useToast'

const router = useRouter()
const { strength, updateStrength } = usePasswordStrength()
const { isValidEmail, allFieldsFilled, isStrongEnough } = useFormValidation()
const { completeSignIn } = useAuthSession()
const { renderButton, isConfigured: googleEnabled } = useGoogleAuth()

const googleBtn = ref(null)
const isSigningUp = ref(false)

onMounted(() => {
  renderButton(googleBtn.value, {
    onSuccess: completeSignIn,
    onError: (message) => toast.error(message || 'Google sign-in failed'),
    text: 'signup_with',
    intent: 'signup'
  })
})

const selectedRole = ref('student')
const fullName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const route = useRoute()

function selectRole(role) {
  selectedRole.value = role
}

function handlePasswordInput() {
  updateStrength(password.value)
}

function validateSignupForm() {
  const fields = { name: fullName.value, email: email.value, password: password.value, confirmPassword: confirmPassword.value }

  if (!allFieldsFilled(fields)) {
    toast.error('Please fill in all fields before continuing.')
    return false
  }
  if (!isValidEmail(email.value)) {
    toast.error('Please enter a valid college email address.')
    return false
  }
  if (fullName.value.trim().length < 5) {
    toast.error('Full name must be at least 5 characters.')
    return false
  }
  if (!isStrongEnough(password.value)) {
    toast.error('Password must be at least 8 characters.')
    return false
  }
  if (password.value !== confirmPassword.value) {
    toast.error("Passwords do not match.")
    return false
}
  return true
}

async function handleSignup() {
  if (!validateSignupForm()) return
  if (isSigningUp.value) return

  const roleMap = {
    student: "STUDENT",
    admin: "CAMPUS_ADMIN"
    }

  isSigningUp.value = true

  try {
    await signupUser({
      email: email.value.trim(),
      full_name: fullName.value.trim(),
      password: password.value,
      confirm_password: confirmPassword.value,
      role: roleMap[selectedRole.value]
    })

    sessionStorage.setItem('signupEmail', email.value.trim())
    sessionStorage.setItem('signupRole', selectedRole.value)

    // Redirect users to sign in after successful registration.
    // Email verification will be added once the backend supports it.
    router.push(`/login`)

  } catch (error) {
    toast.error(error?.message || 'Unable to create account.')
  } finally {
    isSigningUp.value = false
  }
}
</script>

<template>
  <div class="auth-frame">

    <section class="auth-form-panel custom-scrollbar">

      <div class="logo-row auth-form-logo" @click="router.push('/')">
        <div class="logo-mark logo-mark-orange">
          <GraduationCap />
        </div>
        <span class="brand">Campus Connect</span>
      </div>

      <h2>Create your account</h2>
      <p class="auth-form-subtitle">
        Already a member? <span @click="router.push(`/login`)">Sign in</span>
      </p>

      <div class="form-group">
        <label>I am registering as</label>
        <div class="register-role-grid">
          <button
            class="btn-register-role"
            :class="{ active: selectedRole === 'student' }"
            @click="selectRole('student')"
          >
            <Compass /> Member
          </button>
          <button
            class="btn-register-role"
            :class="{ active: selectedRole === 'admin' }"
            @click="selectRole('admin')"
          >
            <ShieldCheck /> Institute Admin
          </button>
        </div>
      </div>

      <div class="form-group">
        <label for="name-input">Full Name</label>
        <input type="text" id="name-input" v-model="fullName" placeholder="Shikha Singh" class="input-field">
      </div>

      <div class="form-group">
        <label for="email-input">College Email Address</label>
        <input type="email" id="email-input" v-model="email" placeholder="shikha@knit.ac.in" class="input-field">
      </div>

      <div class="form-group">
        <label for="password-input">Password</label>
        <input
          type="password"
          id="password-input"
          v-model="password"
          placeholder="••••••••"
          class="input-field"
          @input="handlePasswordInput"
        >
      </div>

      <div class="form-group">
        <label>Confirm Password</label>
        <input
          type="password"
          v-model="confirmPassword"
          placeholder="••••••••"
          class="input-field"
         />
      </div>

      <div class="password-strength-row">
        <div
          v-for="barNumber in 4"
          :key="barNumber"
          class="password-strength-bar"
          :class="{ active: barNumber <= strength }"
        ></div>
      </div>

      <button class="btn-auth-submit" :disabled="isSigningUp" @click="handleSignup">
        <span v-if="isSigningUp" class="btn-spinner"></span>
        <template v-else><Sparkles /> Create account</template>
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

    <aside class="auth-sidebar green-auth">

      <svg class="auth-sparkle" viewBox="0 0 24 24">
        <path d="M12 0 C13 7 17 11 24 12 C17 13 13 17 12 24 C11 17 7 13 0 12 C7 11 11 7 12 0Z" fill="#FBF1E3"/>
      </svg>

      <div>
        <h2 class="auth-sidebar-title">Join the<br>campus<br>community.</h2>
        <p class="auth-sidebar-desc">
          Discover clubs, attend events, earn certificates,
          and build a verifiable record of your campus life.
        </p>

        <div class="auth-sidebar-list">
          <div class="auth-sidebar-list-item">
            <CheckCircle2 />
            <span>Browse all active clubs at your college</span>
          </div>
          <div class="auth-sidebar-list-item">
            <CheckCircle2 />
            <span>Get verified participation certificates</span>
          </div>
          <div class="auth-sidebar-list-item">
            <CheckCircle2 />
            <span>Free platform, forever</span>
          </div>
        </div>
      </div>

      <div class="auth-sidebar-circle-1"></div>

      <div class="auth-sidebar-char">
        <svg class="svg-fill" viewBox="0 0 240 240">
          <rect x="6" y="6" width="228" height="228" rx="46" fill="#F5C13D" />
          <path d="M58 234 Q58 176 120 176 Q182 176 182 234 Z" fill="#EFE7DA" />
          <rect x="104" y="148" width="32" height="42" rx="14" fill="#EAC6A2" />
          <ellipse cx="120" cy="110" rx="50" ry="54" fill="#EAC6A2" />
          <path d="M70 110 Q68 50 120 50 Q172 50 170 110 Q150 80 120 80 Q90 80 70 110 Z" fill="#4A3526" />
          <path d="M64 112 Q62 44 120 44 Q178 44 176 112" fill="none" stroke="#4F9D57" stroke-width="13" stroke-linecap="round" />
          <rect x="50" y="98" width="22" height="46" rx="11" fill="#4F9D57" />
          <rect x="168" y="98" width="22" height="46" rx="11" fill="#4F9D57" />
          <circle cx="104" cy="113" r="5" fill="#2E1D16" />
          <circle cx="136" cy="113" r="5" fill="#2E1D16" />
          <circle cx="95" cy="129" r="7" fill="#D98A6A" opacity=".55" />
          <circle cx="145" cy="129" r="7" fill="#D98A6A" opacity=".55" />
          <path d="M104 134 Q120 151 136 134" fill="none" stroke="#2E1D16" stroke-width="5" stroke-linecap="round" />
        </svg>
      </div>

    </aside>

  </div>
</template>
