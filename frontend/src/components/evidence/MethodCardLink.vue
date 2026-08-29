<script setup>
import { computed } from 'vue'
import { methodCardHref } from '../../utils/evidence'

// Links Evidence.method to its Method Card (GET /api/methods/{method} once
// the backend exists). Every figure on the platform links here - it is how
// a reader learns what a stated interval actually guarantees.

const props = defineProps({
  method: {
    type: String,
    required: true
  }
})

const href = computed(() => methodCardHref(props.method))
</script>

<template>
  <a class="method-card-link" :href="href">{{ method }}</a>
</template>
