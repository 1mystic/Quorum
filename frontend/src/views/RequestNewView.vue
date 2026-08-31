<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import SelectField from '../components/ui/SelectField.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { toast } from '../composables/useToast'
import { raiseRequest } from '../api/requests'
import { myApprovedGroups } from '../api/groups'
import { ApiError, NetworkError } from '../api/client'

// Real POST /api/t/{slug}/requests (app/api/request.py). A request always
// belongs to a group, so the group picker is real too (GET .../groups/me).
// text.near_duplicate_candidates (docs/STATS_API.md's "runs on submission")
// has no route yet, so there is no live near-duplicate check here - the old
// fixture-backed one is removed rather than left half-real.

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))

const categoryOptions = computed(() => tenant.value.requestCategories.map((c) => ({ value: c, label: c.replace(/_/g, ' ') })))
const priorityOptions = computed(() => tenant.value.requestPriorities.map((p) => ({ value: p, label: p.replace(/_/g, ' ') })))

const title = ref('')
const category = ref(tenant.value.requestCategories[0])
const priority = ref(tenant.value.requestPriorities[0])
const location = ref('')
const description = ref('')
const submitting = ref(false)
const errorMessage = ref('')

const groups = ref([])
const groupsLoading = ref(true)
const groupId = ref(null)
const groupOptions = computed(() => groups.value.map((g) => ({ value: g.id, label: g.name })))

onMounted(async () => {
  try {
    groups.value = await myApprovedGroups(slug.value)
    if (groups.value.length) groupId.value = groups.value[0].id
  } catch (err) {
    errorMessage.value = err instanceof NetworkError ? err.message : 'Could not load your groups.'
  } finally {
    groupsLoading.value = false
  }
})

async function submit() {
  if (!title.value.trim() || !description.value.trim()) {
    toast.error('Title and description are required.')
    return
  }
  if (!groupId.value) {
    toast.error('You need to be an approved member of a group to raise a ' + tenant.value.labels.request.toLowerCase() + '.')
    return
  }
  submitting.value = true
  errorMessage.value = ''
  try {
    await raiseRequest(slug.value, {
      group_id: groupId.value,
      category: category.value,
      priority: priority.value,
      location_ref: location.value || null,
      title: title.value,
      description: description.value
    })
    toast.success(`${tenant.value.labels.request} raised.`)
    router.push(`/t/${slug.value}/requests`)
  } catch (err) {
    errorMessage.value = (err instanceof NetworkError || err instanceof ApiError) ? err.message : 'Something went wrong.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <TenantShell :title="`Raise a ${tenant.labels.request.toLowerCase()}`" subtitle="request_flow">
    <div class="card" style="max-width:640px">
      <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>

      <div v-if="!groupsLoading && !groups.length" class="callout callout-warn">
        <span>You are not an approved member of any group yet, so there is nowhere to file this. Join a group first.</span>
      </div>

      <form class="form" @submit.prevent="submit">
        <div v-if="groups.length" class="field">
          <label for="group">Group</label>
          <SelectField id="group" v-model="groupId" :options="groupOptions" />
        </div>

        <div class="field">
          <label for="title">Title</label>
          <input id="title" v-model="title" type="text" placeholder="Short summary" />
        </div>

        <div class="form-row">
          <div class="field">
            <label for="category">Category</label>
            <SelectField id="category" v-model="category" :options="categoryOptions" />
          </div>
          <div class="field">
            <label for="priority">Priority</label>
            <SelectField id="priority" v-model="priority" :options="priorityOptions" />
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
