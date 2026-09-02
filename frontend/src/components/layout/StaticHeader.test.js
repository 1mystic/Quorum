import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import StaticHeader from './StaticHeader.vue'
import { useAuthStore } from '../../stores/auth'

async function mountHeader() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/t/:slug/dashboard', component: { template: '<div />' } },
      { path: '/methods', component: { template: '<div />' } }
    ]
  })
  router.push('/methods')
  await router.isReady()
  return { router, wrapper: mount(StaticHeader, { global: { plugins: [router] } }) }
}

describe('StaticHeader', () => {
  test('a logged-out visitor is offered a way back to the landing page', async () => {
    setActivePinia(createPinia())
    const { wrapper } = await mountHeader()

    expect(wrapper.find('.brand').attributes('href')).toBe('/')
    expect(wrapper.find('.static-header-back').text()).toContain('Back to Quorum')
    expect(wrapper.find('.static-header-back').attributes('href')).toBe('/')
  })

  test('a logged-in member is offered a way back to their own dashboard, not the landing page', async () => {
    setActivePinia(createPinia())
    const { wrapper } = await mountHeader()
    const auth = useAuthStore()
    auth.setToken('t')
    auth.setUser({ name: 'A', email: 'a@b.c', tenantSlug: 'vaikunth-heights', tenantName: 'Vaikunth', initials: 'A' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.static-header-back').text()).toContain('Back to dashboard')
    expect(wrapper.find('.static-header-back').attributes('href')).toBe('/t/vaikunth-heights/dashboard')
  })
})
