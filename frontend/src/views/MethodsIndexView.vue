<script setup>
import { methodCards } from '../fixtures/methodCards'

const cards = Object.values(methodCards)
</script>

<template>
  <div class="wrap" style="padding-block:var(--sp8)">
    <router-link to="/" class="brand" style="margin-bottom:var(--sp6);display:inline-flex">Quorum</router-link>
    <h1 style="margin-bottom:var(--sp2)">Method cards</h1>
    <p class="sub" style="margin-bottom:var(--sp6)">Every statistic on the platform links here. Public, unauthenticated, per docs/STATS_API.md §4.</p>

    <div class="list">
      <router-link v-for="c in cards" :key="c.id" class="list-row" :to="`/methods/${c.id}`">
        <div class="lr-main">
          <div class="lr-title">{{ c.name }}</div>
          <div class="lr-sub">{{ c.id }} · min n {{ c.min_n }}</div>
        </div>
      </router-link>
    </div>
  </div>
</template>
