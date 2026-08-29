<script setup>
import { demoTenantList } from '../../fixtures/tenants'
</script>

<template>
  <footer class="landing-foot">
    <div class="wrap">
      <div class="foot">
        <div>
          <a class="brand" href="#top" style="font-size:18px">
            <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
              <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" stroke-width="2.4" />
              <path d="M4.6 19.6a12.5 12.5 0 0 0 22.8 0Z" fill="var(--brand)" />
              <rect x="0" y="18.3" width="32" height="2.6" rx="1.3" fill="var(--accent)" />
            </svg> Quorum
          </a>
          <p>Enough people to decide. Enough data to conclude.</p>
        </div>
        <div>
          <h4>Product</h4>
          <ul>
            <li><a href="#spine">The spine</a></li>
            <li><a href="#packs">Insight packs</a></li>
            <li><router-link :to="`/t/${demoTenantList[0].slug}/dashboard`">Dashboard</router-link></li>
            <li><router-link to="/methods">Method cards</router-link></li>
          </ul>
        </div>
        <div>
          <h4>Demo tenants</h4>
          <ul>
            <li v-for="t in demoTenantList" :key="t.slug">
              <router-link :to="`/t/${t.slug}/dashboard`">{{ t.name }}, {{ t.vertical.replace('_', ' ') }}</router-link>
            </li>
            <li><router-link to="/onboard">Join or create a tenant</router-link></li>
          </ul>
        </div>
        <div>
          <h4>Rigour</h4>
          <ul>
            <li><a href="#uncertainty">Censoring</a></li>
            <li><router-link to="/methods/conformal.eta_calibration">Calibration</router-link></li>
            <li><router-link to="/methods/conformal.mondrian_eta">Conformal ETA</router-link></li>
            <li><router-link to="/methods/network.isolation_report">Privacy floor</router-link></li>
          </ul>
        </div>
      </div>
      <div class="colophon">
        <span>Quorum, community operations, statistically honest</span>
        <span>bricolage grotesque, inter tight, jetbrains mono</span>
      </div>
    </div>
  </footer>
</template>
