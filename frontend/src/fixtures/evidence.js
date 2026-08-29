// Local fixture data shaped exactly like docs/EVIDENCE_CONTRACT.md §5's wire
// format. The backend API does not exist yet; this is what drives the
// dashboard until it does.

export const medianResolution = {
  value: 4.3,
  n: 187,
  method: 'survival.median_resolution_days',
  as_of: '2026-08-29T04:15:00Z',
  interval: [3.4, 5.6],
  interval_kind: 'greenwood-95',
  assumptions: ['Censoring is independent of resolution speed'],
  checks: [
    {
      id: 'censoring-informative',
      label: 'Open requests are not systematically the hard ones',
      status: 'WARN',
      statistic: 0.31,
      p_value: 0.04,
      detail: 'Requests open past 30 days skew to the plumbing category. The median may be optimistic.',
      blocking: false
    }
  ],
  caveats: [],
  insufficient_data: false,
  n_censored: 44,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'days',
  params_hash: 'e3f1a9c2',
  contract_version: 1
}

export const conformalEta = {
  value: 5.5,
  n: 143,
  method: 'conformal.split_eta',
  as_of: '2026-08-29T04:15:00Z',
  interval: [2, 9],
  interval_kind: 'conformal-90',
  assumptions: [],
  checks: [],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'days',
  params_hash: '7b2c0d41',
  contract_version: 1
}

export const openRightNow = {
  value: 44,
  n: 44,
  method: 'queueing.littles_law',
  as_of: '2026-08-29T04:15:00Z',
  interval: null,
  interval_kind: 'none',
  assumptions: [],
  checks: [],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: '',
  params_hash: '4d90ba17',
  contract_version: 1
}

export const tankerCycleInsufficient = {
  value: null,
  n: 11,
  method: 'survival.kaplan_meier',
  as_of: '2026-08-29T04:15:00Z',
  interval: null,
  interval_kind: 'none',
  assumptions: [],
  checks: [],
  caveats: [],
  insufficient_data: true,
  n_censored: 7,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'days',
  params_hash: '',
  contract_version: 1,
  min_n: 30
}

export const hazardsWithheld = {
  value: null,
  n: 187,
  method: 'survival.cox_ph',
  as_of: '2026-08-29T04:15:00Z',
  interval: null,
  interval_kind: 'none',
  assumptions: ['Hazards stay proportional over time'],
  checks: [
    {
      id: 'proportional-hazards',
      label: 'Hazards stay proportional over time',
      status: 'FAIL',
      statistic: null,
      p_value: 0.003,
      detail: 'Schoenfeld residual test: global p = 0.003, wing D alone p < 0.001. Stratify by wing or fit a time-varying coefficient.',
      blocking: true
    }
  ],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: '',
  params_hash: '',
  contract_version: 1
}

export const kaplanMeierCurve = {
  value: {
    x: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    y: [1, 0.95, 0.86, 0.71, 0.53, 0.43, 0.36, 0.3, 0.26, 0.23, 0.2, 0.18, 0.16, 0.15, 0.14],
    lo: [1, 0.89, 0.76, 0.6, 0.35, 0.28, 0.23, 0.19, 0.16, 0.13, 0.11, 0.1, 0.09, 0.08, 0.07],
    hi: [1, 0.99, 0.94, 0.82, 0.68, 0.56, 0.46, 0.4, 0.36, 0.33, 0.3, 0.28, 0.26, 0.25, 0.24],
    censor_x: [2.4, 5.6, 8.3, 10.9, 12.6]
  },
  n: 187,
  method: 'survival.kaplan_meier',
  as_of: '2026-08-29T04:15:00Z',
  interval: null,
  interval_kind: 'greenwood-95',
  assumptions: ['Censoring is independent of resolution speed'],
  checks: [],
  caveats: [],
  insufficient_data: false,
  n_censored: 44,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'days',
  params_hash: 'e3f1a9c2',
  contract_version: 1
}

export const ewmaChart = {
  value: {
    points: [
      { x: 0, y: 17.8 }, { x: 1, y: 18.4 }, { x: 2, y: 17.9 }, { x: 3, y: 18.8 },
      { x: 4, y: 19.2 }, { x: 5, y: 18.6 }, { x: 6, y: 17.4 }, { x: 7, y: 16.9 },
      { x: 8, y: 17.6 }, { x: 9, y: 18.3 }, { x: 10, y: 19.1 }, { x: 11, y: 20.2 },
      { x: 12, y: 21.0 }, { x: 13, y: 21.8 }, { x: 14, y: 22.6 }, { x: 15, y: 24.1, label: 'wk 16 · 24.1' },
      { x: 16, y: 23.2 }, { x: 17, y: 22.0 }, { x: 18, y: 20.8 }, { x: 19, y: 19.6 }
    ],
    center: 18.0,
    ucl: 23.4,
    lcl: 12.6,
    signals: [15]
  },
  n: 20,
  method: 'spc.ewma',
  as_of: '2026-08-29T04:15:00Z',
  interval: null,
  interval_kind: 'control-limits',
  assumptions: [],
  checks: [],
  caveats: [],
  insufficient_data: false,
  n_censored: 0,
  n_excluded: 0,
  exclusion_reason: '',
  unit: 'requests/week',
  params_hash: '9a4c2e88',
  contract_version: 1
}
