<script setup>
// Centred, sidebar-free shell for the public auth/onboarding flow. Shares
// tokens with the tenant shell but never assumes a tenant context exists.

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' }
})
</script>

<template>
  <div class="auth-shell">
    <div class="auth-card card">
      <router-link class="brand" to="/">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" stroke-width="2.4" />
          <path d="M4.6 19.6a12.5 12.5 0 0 0 22.8 0Z" fill="var(--brand)" />
          <rect x="0" y="18.3" width="32" height="2.6" rx="1.3" fill="var(--accent)" />
        </svg>
        Quorum
      </router-link>

      <div class="auth-head">
        <h1>{{ title }}</h1>
        <p v-if="subtitle" class="sub">{{ subtitle }}</p>
      </div>

      <slot />
    </div>
  </div>
</template>
