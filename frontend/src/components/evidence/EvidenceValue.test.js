import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EvidenceValue from './EvidenceValue.vue'
import {
  medianResolution,
  tankerCycleInsufficient,
  hazardsWithheld
} from '../../fixtures/evidence'

describe('EvidenceValue', () => {
  test('estimate: renders the value, n and interval', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: medianResolution } })

    expect(wrapper.find('.big').text()).toContain('4.3')
    expect(wrapper.text()).toContain('187')
    expect(wrapper.text()).toContain('3.4')
    expect(wrapper.text()).toContain('5.6')
  })

  test('qualified: value still shown, the check explanation is not inline', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: medianResolution } })

    // medianResolution carries a non-blocking WARN check. The explanation
    // itself now lives in StatTile.vue's why modal, not rendered inline
    // here, so a qualified card is structurally identical to an estimate
    // or waiting card in the same grid row until its modal is opened.
    expect(wrapper.classes()).toContain('ev-qualified')
    expect(wrapper.find('.big').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('systematically the hard ones')
  })

  test('insufficient_data: no number is rendered', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: tankerCycleInsufficient } })

    expect(wrapper.classes()).toContain('ev-insufficient-data')
    expect(wrapper.find('.big').exists()).toBe(false)
    expect(wrapper.find('.withheld').exists()).toBe(false)
    expect(wrapper.text()).toContain('Not enough data')
  })

  test('insufficient_data: a progress bar toward min_n fills the space instead of leaving it blank', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: tankerCycleInsufficient } })

    // tankerCycleInsufficient: n 11, min_n 30 -> 37%
    const bar = wrapper.find('.wait-bar > i')
    expect(bar.exists()).toBe(true)
    expect(bar.attributes('style')).toContain('37%')
    expect(wrapper.find('.wait-progress-label').text()).toContain('37%')
  })

  test('insufficient_data: never renders an error tone class', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: tankerCycleInsufficient } })

    expect(wrapper.classes().join(' ')).not.toMatch(/error|danger|fail/i)
  })

  test('a blocking failed check suppresses the value entirely', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: hazardsWithheld } })

    expect(wrapper.classes()).toContain('ev-not-interpretable')
    expect(wrapper.find('.big').exists()).toBe(false)
    expect(wrapper.find('.withheld').exists()).toBe(true)
    expect(wrapper.text()).toContain('Schoenfeld')
  })

  test('a missing evidence prop is treated as insufficient data, never a crash', () => {
    const wrapper = mount(EvidenceValue, { props: { evidence: null } })

    expect(wrapper.classes()).toContain('ev-insufficient-data')
    expect(wrapper.find('.big').exists()).toBe(false)
  })
})
