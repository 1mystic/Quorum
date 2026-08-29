import { defineStore } from 'pinia'
import { getUnreadCount, markAnnouncementsRead } from '../api/announcements'

export const useAnnouncementsStore = defineStore('announcements', {
  state: () => ({ unreadCount: 0 }),
  actions: {
    async fetchUnreadCount() {
      try {
        const data = await getUnreadCount()
        this.unreadCount = data.count
      } catch (error) {
        console.error('Failed to load announcement unread count:', error)
      }
    },
    async markRead() {
      try {
        await markAnnouncementsRead()
        this.unreadCount = 0
      } catch (error) {
        console.error('Failed to mark announcements read:', error)
      }
    }
  }
})