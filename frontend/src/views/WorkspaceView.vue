<script setup>
import { useRouter } from 'vue-router'
import AuthShell from '../components/layout/AuthShell.vue'
import { demoTenantList } from '../fixtures/tenants'
import { useAuthStore } from '../stores/auth'

// Shown when a member belongs to more than one tenant. Both demo tenants are
// listed unconditionally here since there is no backend membership lookup
// yet; the real version filters to the caller's actual memberships.

const router = useRouter()
const auth = useAuthStore()

function enter(tenant) {
  auth.setUser({ ...auth.user, tenantSlug: tenant.slug, tenantName: tenant.name })
  router.push(`/t/${tenant.slug}/dashboard`)
}
</script>

<template>
  <AuthShell title="Choose a workspace" subtitle="You belong to more than one tenant.">
    <div class="list">
      <button
        v-for="t in demoTenantList" :key="t.slug"
        class="list-row" style="width:100%;background:none;border:0;cursor:pointer;text-align:left"
        @click="enter(t)"
      >
        <span class="tn" style="pointer-events:none">
          <span class="dot" :style="{ background: t.dotColor }">{{ t.dot }}</span>
          <span><span class="nm">{{ t.name }}</span><br /><span class="sub">{{ t.tagline }}</span></span>
        </span>
      </button>
    </div>

    <p class="auth-foot"><router-link to="/onboard">Join another tenant</router-link></p>
  </AuthShell>
</template>
