<script setup>
import { ArrowRight } from 'lucide-vue-next'
import { demoTenantList } from '../../fixtures/tenants'

const primaryTenant = demoTenantList[0]
</script>

<template>
  <section class="sec" style="border-top:0;padding-top:0">
    <div class="wrap">
      <div class="cta-band rv">
        <h2>Bring a quorum. We will bring the confidence intervals.</h2>
        <p>Open the sample dashboard for a real housing society in Baner, Pune, with 187 requests and every number carrying its own evidence.</p>
        <div class="btnrow">
          <router-link class="btn btn-fill" :to="`/t/${primaryTenant.slug}/dashboard`">
            <span>Open the dashboard</span>
            <span class="arw"><ArrowRight :size="16" /></span>
          </router-link>
          <a class="btn btn-line" href="/#spine">Read the spine</a>
        </div>
      </div>
    </div>
  </section>
</template>
