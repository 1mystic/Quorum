import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import LedgerView from './LedgerView.vue'
import { useToastState } from '../composables/useToast'

async function mountAt(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/t/:slug/ledger', component: LedgerView },
      { path: '/t/:slug/:pathMatch(.*)*', component: { template: '<div />' } },
      { path: '/methods', component: { template: '<div />' } },
      { path: '/workspace', component: { template: '<div />' } }
    ]
  })
  router.push(path)
  await router.isReady()
  return mount(LedgerView, { global: { plugins: [router, createPinia()] } })
}

describe('LedgerView mark-paid flow', () => {
  test('a pending entry can be marked paid and the button disables', async () => {
    const wrapper = await mountAt('/t/vaikunth-heights/ledger')

    const rows = wrapper.findAll('tbody tr')
    const pendingRow = rows.find((r) => r.text().includes('LE-9912'))
    expect(pendingRow).toBeTruthy()

    const button = pendingRow.find('button')
    expect(button.text()).toBe('Mark paid')

    await button.trigger('click')

    expect(button.text()).toBe('Marked')
    expect(button.attributes('disabled')).toBeDefined()
  })

  test('marking paid queues a toast', async () => {
    const { toasts } = useToastState()
    toasts.value = []

    const wrapper = await mountAt('/t/vaikunth-heights/ledger')
    const rows = wrapper.findAll('tbody tr')
    const pendingRow = rows.find((r) => r.text().includes('LE-9912'))
    await pendingRow.find('button').trigger('click')

    expect(toasts.value.some((t) => t.message.includes('LE-9912'))).toBe(true)
  })

  test('verification lag and receipt gap render through StatTile, never a bare number', async () => {
    const wrapper = await mountAt('/t/vaikunth-heights/ledger')
    expect(wrapper.text()).toContain('Verification lag')
    expect(wrapper.text()).toContain('Receipt collection gap')
    expect(wrapper.findAll('.audit').length).toBeGreaterThan(0)
  })
})
