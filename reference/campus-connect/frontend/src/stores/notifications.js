import { defineStore } from 'pinia'
import { getUnreadNotificationCount } from '../api/notifications'

export const useNotificationsStore = defineStore('notifications', {
  state: () => ({ unreadCount: 0 }),
  actions: {
    async fetchUnreadCount() {
      try {
        const data = await getUnreadNotificationCount()
        this.unreadCount = data.count
      } catch (error) {
        console.error('Failed to load notification count:', error)
      }
    }
  }
})