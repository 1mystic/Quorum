<script setup>
import LandingNav from '../components/landing/LandingNav.vue'
import LandingFooter from '../components/landing/LandingFooter.vue'
</script>

<template>
  <div>
    <LandingNav />
    <section class="sec">
      <div class="wrap" style="max-width:74ch">
        <div class="sec-no"><b>·</b> About</div>
        <h1 style="font-size:var(--fs-h2);margin-top:var(--sp4)">The LLM narrates. Statistics decide.</h1>
        <p style="color:var(--ink-2);margin-top:var(--sp5);font-size:var(--fs-lead);line-height:1.65">
          Quorum is a general community operations platform, not a course project and not an LLM wrapper. Any kind of
          community, a housing society, a campus club, an NGO, an alumni chapter, a co-op, a sports club, a
          professional guild, onboards by slug and switches on the services it needs.
        </p>
        <p style="color:var(--ink-2);margin-top:var(--sp4);line-height:1.65">
          The differentiator is not CRUD and not agentic AI. Those are table stakes now. The differentiator is that
          the platform is a statistical instrument for communities: it treats every community as a stream of
          observable processes and applies real inferential machinery, survival analysis, statistical process
          control, queueing theory, empirical-Bayes shrinkage, calibrated forecasting, conformal prediction,
          social-choice theory, privacy-preserving aggregation, to answer questions communities actually cannot
          answer today.
        </p>
        <p style="color:var(--ink-2);margin-top:var(--sp4);line-height:1.65">
          The agent that writes the summary you read on a dashboard card is never the thing that computed the number
          underneath it. Every statistic that crosses into the UI or into the agent's context arrives as an
          <code class="mono">Evidence</code> envelope: a value, its sample size, its interval, the method that
          produced it, the assumption checks that were run, and whether there was even enough data to say anything
          at all. The agent may narrate that envelope. It may never invent, adjust or recompute the number inside it.
        </p>
        <div class="pull" style="margin-top:var(--sp6)">
          <b>Enough people to decide. Enough data to conclude.</b> Both readings of "quorum" are the product.
        </div>
        <p style="color:var(--ink-2);margin-top:var(--sp5);line-height:1.65">
          Three things follow from that, on purpose: a number is never shown without its evidence, a below-minimum
          sample is shown as calm and deliberately unresolved rather than as an error, and a statistic that is
          computed but not interpretable, a failed proportional-hazards check, an unstable poll count, is withheld
          and explained rather than rounded off and reported anyway.
        </p>
        <div style="margin-top:var(--sp7)">
          <router-link class="tl" to="/methods">Read the method cards behind every figure</router-link>
        </div>
      </div>
    </section>
    <LandingFooter />
  </div>
</template>
