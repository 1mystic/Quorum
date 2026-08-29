<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { methodCard } from '../fixtures/methodCards'

// GET /api/methods/{method_id} per docs/STATS_API.md §4: not tenant-scoped,
// public and unauthenticated, because a Method Card is a property of the
// mathematics and the trust story only works if a sceptical reader can
// check it without an account.

const route = useRoute()
const card = computed(() => methodCard(route.params.id))
</script>

<template>
  <div class="wrap" style="padding-block:var(--sp8)">
    <router-link to="/" class="brand" style="margin-bottom:var(--sp6);display:inline-flex">Quorum</router-link>

    <div v-if="card" class="card">
      <div class="chead"><div><h1 style="font-size:1.6rem">{{ card.name }}</h1><div class="sub">{{ card.id }}</div></div></div>
      <p style="font-size:15.5px;line-height:1.7;color:var(--ink-2)">{{ card.one_liner }}</p>

      <div class="row r-32" style="margin-top:var(--sp4)">
        <div>
          <h3 style="margin-bottom:var(--sp3)">Assumes</h3>
          <ul style="padding-left:1.2em;display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--ink-2)">
            <li v-for="(a, i) in card.assumes" :key="i">{{ a }}</li>
          </ul>
        </div>
        <div>
          <h3 style="margin-bottom:var(--sp3)">Wrong when</h3>
          <ul style="padding-left:1.2em;display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--ink-2)">
            <li v-for="(w, i) in card.wrong_when" :key="i">{{ w }}</li>
          </ul>
        </div>
      </div>

      <div class="meta" style="margin-top:var(--sp4)">
        <span><b>min n</b> {{ card.min_n }}</span>
      </div>

      <h3 style="margin-top:var(--sp4)">What the interval means</h3>
      <p style="font-size:14px;color:var(--ink-2)">{{ card.interval_meaning }}</p>

      <h3 style="margin-top:var(--sp4)">References</h3>
      <ul style="padding-left:1.2em;font-size:13px;color:var(--ink-3)">
        <li v-for="(r, i) in card.references" :key="i">{{ r }}</li>
      </ul>
    </div>

    <div v-else class="empty-state">
      <h3>No method card for "{{ route.params.id }}"</h3>
      <p><router-link to="/methods">Browse all method cards</router-link></p>
    </div>
  </div>
</template>
