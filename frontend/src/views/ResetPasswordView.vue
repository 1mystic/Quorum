<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { toast } from '../composables/useToast'

const router = useRouter()
const { isStrongEnough } = useFormValidation()
const password = ref('')
const confirm = ref('')
const errorMessage = ref('')

function submit() {
  if (!isStrongEnough(password.value)) {
    errorMessage.value = 'Password needs at least 8 characters.'
    return
  }
  if (password.value !== confirm.value) {
    errorMessage.value = 'Passwords do not match.'
    return
  }
  errorMessage.value = ''
  toast.success('Password updated. Sign in with your new password.')
  router.push('/login')
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
      <button type="submit" class="btn btn-primary" style="width:100%"><span>Update password</span></button>
    </form>
  </AuthShell>
</template>
