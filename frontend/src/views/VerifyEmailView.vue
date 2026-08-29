<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'

const route = useRoute()
const state = ref('checking')

onMounted(() => {
  window.setTimeout(() => {
    state.value = route.query.token ? 'verified' : 'pending'
  }, 500)
})
</script>

<template>
  <AuthShell title="Verify your email" subtitle="">
    <div v-if="state === 'checking'" class="stat-tile-empty">
      <div class="wait-bar"><i style="width:60%"></i></div>
      <p style="margin-top:var(--sp3)">Checking your verification link…</p>
    </div>

    <div v-else-if="state === 'verified'" class="form-success">Email verified. You can sign in now.</div>

    <div v-else class="callout callout-info">
      A verification email was sent. Follow the link in it to activate your account, then
      <router-link to="/login">sign in</router-link>.
    </div>

    <p class="auth-foot" style="margin-top:var(--sp5)"><router-link to="/login">Back to sign in</router-link></p>
  </AuthShell>
</template>
