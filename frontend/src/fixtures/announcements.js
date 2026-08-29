export const announcements = {
  'vaikunth-heights': [
    { id: 'an-1', title: 'Water tanker schedule this week', body: 'Tankers will supply blocks A-D on Tuesday and E-H on Thursday, 6-9am, due to ongoing borewell maintenance.', posted_by: 'Secretary', posted_at: '2026-08-28T06:00:00Z', pinned: true, category: 'maintenance' },
    { id: 'an-2', title: 'General body meeting, 6 September', body: 'Q3 general body meeting will cover the STP vendor renewal and the sinking-fund review. Agenda circulated separately.', posted_by: 'President', posted_at: '2026-08-26T08:00:00Z', pinned: true, category: 'governance' },
    { id: 'an-3', title: 'Festival contribution drive closed', body: 'Thank you to the 140 households who contributed. Collection and expense summary is on the events page.', posted_by: 'Treasurer', posted_at: '2026-08-16T09:00:00Z', pinned: false, category: 'finance' }
  ],
  'aavartan-robotics': [
    { id: 'an-11', title: 'ROS workshop registrations closing Friday', body: '58 of 60 seats filled. Register before Friday 5pm to secure a spot.', posted_by: 'Core team', posted_at: '2026-08-27T07:00:00Z', pinned: true, category: 'event' },
    { id: 'an-12', title: 'Committee election nominations open', body: 'Nominations for the 5-seat core committee are open until 10 September. STV counting per the club constitution.', posted_by: 'Faculty advisor', posted_at: '2026-08-24T05:00:00Z', pinned: true, category: 'governance' },
    { id: 'an-13', title: 'Equipment inventory audit results', body: 'Two soldering stations repaired, one 3D printer nozzle replaced. Full list on the knowledge base.', posted_by: 'Core team', posted_at: '2026-08-11T04:00:00Z', pinned: false, category: 'ops' }
  ]
}

export function announcementsFor(slug) {
  return announcements[slug] || []
}
