<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import TenantShell from '../components/layout/TenantShell.vue'
import { tenantBySlug } from '../fixtures/tenants'
import { membersFor } from '../fixtures/members'
import { toast } from '../composables/useToast'

const route = useRoute()
const slug = computed(() => route.params.slug)
const tenant = computed(() => tenantBySlug(slug.value))
const pending = ref(membersFor(slug.value).filter((m) => m.status === 'pending'))

function approve(m) {
  pending.value = pending.value.filter((x) => x.id !== m.id)
  toast.success(`${m.name} approved. UI stub until the membership write path lands.`)
}
function reject(m) {
  pending.value = pending.value.filter((x) => x.id !== m.id)
  toast.info(`${m.name} rejected.`)
}
</script>

<template>
  <TenantShell title="Approvals" :subtitle="`${tenant.labels.member.toLowerCase()} join requests · ${pending.length} pending`">
    <div class="card">
      <div v-if="!pending.length" class="empty-state">
        <h3>Queue is clear</h3>
        <p>No pending {{ tenant.labels.member.toLowerCase() }} approvals right now.</p>
      </div>
      <div v-else class="list">
        <div v-for="m in pending" :key="m.id" class="list-row">
          <div class="lr-main">
            <div class="lr-title">{{ m.name }}</div>
            <div class="lr-sub">{{ m.role.replace('_', ' ') }} · {{ tenant.vertical === 'rwa_society' ? m.unit : `Y${m.year} ${m.department}` }}</div>
          </div>
          <div class="lr-meta">
            <button class="btn btn-ghost" style="min-height:36px;padding:8px 14px" @click="reject(m)">Reject</button>
            <button class="btn btn-primary" style="min-height:36px;padding:8px 14px" @click="approve(m)"><span>Approve</span></button>
          </div>
        </div>
      </div>
    </div>
  </TenantShell>
</template>
