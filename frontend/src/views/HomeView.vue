<script setup>
import { demoTenantList } from '../fixtures/tenants'
</script>

<template>
  <div class="wrap" style="padding-block:var(--sp8);display:flex;flex-direction:column;gap:var(--sp6)">
    <h1 class="disp">Quorum</h1>
    <p style="color:var(--ink-2);max-width:56ch">The LLM narrates; statistics decide. Every figure on this platform carries its <code style="font-family:var(--font-mono)">n</code>, its interval and a link to the mathematics behind it.</p>

    <div style="display:flex;gap:var(--sp3);flex-wrap:wrap">
      <router-link class="btn btn-primary" to="/login"><span>Sign in</span></router-link>
      <router-link class="btn btn-ghost" to="/onboard">Join or create a tenant</router-link>
      <router-link class="btn btn-ghost" to="/methods">Method cards</router-link>
    </div>

    <div>
      <h3 style="margin-bottom:var(--sp3)">Demo tenants</h3>
      <div class="list">
        <router-link v-for="t in demoTenantList" :key="t.slug" class="list-row" :to="`/t/${t.slug}/dashboard`">
          <div class="lr-main">
            <div class="lr-title">{{ t.name }}</div>
            <div class="lr-sub">{{ t.tagline }} · {{ t.vertical }}</div>
          </div>
        </router-link>
      </div>
    </div>
  </div>
</template>
