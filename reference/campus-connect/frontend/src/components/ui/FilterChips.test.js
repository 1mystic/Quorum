import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FilterChips from './FilterChips.vue'

const chips = [
  { id: 'all', label: 'All' },
  { id: 'tech', label: 'Tech' },
  { id: 'arts', label: 'Arts' }
]

describe('FilterChips', () => {
  test('renders one button per chip', () => {
    const wrapper = mount(FilterChips, { props: { chips, modelValue: 'all' } })

    expect(wrapper.findAll('.filter-chip').length).toBe(3)
  })

  test('marks only the selected chip as active', () => {
    const wrapper = mount(FilterChips, { props: { chips, modelValue: 'tech' } })

    const buttons = wrapper.findAll('.filter-chip')
    expect(buttons[0].classes()).not.toContain('active')
    expect(buttons[1].classes()).toContain('active')
    expect(buttons[2].classes()).not.toContain('active')
  })

  test('emits update:modelValue with the chip id when clicked', async () => {
    const wrapper = mount(FilterChips, { props: { chips, modelValue: 'all' } })

    await wrapper.findAll('.filter-chip')[2].trigger('click')

    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['arts'])
  })
})
