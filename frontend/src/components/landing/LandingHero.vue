<script setup>
import { ArrowRight } from 'lucide-vue-next'
import { demoTenantList } from '../../fixtures/tenants'

const primaryTenant = demoTenantList[0]

// Numbers mirror the readout in dashboard.html / fixtures/evidence.js
// (medianResolution, n 187, CI 3.4-5.6) so the landing page and the demo
// dashboard never disagree about the same figure.
const rails = {
  left: [
    { h: 304, seed: 'quorum-society' },
    { h: 228, seed: 'quorum-meeting' },
    { h: 282, seed: 'quorum-festival' },
    { h: 210, seed: 'quorum-volunteers' },
    { h: 264, seed: 'quorum-courtyard' }
  ],
  right: [
    { h: 250, seed: 'quorum-club' },
    { h: 296, seed: 'quorum-workshop' },
    { h: 216, seed: 'quorum-garden' },
    { h: 272, seed: 'quorum-committee' },
    { h: 238, seed: 'quorum-terrace' }
  ]
}
</script>

<template>
  <header id="top" class="hero">
    <div class="hero-grid" aria-hidden="true" />
    <div class="rails" aria-hidden="true">
      <div class="rail l">
        <div class="track">
          <figure v-for="(f, i) in [...rails.left, ...rails.left]" :key="`l${i}`" :style="{ height: f.h + 'px' }">
            <img loading="lazy" alt="" :src="`https://picsum.photos/seed/${f.seed}/360/${f.h}`" @error="$event.target.remove()" />
          </figure>
        </div>
      </div>
      <div class="rail r">
        <div class="track">
          <figure v-for="(f, i) in [...rails.right, ...rails.right]" :key="`r${i}`" :style="{ height: f.h + 'px' }">
            <img loading="lazy" alt="" :src="`https://picsum.photos/seed/${f.seed}/360/${f.h}`" @error="$event.target.remove()" />
          </figure>
        </div>
      </div>
    </div>

    <div class="wrap hero-in">
      <span class="eyebrow rv"><i /> Community operations, statistically honest</span>
      <h1 class="rv">Numbers your community can <em>actually act on.</em></h1>
      <p class="lead rv">Quorum runs a housing society, a campus club or an NGO. Unlike every other tool in the category, it tells you how much to trust each number it shows you.</p>
      <div class="btnrow rv">
        <router-link class="btn btn-fill" :to="`/t/${primaryTenant.slug}/dashboard`">
          <span>See the dashboard</span>
          <span class="arw"><ArrowRight :size="16" /></span>
        </router-link>
        <a class="btn btn-line" href="/#uncertainty">Why intervals</a>
      </div>

      <div class="readout rv">
        <div><span class="lbl">Median resolution</span><div class="v">4.3<span style="font-size:.5em;color:var(--ink-3)">d</span></div><div class="n">n 187, CI 3.4-5.6, 44 censored</div></div>
        <div><span class="lbl">ETA coverage</span><div class="v">91.4<span style="font-size:.5em;color:var(--ink-3)">%</span></div><div class="n">n 39,118, target 90%</div></div>
        <div><span class="lbl">Communities</span><div class="v">41</div><div class="n">7 verticals, one codebase</div></div>
        <div><span class="lbl">Statistics shipped</span><div class="v">34</div><div class="n">each with a method card</div></div>
      </div>
    </div>
  </header>
</template>
