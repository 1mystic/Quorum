<script setup>
import { ArrowRight } from 'lucide-vue-next'
</script>

<template>
  <section class="sec alt" id="uncertainty">
    <div class="wrap">
      <div class="sec-head rv">
        <div class="sec-no"><b>02</b> Thesis</div>
        <div>
          <h2>Every other tool shows you a number. We show you how much of one it is.</h2>
          <p>"Average resolution: 3.2 days" is not a fact, it is a summary of a choice. Which tickets were counted, which were quietly dropped, and how wide the honest answer really is.</p>
        </div>
      </div>
      <div class="uncert">
        <figure class="plate rv">
          <svg viewBox="0 0 560 300" role="img" aria-label="Kaplan-Meier curve with a 95% Greenwood confidence band">
            <defs>
              <pattern id="hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
                <line x1="0" y="0" x2="0" y2="6" stroke="var(--s1)" stroke-width="1.4" opacity=".28" />
              </pattern>
            </defs>
            <g stroke="var(--grid)" stroke-width="1">
              <line x1="52" y1="30" x2="536" y2="30" /><line x1="52" y1="90" x2="536" y2="90" />
              <line x1="52" y1="150" x2="536" y2="150" /><line x1="52" y1="210" x2="536" y2="210" />
              <line x1="52" y1="258" x2="536" y2="258" />
            </g>
            <g font-family="JetBrains Mono, monospace" font-size="10" fill="var(--ink-4)">
              <text x="44" y="34" text-anchor="end">100%</text><text x="44" y="94" text-anchor="end">75</text>
              <text x="44" y="154" text-anchor="end">50</text><text x="44" y="214" text-anchor="end">25</text>
              <text x="52" y="278">0 d</text><text x="292" y="278" text-anchor="middle">7 d</text><text x="536" y="278" text-anchor="end">14 d</text>
            </g>
            <path d="M52,30 L86,30 L86,44 L120,44 L120,66 L155,66 L155,88 L190,88 L190,104 L224,104 L224,126 L258,126 L258,142 L292,142 L292,158 L327,158 L327,172 L361,172 L361,186 L396,186 L396,196 L430,196 L430,206 L465,206 L465,214 L500,214 L500,220 L536,220 L536,254 L52,254 Z" fill="url(#hatch)" opacity=".55" />
            <path d="M52,30 L86,30 L86,37 L120,37 L120,55 L155,55 L155,77 L190,77 L190,96 L224,96 L224,115 L258,115 L258,134 L292,134 L292,151 L327,151 L327,166 L361,166 L361,179 L396,179 L396,190 L430,190 L430,199 L465,199 L465,208 L500,208 L500,214 L536,214"
              fill="none" stroke="var(--s1)" stroke-width="2.6" stroke-linejoin="round" />
            <g stroke="var(--ink-3)" stroke-width="1.4" opacity=".8">
              <line x1="206" y1="101" x2="206" y2="111" /><line x1="311" y1="153" x2="311" y2="163" />
              <line x1="413" y1="189" x2="413" y2="199" /><line x1="482" y1="203" x2="482" y2="213" />
            </g>
            <g>
              <line x1="212" y1="134" x2="292" y2="134" stroke="var(--accent)" stroke-width="1.6" stroke-dasharray="3 3" />
              <circle cx="252" cy="134" r="4" fill="var(--accent)" />
              <text x="258" y="128" font-family="JetBrains Mono, monospace" font-size="10.5" fill="var(--ink-2)">median 4.3 d</text>
            </g>
          </svg>
          <figcaption>survival.kaplan_meier, n 187 requests, 44 still open and censored, not dropped, band = greenwood-95, ticks mark censoring</figcaption>
        </figure>
        <div class="rv">
          <h3>The bug is in every dashboard you have used.</h3>
          <p>Average resolution time is usually computed over closed tickets only. But a ticket that is still open has an <em>unknown</em> resolution time, and the ones still open are exactly the slow ones. Dropping them does not make the number neutral. It biases it downward, every single time.</p>
          <div class="pull"><b>Quorum censors instead of dropping.</b> The 44 open requests above contribute what is known about them, that they have already exceeded their current age, and the curve is honest as a result.</div>
          <p>Same discipline everywhere else. A vendor at 3-for-3 does not outrank one at 47-for-52. A forecast that cannot beat a seasonal-naive baseline does not ship. A "30% risk" bucket is checked against whether 30% of it actually defaulted.</p>
          <router-link class="tl" to="/methods/survival.kaplan_meier">See it running in the dashboard<ArrowRight :size="14" /></router-link>
        </div>
      </div>
    </div>
  </section>
</template>
