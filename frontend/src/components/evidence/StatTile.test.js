import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatTile from './StatTile.vue'
import { medianResolution, tankerCycleInsufficient, hazardsWithheld } from '../../fixtures/evidence'

describe('StatTile', () => {
  test('shows the estimate pill and audit line for a clean reading', () => {
    const wrapper = mount(StatTile, {
      props: { title: 'Median time to resolution', evidence: { ...medianResolution, checks: [] } }
    })

    expect(wrapper.find('.pill').text()).toBe('Estimate')
    expect(wrapper.find('.audit').text()).toContain(medianResolution.method)
    expect(wrapper.find('.audit').text()).toContain(medianResolution.params_hash)
  })

  test('qualified reading keeps the pill honest, not styled as clean', () => {
    const wrapper = mount(StatTile, {
      props: { title: 'Median time to resolution', evidence: medianResolution }
    })

    expect(wrapper.find('.pill').text()).toBe('Qualified')
    expect(wrapper.find('.pill').classes()).toContain('p-qual')
  })

  test('the why modal is closed by default, opens on trigger, closes on the X', async () => {
    const wrapper = mount(StatTile, {
      props: { title: 'Median time to resolution', evidence: medianResolution },
      slots: { why: '<p>because</p>' },
      attachTo: document.body
    })

    expect(document.querySelector('.why-modal-backdrop')).toBeNull()

    await wrapper.find('.why-trigger').trigger('click')
    const backdrop = document.querySelector('.why-modal-backdrop')
    expect(backdrop).not.toBeNull()
    // the qualifying-check explanation (moved out of EvidenceValue.vue) is
    // included ahead of the custom #why slot content, not lost
    expect(document.querySelector('.why-modal-body').textContent).toContain(
      medianResolution.checks[0].detail
    )
    expect(document.querySelector('.why-modal-body').textContent).toContain('because')
    expect(document.activeElement).toBe(document.querySelector('.why-modal-close'))

    document.querySelector('.why-modal-close').click()
    await wrapper.vm.$nextTick()
    expect(document.querySelector('.why-modal-backdrop')).toBeNull()
    expect(document.activeElement).toBe(wrapper.find('.why-trigger').element)

    wrapper.unmount()
  })

  test('insufficient data reads calm: waiting pill, muted card, no error styling', () => {
    const wrapper = mount(StatTile, {
      props: { title: 'Water-tanker call-out cycle', evidence: tankerCycleInsufficient }
    })

    expect(wrapper.find('.pill').text()).toBe('Waiting')
    expect(wrapper.find('.pill').classes()).toContain('p-wait')
    expect(wrapper.classes()).toContain('muted')
  })

  test('a blocking check withholds the tile value', () => {
    const wrapper = mount(StatTile, {
      props: { title: 'Resolution speed by wing', evidence: hazardsWithheld }
    })

    expect(wrapper.find('.pill').text()).toBe('Withheld')
    expect(wrapper.find('.withheld').exists()).toBe(true)
  })
})
