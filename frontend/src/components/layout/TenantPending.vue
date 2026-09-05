<script setup>
// The state shown at a tenant-scoped route (`/t/:slug/...`) before
// GET /api/t/{slug}/tenant has resolved, or when it never will. Deliberately
// has no sidebar/topbar chrome of its own - TenantShell cannot render
// either (its nav depends on the tenant object too), so every gated view
// falls back to this bare, centered state instead of TenantShell's
// undefined-property crash this component exists to replace.
//
// Two real states, not one generic spinner: still loading (calm, expected,
// especially on a slow connection) versus a fetch that failed outright
// (wrong slug, 404, network down) - the message has to say which.

const props = defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})
</script>

<template>
  <div class="wrap tenant-pending">
    <div class="card tenant-pending-card">
      <template v-if="props.error">
        <h3>Could not load this tenant</h3>
        <p class="sub">{{ props.error }}</p>
        <p class="sub">Check the link, or <router-link to="/login">sign in again</router-link>.</p>
      </template>
      <template v-else>
        <div class="route-buffer-spinner" aria-hidden="true"></div>
        <h3>Loading tenant…</h3>
        <p class="sub">Fetching this workspace's details.</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tenant-pending{
  min-height:60vh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding-block:var(--sp8);
}
.tenant-pending-card{
  align-items:center;
  text-align:center;
  max-width:44ch;
}
.tenant-pending-card h3{
  color:var(--ink);
  font-size:1.05rem;
}
</style>
