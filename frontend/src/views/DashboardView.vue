<script setup>
import StatTile from '../components/evidence/StatTile.vue'
import SurvivalCurve from '../components/evidence/SurvivalCurve.vue'
import ControlChart from '../components/evidence/ControlChart.vue'
import {
  medianResolution,
  conformalEta,
  openRightNow,
  tankerCycleInsufficient,
  hazardsWithheld,
  kaplanMeierCurve,
  ewmaChart
} from '../fixtures/evidence'
</script>

<template>
  <div class="app">
    <aside class="side">
      <a class="brand" href="/">Quorum</a>
    </aside>

    <div class="main">
      <div class="topbar">
        <div>
          <h1>Resolution</h1>
          <div class="sub">request_flow · demo tenant</div>
        </div>
      </div>

      <div class="content">
        <div class="row r-4">
          <StatTile title="Median time to resolution" subtitle="all categories" :evidence="medianResolution">
            <template #why>
              <p>Requests still open past 30 days skew towards plumbing (censoring test <b>p = 0.04</b>). The median may be optimistic.</p>
            </template>
          </StatTile>

          <StatTile title="ETA · RQ-2214" subtitle="leaking tap, C-704" :evidence="conformalEta" display="range">
            <template #why>
              <p>A conformal interval guarantees marginal coverage: across many requests like this one, <b>90% resolve inside it</b>.</p>
            </template>
          </StatTile>

          <StatTile title="Open right now" subtitle="unresolved, all wings" :evidence="openRightNow" />

          <StatTile title="Water-tanker call-out cycle" subtitle="kaplan-meier · tanker category" :evidence="tankerCycleInsufficient">
            <template #why>
              <p>A curve over 11 observations is a staircase of single events, not an estimate. This is the minimum-n policy doing exactly what it is for.</p>
            </template>
          </StatTile>
        </div>

        <div class="row r-32">
          <SurvivalCurve title="Requests still unresolved, by day" subtitle="kaplan-meier · greenwood 95% band" :evidence="kaplanMeierCurve" />
          <ControlChart title="Weekly request rate" subtitle="ewma control chart" :evidence="ewmaChart" />
        </div>

        <div class="row" style="grid-template-columns:1fr">
          <StatTile title="Resolution speed by wing" subtitle="cox proportional hazards" :evidence="hazardsWithheld">
            <template #why>
              <p>Wing D was slow for six weeks after its pump replacement and ordinary afterwards. A single hazard ratio would average two regimes into one number that reads as decisive and is not.</p>
            </template>
          </StatTile>
        </div>
      </div>
    </div>
  </div>
</template>
