import { describe, test, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import AssistantView from './AssistantView.vue'
import { chat } from '../api/ai'

vi.mock('../api/ai', () => ({ chat: vi.fn() }))

async function mountAt(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/t/:slug/assistant', component: AssistantView },
      { path: '/t/:slug/:pathMatch(.*)*', component: { template: '<div />' } },
      { path: '/methods', component: { template: '<div />' } },
      { path: '/workspace', component: { template: '<div />' } }
    ]
  })
  router.push(path)
  await router.isReady()
  return mount(AssistantView, { global: { plugins: [router, createPinia()] } })
}

describe('AssistantView', () => {
  beforeEach(() => {
    chat.mockReset()
    sessionStorage.clear()
  })

  test('shows the empty state with suggestion chips before any message is sent', async () => {
    const wrapper = await mountAt('/t/vaikunth-heights/assistant')
    expect(wrapper.find('.assistant-empty').exists()).toBe(true)
    expect(wrapper.findAll('.chip').length).toBeGreaterThan(0)
  })

  test('sending a message renders both turns and the reply, no bare JSON', async () => {
    chat.mockResolvedValue({
      reply: 'Here are two groups that match.',
      kind: 'groups',
      items: [{ id: 1, name: 'Robotics Club', category: 'technology', member_count: 12, entity_kind: 'group' }],
      degraded: false,
      offline: false,
      tools_used: ['search_groups'],
      iterations: 1,
      budget_exhausted: false
    })

    const wrapper = await mountAt('/t/vaikunth-heights/assistant')
    await wrapper.find('.chip').trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Here are two groups that match.')
    expect(wrapper.find('.assistant-item .lr-title').text()).toBe('Robotics Club')
    expect(wrapper.text()).not.toContain('{"id"')
  })

  test('a degraded, offline answer shows both notices honestly, not hidden', async () => {
    chat.mockResolvedValue({
      reply: 'Sample data - here is what I could find.',
      kind: 'groups',
      items: [],
      degraded: true,
      offline: true,
      tools_used: [],
      iterations: 0,
      budget_exhausted: false
    })

    const wrapper = await mountAt('/t/vaikunth-heights/assistant')
    wrapper.vm.draft = 'what groups match my interests'
    await wrapper.find('.assistant-composer').trigger('submit')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.assistant-tag.is-degraded').exists()).toBe(true)
    expect(wrapper.find('.assistant-tag.is-offline').exists()).toBe(true)
  })

  test('a failed request keeps the question on screen and marks the answer as failed', async () => {
    chat.mockRejectedValue(new Error('network down'))

    const wrapper = await mountAt('/t/vaikunth-heights/assistant')
    wrapper.vm.draft = 'anything happening this week'
    await wrapper.find('.assistant-composer').trigger('submit')
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.assistant-msg.is-user').text()).toBe('anything happening this week')
    expect(wrapper.find('.assistant-msg.is-failed').exists()).toBe(true)
  })
})
