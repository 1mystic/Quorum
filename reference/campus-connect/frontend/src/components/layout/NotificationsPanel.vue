<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '../../composables/useToast'   // add this
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '../../api/notifications'

const props = defineProps({ slug: { type: String, required: true } })
const emit = defineEmits(['read'])
const router = useRouter()
const items = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    items.value = await getNotifications({ limit: 20 })
  } catch (error) {
    console.error('Failed to load notifications:', error)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function openItem(item) {
  if (!item.is_read) {
    try {
      await markNotificationRead(item.id)
      item.is_read = true
      emit('read')
    } catch (error) {
       toast.error(error.message)  
    }
  }
  if (item.event_id) router.push(`/${props.slug}/events/${item.event_id}`)
  else if (item.club_id) router.push(`/${props.slug}/clubs/${item.club_id}`)
}

async function markAll() {
  try {
    await markAllNotificationsRead()
    items.value.forEach(i => (i.is_read = true))
    emit('read')
  } catch (error) {
    toast.error(error.message)  
  }
}

defineExpose({ load })
</script>

<template>
  <div class="notif-panel">
    <div class="notif-panel-header">
      <span>Notifications</span>
      <button class="notif-mark-all" @click="markAll">Mark all read</button>
    </div>
    <div v-if="loading" class="notif-empty">Loading...</div>
    <div v-else-if="items.length === 0" class="notif-empty">You're all caught up.</div>
    <div v-else class="notif-list">
      <div v-for="item in items" :key="item.id" class="notif-item" :class="{ unread: !item.is_read }" @click="openItem(item)">
        <p class="notif-message">{{ item.message }}</p>
        <span class="notif-time">{{ new Date(item.created_at).toLocaleString() }}</span>
      </div>
    </div>
  </div>
</template>