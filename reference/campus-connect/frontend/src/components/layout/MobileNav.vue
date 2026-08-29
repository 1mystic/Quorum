<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
  items: { type: Array, required: true },
  roleClass: { type: String, required: true }
})

const route = useRoute()

// Among every non-exact item whose path is a prefix of the current route,
// only the longest one should be treated as active. Without this, two
// items whose paths share a prefix (like "/clubs" and "/clubs/propose")
// could both light up at once.
const bestMatchPath = computed(function findBestMatch() {
  const candidatePaths = props.items
    .filter(function isPrefixMatchable(item) { return !item.exact })
    .map(function getPath(item) { return item.to })
    .filter(function matchesCurrentRoute(path) {
      return route.path === path || route.path.startsWith(path + '/')
    })

  if (candidatePaths.length === 0) {
    return null
  }

  return candidatePaths.reduce(function pickLongest(longestSoFar, path) {
    return path.length > longestSoFar.length ? path : longestSoFar
  })
})

function isActive(item) {
  if (item.exact) {
    return route.path === item.to
  }
  return item.to === bestMatchPath.value
}
</script>

<template>
  <nav class="mobile-nav">
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="mobile-nav-item"
      :class="[roleClass, { active: isActive(item) }]"
    >
      <component :is="item.icon" />
      <span>{{ item.label }}</span>
    </router-link>
  </nav>
</template>
