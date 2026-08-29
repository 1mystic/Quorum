import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EventCard from './EventCard.vue'

const sampleEvent = {
  id: 1,
  title: 'Line Follower Robot Build',
  club: 'Robotics & Automation Club',
  day: '12',
  month: 'Jul',
  time: '3:00 PM',
  venue: 'Main Lab',
  status: 'upcoming',
  accent: 'banner-orange',
  registered: 30,
  capacity: 50
}

describe('EventCard', () => {
  test('shows the event title, club and date box', () => {
    const wrapper = mount(EventCard, { props: { event: sampleEvent } })

    expect(wrapper.find('.event-card-title').text()).toBe('Line Follower Robot Build')
    expect(wrapper.find('.event-card-club').text()).toBe('Robotics & Automation Club')
    expect(wrapper.find('.event-date-day').text()).toBe('12')
    expect(wrapper.find('.event-date-month').text()).toBe('Jul')
  })

  test('applies the accent class and status class', () => {
    const wrapper = mount(EventCard, { props: { event: sampleEvent } })

    expect(wrapper.find('.event-card-accent').classes()).toContain('banner-orange')
    expect(wrapper.find('.event-status').classes()).toContain('upcoming')
    expect(wrapper.find('.event-status').text()).toBe('Upcoming')
  })

  test('shows the registered versus capacity count', () => {
    const wrapper = mount(EventCard, { props: { event: sampleEvent } })

    expect(wrapper.find('.club-card-members').text()).toContain('30 / 50')
  })

  test('emits open when the card is clicked', async () => {
    const wrapper = mount(EventCard, { props: { event: sampleEvent } })

    await wrapper.find('.event-card').trigger('click')

    expect(wrapper.emitted('open')).toBeTruthy()
  })
})
