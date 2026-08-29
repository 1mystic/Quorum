<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { requestsFor } from '../fixtures/requests'
import { toast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))

const title = ref('')
const category = ref(tenant.value.requestCategories[0])
const priority = ref(tenant.value.requestPriorities[0])
const location = ref('')
const description = ref('')
const submitting = ref(false)

// text.near_duplicate_candidates runs on submission per docs/STATS_API.md's
// cadence table; here it is a client-side stub over the fixture list.
const nearDuplicate = computed(() => {
  if (title.value.trim().length < 4) return null
  const lower = title.value.toLowerCase()
  return requestsFor(slug.value).find((r) => r.title.toLowerCase().includes(lower.split(' ')[0])) || null
})

function submit() {
  if (!title.value.trim() || !description.value.trim()) {
    toast.error('Title and description are required.')
    return
  }
  submitting.value = true
  window.setTimeout(() => {
    submitting.value = false
    toast.success(`${tenant.value.labels.request} raised. This is a UI stub until the request_flow write path lands.`)
    router.push(`/t/${slug.value}/requests`)
  }, 300)
}
</script>

<template>
  <TenantShell :title="`Raise a ${tenant.labels.request.toLowerCase()}`" subtitle="request_flow">
    <div class="card" style="max-width:640px">
      <form class="form" @submit.prevent="submit">
        <div class="field">
          <label for="title">Title</label>
          <input id="title" v-model="title" type="text" placeholder="Short summary" />
        </div>

        <div v-if="nearDuplicate" class="callout callout-warn">
          <span>Looks similar to <b>{{ nearDuplicate.title }}</b> ({{ nearDuplicate.ref }}), already {{ nearDuplicate.status.replace('_', ' ') }}. You can still raise a new one if this is a different occurrence.</span>
        </div>

        <div class="form-row">
          <div class="field">
            <label for="category">Category</label>
            <select id="category" v-model="category">
              <option v-for="c in tenant.requestCategories" :key="c" :value="c">{{ c.replace(/_/g, ' ') }}</option>
            </select>
          </div>
          <div class="field">
            <label for="priority">Priority</label>
            <select id="priority" v-model="priority">
              <option v-for="p in tenant.requestPriorities" :key="p" :value="p">{{ p.replace(/_/g, ' ') }}</option>
            </select>
          </div>
        </div>

        <div class="field">
          <label for="location">Location</label>
          <input id="location" v-model="location" type="text" placeholder="e.g. C-704, or leave blank" />
        </div>

        <div class="field">
          <label for="description">Description</label>
          <textarea id="description" v-model="description" placeholder="What happened, and since when?"></textarea>
        </div>

        <div style="display:flex;gap:var(--sp3)">
          <button type="submit" class="btn btn-primary" :disabled="submitting"><span>{{ submitting ? 'Submitting…' : 'Submit' }}</span></button>
          <router-link class="btn btn-ghost" :to="`/t/${slug}/requests`">Cancel</router-link>
        </div>
      </form>
    </div>
  </TenantShell>
</template>
