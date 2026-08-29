import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SurvivalCurve from './SurvivalCurve.vue'
import { kaplanMeierCurve, tankerCycleInsufficient } from '../../fixtures/evidence'

describe('SurvivalCurve', () => {
  test('draws the step curve and its band when there is enough data', () => {
    const wrapper = mount(SurvivalCurve, {
      props: { title: 'Requests still unresolved, by day', evidence: kaplanMeierCurve }
    })

    expect(wrapper.find('svg.chart').exists()).toBe(true)
    // one path for the band, one for the step line
    expect(wrapper.findAll('svg path').length).toBeGreaterThanOrEqual(2)
  })

  test('n_censored > 0 is surfaced in the legend and the audit line', () => {
    const wrapper = mount(SurvivalCurve, {
      props: { title: 'Requests still unresolved, by day', evidence: kaplanMeierCurve }
    })

    expect(wrapper.text()).toContain('censoring tick')
    expect(wrapper.find('.audit').text()).toContain('44')
    expect(wrapper.find('.audit').text()).toContain('censored')
  })

  test('censoring ticks are drawn on the chart, one per censored observation supplied', () => {
    const wrapper = mount(SurvivalCurve, {
      props: { title: 'Requests still unresolved, by day', evidence: kaplanMeierCurve }
    })

    const ticks = wrapper.findAll('svg line[stroke="var(--ink-4)"]')
    expect(ticks.length).toBe(kaplanMeierCurve.value.censor_x.length)
  })

  test('insufficient data never draws a curve, falls back to the calm empty state', () => {
    const wrapper = mount(SurvivalCurve, {
      props: { title: 'Water-tanker call-out cycle', evidence: tankerCycleInsufficient }
    })

    expect(wrapper.find('svg.chart').exists()).toBe(false)
    expect(wrapper.text()).toContain('Not enough data')
  })
})
