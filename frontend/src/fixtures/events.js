// participation stream fixtures, per docs/DATA_SPINE.md. Events feed RSVP,
// attendance and the no-show rate; fund summaries pull from the ledger's
// campaign_ref, kept as plain totals here (not an Evidence statistic on
// their own, unlike the attendance forecast on the event detail page).

export const events = {
  'vaikunth-heights': [
    {
      id: 'ev-1', title: 'General body meeting, Q3', kind: 'attend', starts_at: '2026-09-06T11:00:00Z',
      location: 'Clubhouse hall', rsvp: 96, attended: null, capacity: 150, status: 'upcoming',
      fund: { collected_minor: 0, spent_minor: 0, currency: 'INR' }
    },
    {
      id: 'ev-2', title: 'Ganesh Utsav contribution drive', kind: 'rsvp', starts_at: '2026-08-15T05:00:00Z',
      location: 'Society ground', rsvp: 140, attended: 132, capacity: 200, status: 'closed',
      fund: { collected_minor: 18600000, spent_minor: 15200000, currency: 'INR' }
    },
    {
      id: 'ev-3', title: 'Monsoon fire-safety drill', kind: 'attend', starts_at: '2026-07-12T04:30:00Z',
      location: 'All wings', rsvp: 210, attended: 178, capacity: 214, status: 'closed',
      fund: { collected_minor: 0, spent_minor: 45000, currency: 'INR' }
    }
  ],
  'aavartan-robotics': [
    {
      id: 'ev-11', title: 'ROS workshop', kind: 'rsvp', starts_at: '2026-09-02T09:00:00Z',
      location: 'Seminar Hall 2', rsvp: 58, attended: null, capacity: 60, status: 'upcoming',
      fund: { collected_minor: 0, spent_minor: 320000, currency: 'INR' }
    },
    {
      id: 'ev-12', title: 'Regional robotics meet: send-off', kind: 'attend', starts_at: '2026-08-20T06:00:00Z',
      location: 'Club room', rsvp: 24, attended: 22, capacity: 30, status: 'closed',
      fund: { collected_minor: 0, spent_minor: 180000, currency: 'INR' }
    },
    {
      id: 'ev-13', title: 'Freshers induction', kind: 'attend', starts_at: '2026-08-03T05:00:00Z',
      location: 'Auditorium', rsvp: 140, attended: 96, capacity: 150, status: 'closed',
      fund: { collected_minor: 0, spent_minor: 60000, currency: 'INR' }
    }
  ]
}

export function eventsFor(slug) {
  return events[slug] || []
}

export function eventById(slug, id) {
  return eventsFor(slug).find((e) => e.id === id) || null
}
