<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Bell } from 'lucide-vue-next'
import { useNotificationsStore } from '../../stores/notifications'
import NotificationsPanel from './NotificationsPanel.vue'

const props = defineProps({
  title: { type: String, required: true },
  sub: { type: String, default: '' },
  showBell: { type: Boolean, default: true }
})

const notificationsStore = useNotificationsStore()
const route = useRoute()
const showPanel = ref(false)
const panelRef = ref(null)
let pollTimer = null

function showNotifications() {
  showPanel.value = !showPanel.value
}

onMounted(() => {
  if (props.showBell) {
    notificationsStore.fetchUnreadCount()
    pollTimer = setInterval(notificationsStore.fetchUnreadCount, 60000)
  }
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<template>
  <header class="topbar">
    <div class="title-block">
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="sub" class="page-sub">{{ sub }}</p>
      <slot name="subtitle"></slot>
    </div>

    <div class="topbar-spacer"></div>

    <slot name="actions"></slot>

    <div v-if="showBell" class="bell-btn" @click="showNotifications">
      <Bell />
      <span v-if="notificationsStore.unreadCount > 0" class="bell-dot">{{ notificationsStore.unreadCount > 99 ? '99+' : notificationsStore.unreadCount }}</span>
      <NotificationsPanel v-if="showPanel" ref="panelRef" :slug="route.params.slug" class="notif-dropdown" @read="notificationsStore.fetchUnreadCount" @click.stop />
    </div>
  </header>
</template>
