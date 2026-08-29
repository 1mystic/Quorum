import { defineStore } from 'pinia'

// Campus admin owns the club rules/guidelines and the application template link.
// In the mock build this lives in localStorage so the admin's CRUD edits persist
// and show up for club leaders on the create-club form. Swap the load/persist
// helpers for real API calls when the backend is ready.

const SECTIONS = ['Creating a Club', 'Managing Members', 'Operating & Events']

const DEFAULT_TEMPLATE = 'https://docs.google.com/document/d/campus-connect-club-application-template/edit'

const DEFAULT_ITEMS = [
  { id: 1, section: 'Creating a Club', text: 'Copy the Google Docs application template linked above, fill it in, and submit the shareable link.' },
  { id: 2, section: 'Creating a Club', text: 'A club needs at least 10 founding members from a verified college email domain.' },
  { id: 3, section: 'Creating a Club', text: 'Club objectives must align with campus policy and pose no reputational or safety risk.' },
  { id: 4, section: 'Managing Members', text: 'Respond to join requests within 7 days and keep the member roster up to date.' },
  { id: 5, section: 'Managing Members', text: 'Every club must appoint at least two officers in addition to the club leader.' },
  { id: 6, section: 'Operating & Events', text: 'Announce events at least 3 days in advance through the platform.' },
  { id: 7, section: 'Operating & Events', text: 'Publish attendance and results within 48 hours of each event so certificates issue on time.' }
]

function loadItems() {
  try {
    const raw = localStorage.getItem('cc_guidelines_items')
    if (raw) {
      return JSON.parse(raw)
    }
  } catch (error) {
    // fall through to defaults
  }
  return DEFAULT_ITEMS.map(function copyItem(item) {
    return { ...item }
  })
}

function loadTemplate() {
  return localStorage.getItem('cc_guidelines_template') || DEFAULT_TEMPLATE
}

export const useGuidelinesStore = defineStore('guidelines', {
  state: () => ({
    sectionsList: SECTIONS.slice(),
    items: loadItems(),
    templateLink: loadTemplate()
  }),

  getters: {
    itemsBySection: (state) => (section) => {
      return state.items.filter(function inSection(item) {
        return item.section === section
      })
    }
  },

  actions: {
    persist() {
      localStorage.setItem('cc_guidelines_items', JSON.stringify(this.items))
      localStorage.setItem('cc_guidelines_template', this.templateLink)
    },

    addItem(section, text) {
      const clean = text.trim()
      if (!clean) {
        return
      }
      const id = Date.now() + Math.floor(Math.random() * 1000)
      this.items.push({ id, section, text: clean })
      this.persist()
    },

    updateItem(id, text) {
      const clean = text.trim()
      if (!clean) {
        return
      }
      const item = this.items.find(function match(entry) {
        return entry.id === id
      })
      if (item) {
        item.text = clean
        this.persist()
      }
    },

    removeItem(id) {
      this.items = this.items.filter(function keep(entry) {
        return entry.id !== id
      })
      this.persist()
    },

    setTemplateLink(link) {
      this.templateLink = link.trim()
      this.persist()
    }
  }
})
