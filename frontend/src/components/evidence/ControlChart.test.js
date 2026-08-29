import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ControlChart from './ControlChart.vue'
import { ewmaChart, tankerCycleInsufficient } from '../../fixtures/evidence'

describe('ControlChart', () => {
  test('draws the series, centre line and control limits', () => {
    const wrapper = mount(ControlChart, {
      props: { title: 'Weekly request rate', evidence: ewmaChart }
    })

    expect(wrapper.find('svg.chart').exists()).toBe(true)
    expect(wrapper.text()).toContain('UCL')
    expect(wrapper.text()).toContain('LCL')
  })

  test('the signalled point is highlighted and the pill counts it', () => {
    const wrapper = mount(ControlChart, {
      props: { title: 'Weekly request rate', evidence: ewmaChart }
    })

    expect(wrapper.find('.pill').text()).toContain('1 signal')
    // 20 points total, one of them signalled and drawn larger (r=6)
    const bigCircles = wrapper.findAll('svg circle[r="6"]')
    expect(bigCircles.length).toBe(1)
  })

  test('insufficient data never draws a chart', () => {
    const wrapper = mount(ControlChart, {
      props: { title: 'Weekly request rate', evidence: tankerCycleInsufficient }
    })

    expect(wrapper.find('svg.chart').exists()).toBe(false)
  })
})
