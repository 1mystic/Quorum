import { describe, test, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import GettingStartedCard from './GettingStartedCard.vue'

async function mountCard() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/t/:slug/dashboard', component: { template: '<div />' } },
      { path: '/t/:slug/assistant', component: { template: '<div />' } },
      { path: '/t/:slug/requests/new', component: { template: '<div />' } }
    ]
  })
  router.push('/t/vaikunth-heights/dashboard')
  await router.isReady()
  return mount(GettingStartedCard, {
    props: { slug: 'vaikunth-heights', requestLabel: 'Complaint' },
    global: { plugins: [router] }
  })
}

describe('GettingStartedCard', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  test('shows on a first visit and covers the sidebar, Evidence, assistant and raising a request', async () => {
    const wrapper = await mountCard()
    expect(wrapper.find('.getting-started').exists()).toBe(true)
    expect(wrapper.text()).toContain('sidebar')
    expect(wrapper.text()).toContain('Evidence')
    expect(wrapper.text()).toContain('assistant')
    expect(wrapper.text()).toContain('Raise a complaint')
  })

  test('dismissing hides it and persists across a remount', async () => {
    const wrapper = await mountCard()
    await wrapper.find('.getting-started .icon-tgl').trigger('click')
    expect(wrapper.find('.getting-started').exists()).toBe(false)

    const remounted = await mountCard()
    expect(remounted.find('.getting-started').exists()).toBe(false)
  })

  test('never a blocking modal: no backdrop, the rest of the page stays reachable', async () => {
    const wrapper = await mountCard()
    expect(wrapper.find('[class*="backdrop"]').exists()).toBe(false)
  })
})
