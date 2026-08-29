import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import IssueCard from './IssueCard.vue'

const openIssue = {
  id: 1,
  title: 'Registration ID not received',
  meta: 'Music Collective · Event · Raised 2 days ago',
  status: 'open',
  statusLabel: 'Open',
  desc: 'I never received a confirmation email.',
  tags: ['Event', 'Registration'],
  response: null
}

const resolvedIssue = {
  ...openIssue,
  id: 2,
  status: 'resolved',
  statusLabel: 'Resolved',
  response: { by: 'Aayansh Yadav', text: 'Fixed and closed.' }
}

describe('IssueCard', () => {
  test('shows title, meta, description and tags', () => {
    const wrapper = mount(IssueCard, { props: { issue: openIssue } })

    expect(wrapper.find('.issue-title').text()).toBe('Registration ID not received')
    expect(wrapper.find('.issue-meta').text()).toContain('Music Collective')
    expect(wrapper.find('.issue-desc').text()).toContain('confirmation email')
    expect(wrapper.findAll('.announce-tag').length).toBe(2)
  })

  test('shows the status pill with the right class', () => {
    const wrapper = mount(IssueCard, { props: { issue: openIssue } })

    expect(wrapper.find('.status-pill').classes()).toContain('open')
    expect(wrapper.find('.status-pill').text()).toBe('Open')
  })

  test('hides the response block when there is no response', () => {
    const wrapper = mount(IssueCard, { props: { issue: openIssue } })

    expect(wrapper.find('.issue-response').exists()).toBe(false)
  })

  test('shows the leader response and resolved styling when resolved', () => {
    const wrapper = mount(IssueCard, { props: { issue: resolvedIssue } })

    expect(wrapper.find('.issue-card').classes()).toContain('resolved')
    expect(wrapper.find('.issue-response-label').text()).toContain('Aayansh Yadav')
    expect(wrapper.find('.issue-response-text').text()).toBe('Fixed and closed.')
  })
})
