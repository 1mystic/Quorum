// request_flow stream fixtures, per docs/DATA_SPINE.md. Every open request
// carries its conformal ETA as a full Evidence envelope, never a bare number.

const etaGood = {
  value: { lower_days: 2.0, upper_days: 9.0, point_days: 4.5 },
  n: 143,
  method: 'conformal.mondrian_eta',
  as_of: '2026-08-29T04:15:00Z',
  interval: [2.0, 9.0],
  interval_kind: 'conformal-90',
  assumptions: ['Past intervals are exchangeable with this request'],
  checks: [
    {
      id: 'coverage-backtest',
      label: 'Past intervals contained the true time 91% of the time',
      status: 'PASS',
      statistic: 0.914,
      detail: '',
      blocking: false
    }
  ],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'days',
  params_hash: '7b2c0d41',
  contract_version: 1
}

const etaWaiting = {
  value: null,
  n: 9,
  method: 'conformal.mondrian_eta',
  as_of: '2026-08-29T04:15:00Z',
  interval: null,
  interval_kind: 'none',
  assumptions: [],
  checks: [],
  caveats: [],
  insufficient_data: true,
  n_censored: 4,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'days',
  params_hash: '',
  contract_version: 1,
  min_n: 30
}

export const requests = {
  'vaikunth-heights': [
    {
      ref: 'RQ-2214', title: 'Leaking tap in kitchen', category: 'water_supply', priority: 'urgent',
      status: 'in_progress', location: 'C-704', raised_by: 'Meera Kulkarni', assignee: 'Ravindra (plumber)',
      opened_at: '2026-08-24T09:12:00Z', updated_at: '2026-08-28T14:02:00Z',
      channel: 'whatsapp', description: 'Kitchen sink tap has been dripping continuously since Sunday morning, water pooling under the cabinet.',
      near_duplicates: [{ ref: 'RQ-2209', title: 'Low water pressure, C block', similarity: 0.61 }],
      eta: etaGood,
      timeline: [
        { at: '2026-08-24T09:12:00Z', label: 'Raised', detail: 'Submitted via WhatsApp bridge' },
        { at: '2026-08-24T11:40:00Z', label: 'Assigned', detail: 'Assigned to Ravindra, plumbing vendor' },
        { at: '2026-08-25T08:00:00Z', label: 'In progress', detail: 'Vendor visited, part on order' },
        { at: '2026-08-28T14:02:00Z', label: 'Update', detail: 'Part arrived, revisit scheduled' }
      ]
    },
    {
      ref: 'RQ-2231', title: 'STP odour near block D', category: 'sewage_stp', priority: 'safety',
      status: 'open', location: 'Block D', raised_by: 'Suhas Patwardhan', assignee: '',
      opened_at: '2026-08-27T07:30:00Z', updated_at: '2026-08-27T07:30:00Z',
      channel: 'app', description: 'Strong sewage odour near the D block STP outlet since this morning, several residents reporting.',
      near_duplicates: [],
      eta: etaWaiting,
      timeline: [{ at: '2026-08-27T07:30:00Z', label: 'Raised', detail: 'Submitted via app' }]
    },
    {
      ref: 'RQ-2198', title: 'Lift 2 stuck between floors', category: 'lift', priority: 'safety',
      status: 'escalated', location: 'B wing', raised_by: 'Front desk', assignee: 'Committee (escalated)',
      opened_at: '2026-08-19T18:05:00Z', updated_at: '2026-08-26T10:00:00Z',
      channel: 'phone', description: 'Lift 2 stopped between 4th and 5th floor for 20 minutes, AMC vendor unresponsive after two calls.',
      near_duplicates: [],
      eta: etaWaiting,
      timeline: [
        { at: '2026-08-19T18:05:00Z', label: 'Raised', detail: 'Reported by front desk security' },
        { at: '2026-08-20T09:00:00Z', label: 'Assigned', detail: 'AMC vendor notified' },
        { at: '2026-08-26T10:00:00Z', label: 'Escalated', detail: 'No AMC response after two follow-ups; escalated to committee' }
      ]
    },
    {
      ref: 'RQ-2107', title: 'Parking slot dispute, A-12', category: 'parking', priority: 'routine',
      status: 'resolved', location: 'A wing basement', raised_by: 'Vikram Iyer', assignee: 'Secretary',
      opened_at: '2026-08-02T10:00:00Z', updated_at: '2026-08-06T16:00:00Z', resolved_at: '2026-08-06T16:00:00Z',
      channel: 'app', description: 'Visitor car repeatedly parked in allotted resident slot A-12.',
      near_duplicates: [],
      eta: null,
      timeline: [
        { at: '2026-08-02T10:00:00Z', label: 'Raised', detail: '' },
        { at: '2026-08-03T09:00:00Z', label: 'Assigned', detail: 'Secretary to mediate' },
        { at: '2026-08-06T16:00:00Z', label: 'Resolved', detail: 'Slot markings repainted, notice circulated' }
      ]
    }
  ],
  'aavartan-robotics': [
    {
      ref: 'IS-0142', title: 'Venue booking clash for workshop', category: 'venue_booking', priority: 'deadline_bound',
      status: 'in_progress', location: 'Seminar Hall 2', raised_by: 'Ananya Rao', assignee: 'Logistics lead',
      opened_at: '2026-08-25T05:00:00Z', updated_at: '2026-08-28T09:00:00Z',
      channel: 'app', description: 'Booked slot for the ROS workshop overlaps with a departmental seminar, need alternate room by Friday.',
      near_duplicates: [],
      eta: etaGood,
      timeline: [
        { at: '2026-08-25T05:00:00Z', label: 'Raised', detail: '' },
        { at: '2026-08-26T10:00:00Z', label: 'Assigned', detail: 'Logistics lead looking into alternate slots' }
      ]
    },
    {
      ref: 'IS-0139', title: 'Funding request: regional competition travel', category: 'funding_request', priority: 'normal',
      status: 'open', location: '', raised_by: 'Karthik Menon', assignee: '',
      opened_at: '2026-08-26T12:00:00Z', updated_at: '2026-08-26T12:00:00Z',
      channel: 'app', description: 'Requesting travel funding for 6 members attending the regional robotics meet next month.',
      near_duplicates: [{ ref: 'IS-0111', title: 'Funding request: workshop kits', similarity: 0.44 }],
      eta: etaWaiting,
      timeline: [{ at: '2026-08-26T12:00:00Z', label: 'Raised', detail: '' }]
    },
    {
      ref: 'IS-0098', title: 'Equipment: soldering station not working', category: 'equipment', priority: 'normal',
      status: 'resolved', location: 'Club room', raised_by: 'Priya Nair', assignee: 'Core team',
      opened_at: '2026-08-05T06:00:00Z', updated_at: '2026-08-09T11:00:00Z', resolved_at: '2026-08-09T11:00:00Z',
      channel: 'app', description: 'Soldering iron in station 2 not heating up.',
      near_duplicates: [],
      eta: null,
      timeline: [
        { at: '2026-08-05T06:00:00Z', label: 'Raised', detail: '' },
        { at: '2026-08-06T08:00:00Z', label: 'Assigned', detail: 'Core team member to inspect' },
        { at: '2026-08-09T11:00:00Z', label: 'Resolved', detail: 'Heating element replaced' }
      ]
    }
  ]
}

export function requestsFor(slug) {
  return requests[slug] || []
}

export function requestByRef(slug, ref) {
  return requestsFor(slug).find((r) => r.ref === ref) || null
}

export const requestStatuses = ['open', 'in_progress', 'escalated', 'resolved', 'closed']
