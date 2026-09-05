import { describe, test, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import TenantShell from './TenantShell.vue'
import { useAuthStore } from '../../stores/auth'
import { getTenant } from '../../api/tenant'

vi.mock('../../api/tenant', () => ({ getTenant: vi.fn() }))

async function mountShell() {
  getTenant.mockResolvedValue({
    name: 'Vaikunth Heights',
    slug: 'vaikunth-heights',
    vertical: 'rwa_society',
    description: '214 flats',
    enabled_packs: ['reliability_ops', 'forecast_risk'],
    timezone: 'Asia/Kolkata'
  })

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/t/:slug/dashboard', component: { template: '<div>dashboard</div>' } },
      { path: '/t/:slug/requests', component: { template: '<div>requests</div>' } },
      { path: '/t/:slug/:pathMatch(.*)*', component: { template: '<div />' } },
      { path: '/methods', component: { template: '<div />' } },
      { path: '/login', component: { template: '<div />' } }
    ]
  })
  router.push('/t/vaikunth-heights/dashboard')
  await router.isReady()
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(TenantShell, {
    props: { title: 'Overview' },
    global: { plugins: [router, pinia] },
    slots: { default: '<div>page content</div>' }
  })
  await flushPromises()
  return { router, wrapper }
}

describe('TenantShell mobile nav drawer', () => {
  test('the drawer is closed by default', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.find('aside.side').classes()).not.toContain('open')
  })

  test('the hamburger opens the drawer', async () => {
    const { wrapper } = await mountShell()
    await wrapper.find('.nav-toggle').trigger('click')
    expect(wrapper.find('aside.side').classes()).toContain('open')
    expect(wrapper.find('.side-backdrop').classes()).toContain('open')
  })

  test('the close button closes the drawer and Escape closes it too', async () => {
    const { wrapper } = await mountShell()
    await wrapper.find('.nav-toggle').trigger('click')
    await wrapper.find('.side-close').trigger('click')
    expect(wrapper.find('aside.side').classes()).not.toContain('open')

    await wrapper.find('.nav-toggle').trigger('click')
    expect(wrapper.find('aside.side').classes()).toContain('open')
    await document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('aside.side').classes()).not.toContain('open')
  })

  test('clicking the backdrop closes the drawer', async () => {
    const { wrapper } = await mountShell()
    await wrapper.find('.nav-toggle').trigger('click')
    await wrapper.find('.side-backdrop').trigger('click')
    expect(wrapper.find('aside.side').classes()).not.toContain('open')
  })

  test('clicking a nav link closes the drawer', async () => {
    const { wrapper } = await mountShell()
    await wrapper.find('.nav-toggle').trigger('click')
    const requestsLink = wrapper.findAll('a.ni').find((a) => a.text() === 'Requests')
    await requestsLink.trigger('click')
    expect(wrapper.find('aside.side').classes()).not.toContain('open')
  })

  test('the sidebar carries one Insights section, not one per pack', async () => {
    const { wrapper } = await mountShell()
    const labels = wrapper.findAll('.navgrp > .lbl').map((l) => l.text())
    expect(labels.filter((l) => l.startsWith('Pack ')).length).toBe(0)
    expect(labels).toContain('Insights')
  })
})

describe('TenantShell tenant panel and sign-out', () => {
  test('the tenant panel is a static label, not a clickable list of alternatives', async () => {
    const { wrapper } = await mountShell()
    expect(wrapper.findAll('.tenant button').length).toBe(0)
    expect(wrapper.find('.tn-static').exists()).toBe(true)
    expect(wrapper.find('.tn-static').text()).toContain('Vaikunth Heights')
  })

  test('sign-out clears the session and lands on /login', async () => {
    const { wrapper, router } = await mountShell()
    const auth = useAuthStore()
    auth.setToken('t')
    auth.setUser({ name: 'A', email: 'a@b.c', tenantSlug: 'vaikunth-heights', tenantName: 'Vaikunth', initials: 'A' })

    const signOut = wrapper.findAll('button.ni').find((b) => b.text().includes('Sign out'))
    expect(signOut).toBeTruthy()
    await signOut.trigger('click')
    await flushPromises()

    expect(auth.isLoggedIn).toBe(false)
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
