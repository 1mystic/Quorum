import { describe, test, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import DecisionDetailView from './DecisionDetailView.vue'
import { getTenant } from '../api/tenant'

vi.mock('../api/tenant', () => ({ getTenant: vi.fn() }))

const DEMO_TENANTS = {
  'vaikunth-heights': {
    name: 'Vaikunth Heights', slug: 'vaikunth-heights', vertical: 'rwa_society',
    description: '214 flats', enabled_packs: ['reliability_ops', 'forecast_risk'], timezone: 'Asia/Kolkata'
  },
  'aavartan-robotics': {
    name: 'Aavartan Robotics', slug: 'aavartan-robotics', vertical: 'campus_club',
    description: '96 members', enabled_packs: ['reliability_ops', 'governance_insight'], timezone: 'Asia/Kolkata'
  }
}

async function mountAt(path) {
  getTenant.mockImplementation((slug) => Promise.resolve(DEMO_TENANTS[slug]))

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/t/:slug/decisions/:id', component: DecisionDetailView },
      { path: '/t/:slug/:pathMatch(.*)*', component: { template: '<div />' } },
      { path: '/methods', component: { template: '<div />' } },
      { path: '/workspace', component: { template: '<div />' } }
    ]
  })
  router.push(path)
  await router.isReady()
  const wrapper = mount(DecisionDetailView, { global: { plugins: [router, createPinia()] } })
  await flushPromises()
  return wrapper
}

describe('DecisionDetailView Condorcet disclosure', () => {
  test('a cycle is disclosed alongside the winner, not hidden behind it', async () => {
    const wrapper = await mountAt('/t/vaikunth-heights/decisions/dc-1')

    expect(wrapper.text()).toContain('Condorcet cycle present')
    expect(wrapper.find('.pill').text()).toBe('Schulze winner')
    expect(wrapper.find('.callout-warn').exists()).toBe(true)
  })

  test('the pairwise matrix renders every option against every other', async () => {
    const wrapper = await mountAt('/t/vaikunth-heights/decisions/dc-1')

    const matrix = wrapper.find('.matrix')
    expect(matrix.exists()).toBe(true)
    // 3 options -> 1 blank corner + 3 column headers + 3 row headers
    expect(matrix.findAll('th').length).toBe(7)
  })

  test('a clean Condorcet winner is labelled as such, no cycle callout', async () => {
    const wrapper = await mountAt('/t/aavartan-robotics/decisions/dc-11')

    expect(wrapper.find('.pill').text()).toBe('Condorcet winner')
    expect(wrapper.find('.callout-warn').exists()).toBe(false)
    expect(wrapper.find('.callout-info').exists()).toBe(true)
  })

  test('an open ballot shows no premature result', async () => {
    const wrapper = await mountAt('/t/vaikunth-heights/decisions/dc-2')

    expect(wrapper.find('.matrix').exists()).toBe(false)
    expect(wrapper.text()).toContain('Ballot still open')
  })
})
