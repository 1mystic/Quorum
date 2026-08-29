// Pack-level fixtures for the four Insight views, shaped per
// docs/EVIDENCE_CONTRACT.md §4-5 and docs/STATS_CATALOG.md. Reuses the
// dashboard's original envelopes for vaikunth-heights (fixtures/evidence.js)
// and adds a parallel set for aavartan-robotics plus Packs 2-4 for both.

import {
  medianResolution,
  conformalEta,
  openRightNow,
  tankerCycleInsufficient,
  hazardsWithheld,
  kaplanMeierCurve,
  ewmaChart
} from './evidence'

const erlangStaffingVH = {
  value: 4, n: 187, method: 'queueing.erlang_c', as_of: '2026-08-29T04:15:00Z',
  interval: null, interval_kind: 'none', assumptions: ['Poisson arrivals', 'Exponential service times'],
  checks: [], caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
  unit: 'resolvers · have 2', params_hash: 'c1e7f430', contract_version: 1
}

const medianResolutionCC = {
  value: 3.1, n: 230, method: 'survival.median_resolution_days', as_of: '2026-08-29T02:00:00Z',
  interval: [2.6, 3.7], interval_kind: 'greenwood-95', assumptions: ['Censoring is independent of resolution speed'],
  checks: [], caveats: [], insufficient_data: false, n_censored: 30, n_excluded: 0, exclusion_reason: '',
  unit: 'days', params_hash: 'f9d2a801', contract_version: 1
}

const openRightNowCC = {
  value: 30, n: 30, method: 'queueing.littles_law', as_of: '2026-08-29T02:00:00Z',
  interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [], insufficient_data: false,
  n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: '', params_hash: '6e1f0a2c', contract_version: 1
}

const conformalEtaCC = {
  value: 3.5, n: 118, method: 'conformal.mondrian_eta', as_of: '2026-08-29T02:00:00Z',
  interval: [1, 6], interval_kind: 'conformal-90', assumptions: [], checks: [], caveats: [],
  insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'days',
  params_hash: '3a8bd001', contract_version: 1
}

const kmCurveCC = {
  value: {
    x: [0, 1, 2, 3, 4, 5, 6, 7, 8],
    y: [1, 0.9, 0.74, 0.55, 0.4, 0.3, 0.22, 0.18, 0.15],
    lo: [1, 0.83, 0.64, 0.44, 0.29, 0.2, 0.13, 0.1, 0.08],
    hi: [1, 0.96, 0.84, 0.66, 0.51, 0.4, 0.31, 0.26, 0.22],
    censor_x: [1.8, 3.2, 5.5, 6.9]
  },
  n: 230, method: 'survival.kaplan_meier', as_of: '2026-08-29T02:00:00Z', interval: null,
  interval_kind: 'greenwood-95', assumptions: ['Censoring is independent of resolution speed'], checks: [],
  caveats: [], insufficient_data: false, n_censored: 30, n_excluded: 0, exclusion_reason: '',
  unit: 'days', params_hash: 'f9d2a801', contract_version: 1
}

const ewmaCC = {
  value: {
    points: [
      { x: 0, y: 9.1 }, { x: 1, y: 8.8 }, { x: 2, y: 9.4 }, { x: 3, y: 8.6 }, { x: 4, y: 7.9 },
      { x: 5, y: 8.2 }, { x: 6, y: 9.0 }, { x: 7, y: 10.1 }, { x: 8, y: 11.4, label: 'wk 9 · 11.4' },
      { x: 9, y: 10.6 }, { x: 10, y: 9.8 }, { x: 11, y: 9.2 }
    ],
    center: 9.2, ucl: 11.2, lcl: 7.2, signals: [8]
  },
  n: 12, method: 'spc.ewma', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'control-limits',
  assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0,
  exclusion_reason: '', unit: 'issues/week', params_hash: '1b7ce900', contract_version: 1
}

export const operationsPack = {
  'vaikunth-heights': {
    tiles: [
      { title: 'Median time to resolution', subtitle: 'all categories', evidence: medianResolution, why: 'Requests still open past 30 days skew towards plumbing (censoring test p = 0.04). The median may be optimistic.' },
      { title: 'ETA · RQ-2214', subtitle: 'leaking tap, C-704', evidence: conformalEta, display: 'range', why: 'A conformal interval guarantees marginal coverage: across many requests like this one, 90% resolve inside it.' },
      { title: 'Open right now', subtitle: 'unresolved, all wings', evidence: openRightNow },
      { title: 'Resolvers needed', subtitle: 'for 90% closed in 5 days', evidence: erlangStaffingVH, why: 'At the current arrival and service rate, two active resolvers reach the 5-day target 61% of the time. Four reach it 90%.' }
    ],
    survival: { title: 'Requests still unresolved, by day', subtitle: 'kaplan-meier · greenwood 95% band', evidence: kaplanMeierCurve },
    controlChart: { title: 'Weekly request rate', subtitle: 'ewma control chart', evidence: ewmaChart },
    insufficientTile: { title: 'Water-tanker call-out cycle', subtitle: 'kaplan-meier · tanker category', evidence: tankerCycleInsufficient, why: 'A curve over 11 observations is a staircase of single events, not an estimate. This is the minimum-n policy doing exactly what it is for.' },
    withheldTile: { title: 'Resolution speed by wing', subtitle: 'cox proportional hazards', evidence: hazardsWithheld, why: 'Wing D was slow for six weeks after its pump replacement and ordinary afterwards. A single hazard ratio would average two regimes into one number that reads as decisive and is not.' }
  },
  'aavartan-robotics': {
    tiles: [
      { title: 'Median time to resolution', subtitle: 'all categories', evidence: medianResolutionCC, why: 'Venue booking and funding requests resolve slower than equipment issues; the club has not yet enabled Cox regression to split them out.' },
      { title: 'ETA · IS-0142', subtitle: 'venue booking clash', evidence: conformalEtaCC, display: 'range' },
      { title: 'Open right now', subtitle: 'unresolved, all categories', evidence: openRightNowCC },
      { title: 'First response', subtitle: 'time to first assignment', evidence: { value: 0.8, n: 230, method: 'survival.median_resolution_days', as_of: '2026-08-29T02:00:00Z', interval: [0.5, 1.2], interval_kind: 'greenwood-95', assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 5, n_excluded: 0, exclusion_reason: '', unit: 'days', params_hash: '77c1a0f2', contract_version: 1 } }
    ],
    survival: { title: 'Issues still unresolved, by day', subtitle: 'kaplan-meier · greenwood 95% band', evidence: kmCurveCC },
    controlChart: { title: 'Weekly issue rate', subtitle: 'ewma control chart · exam-break periods excluded from baseline', evidence: ewmaCC },
    insufficientTile: {
      title: 'Grievance category resolution', subtitle: 'kaplan-meier · grievance category',
      evidence: { value: null, n: 6, method: 'survival.kaplan_meier', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [], insufficient_data: true, n_censored: 2, n_excluded: 0, exclusion_reason: '', unit: 'days', params_hash: '', contract_version: 1, min_n: 30 },
      why: 'Grievances are rare by design. The platform will not draw a curve over 6 observations.'
    },
    withheldTile: {
      title: 'Resolution speed by department', subtitle: 'cox proportional hazards',
      evidence: { value: null, n: 230, method: 'survival.cox_ph', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'none', assumptions: ['Hazards stay proportional over time'], checks: [{ id: 'proportional-hazards', label: 'Hazards stay proportional over time', status: 'FAIL', p_value: 0.011, detail: 'Schoenfeld residual test: p = 0.011, driven by a term-break gap in the electronics department series. Stratify by term or exclude the break window.', blocking: true }], caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: '', params_hash: '', contract_version: 1 },
      why: 'The term-break gap in this vertical\'s calendar (docs/VERTICALS.md campus_club spc.* override) violates proportionality until it is excluded from the fit.'
    }
  }
}

export const forecastPack = {
  'vaikunth-heights': {
    forecast: {
      title: 'September dues collection', subtitle: 'seasonal-naive backtested · season length 12 (monthly)',
      evidence: {
        value: { history: [78, 81, 76, 88, 92, 85, 79, 83, 90, 94, 87, 91], forecast: [93], lo: [86], hi: [100] },
        n: 26, method: 'forecast.dues_collection', as_of: '2026-08-31T21:00:00Z', interval: [86, 100],
        interval_kind: 'predictive-80', assumptions: ['At least two full seasonal cycles of history', 'The seasonal pattern is stable'],
        checks: [{ id: 'mase-beats-naive', label: 'Beats the seasonal-naive baseline', status: 'PASS', statistic: 0.71, detail: 'MASE 0.71 against seasonal-naive over 12 backtested cycles.', blocking: false }],
        caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'lakh INR', params_hash: '8e21c4a0', contract_version: 1
      }
    },
    calibration: {
      title: 'ETA interval coverage', subtitle: 'backtest on resolved requests, last 90 days',
      evidence: {
        value: 0.914, n: 412, method: 'conformal.eta_calibration', as_of: '2026-08-29T02:00:00Z', interval: [0.887, 0.937],
        interval_kind: 'normal-95', assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 0,
        n_excluded: 0, exclusion_reason: '', unit: 'probability', params_hash: 'a71c33e0', contract_version: 1
      },
      why: 'Target coverage is 90%. Observed 91.4% is within sampling noise of the target, so the calibration holds.'
    },
    etaDistribution: {
      title: 'Open request ETA distribution', subtitle: 'conformal 90% intervals, current backlog',
      evidence: {
        value: { buckets: [{ label: '0-2d', n: 6 }, { label: '2-4d', n: 14 }, { label: '4-6d', n: 12 }, { label: '6-9d', n: 9 }, { label: '9d+', n: 3 }] },
        n: 44, method: 'conformal.mondrian_eta', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
        unit: 'requests', params_hash: '7b2c0d41', contract_version: 1
      }
    }
  },
  'aavartan-robotics': {
    forecast: {
      title: 'Next semester attendance', subtitle: 'seasonal-naive backtested · season length 2 (per academic year)',
      evidence: {
        value: { history: [58, 62, 55, 60, 64, 59], forecast: [61], lo: [52], hi: [70] },
        n: 6, method: 'forecast.attendance', as_of: '2026-08-31T21:00:00Z', interval: [52, 70], interval_kind: 'predictive-80',
        assumptions: ['At least two full seasonal cycles of history'], checks: [{ id: 'mase-beats-naive', label: 'Beats the seasonal-naive baseline', status: 'WARN', statistic: 1.04, detail: 'MASE 1.04: this forecast is not clearly better than assuming the same as last semester. Clubs consistently over-forecast turnout; treat this figure with care.', blocking: false }],
        caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'attendees', params_hash: 'c40b91aa', contract_version: 1
      }
    },
    calibration: {
      title: 'ETA interval coverage', subtitle: 'backtest on resolved issues, last semester',
      evidence: {
        value: null, n: 42, method: 'conformal.eta_calibration', as_of: '2026-08-29T02:00:00Z', interval: null,
        interval_kind: 'none', assumptions: [], checks: [], caveats: [], insufficient_data: true, n_censored: 0,
        n_excluded: 0, exclusion_reason: '', unit: 'probability', params_hash: '', contract_version: 1, min_n: 50
      },
      why: 'The backtest needs 50 resolved issues with a matured ETA interval; the club has 42 so far this semester.'
    },
    etaDistribution: {
      title: 'Open issue ETA distribution', subtitle: 'conformal 90% intervals, current backlog',
      evidence: {
        value: { buckets: [{ label: '0-1d', n: 4 }, { label: '1-3d', n: 11 }, { label: '3-6d', n: 9 }, { label: '6d+', n: 6 }] },
        n: 30, method: 'conformal.mondrian_eta', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
        unit: 'issues', params_hash: '3a8bd001', contract_version: 1
      }
    }
  }
}

export const governancePack = {
  'vaikunth-heights': {
    segmentation: {
      title: 'Involvement segments', subtitle: 'gaussian mixture · k chosen by BIC',
      evidence: {
        value: { clusters: [{ label: 'Highly engaged', n: 38, share: 0.18 }, { label: 'Occasional', n: 96, share: 0.45 }, { label: 'Drifting away', n: 52, share: 0.24 }, { label: 'Dormant', n: 28, share: 0.13 }] },
        n: 214, method: 'segmentation.gmm_select_k', as_of: '2026-08-24T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: ['At least 50 members with sufficient activity history'], checks: [], caveats: [], insufficient_data: false,
        n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'residents', params_hash: 'd3e8a1c5', contract_version: 1
      }
    },
    isolation: {
      title: 'Isolation report', subtitle: 'share with few interaction edges, by block',
      evidence: {
        value: { rows: [{ stratum: 'Block A', share: 0.11, n: 24 }, { stratum: 'Block B', share: 0.19, n: 22 }, { stratum: 'Block C', share: null, n: 4, suppressed: true }, { stratum: 'Block D', share: 0.24, n: 26 }] },
        n: 214, method: 'network.isolation_report', as_of: '2026-08-24T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: [], checks: [], caveats: ['Block C suppressed below the k = 5 anonymity floor'], insufficient_data: false,
        n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'probability', params_hash: 'f1a09b3c', contract_version: 1
      },
      privacyNote: 'rwa_society disables network.betweenness_centrality (docs/VERTICALS.md): naming informal power brokers in a society with active committee friction is a foreseeable harm. Isolation stays because it is aggregate-only and can never return an individual list.'
    }
  },
  'aavartan-robotics': {
    segmentation: {
      title: 'Engagement segments', subtitle: 'gaussian mixture · k chosen by BIC',
      evidence: {
        value: { clusters: [{ label: 'Core', n: 22, share: 0.12 }, { label: 'Active', n: 68, share: 0.38 }, { label: 'General, engaged', n: 54, share: 0.3 }, { label: 'Drifting away', n: 36, share: 0.2 }] },
        n: 180, method: 'segmentation.gmm_select_k', as_of: '2026-08-24T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: ['At least 50 members with sufficient activity history'], checks: [], caveats: [], insufficient_data: false,
        n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'members', params_hash: 'b6c2f10a', contract_version: 1
      }
    },
    isolation: {
      title: 'Isolation report', subtitle: 'share with few interaction edges, by year',
      evidence: {
        value: { rows: [{ stratum: 'Year 1', share: 0.31, n: 46 }, { stratum: 'Year 2', share: 0.14, n: 44 }, { stratum: 'Year 3', share: 0.09, n: 42 }, { stratum: 'Year 4', share: 0.07, n: 38 }, { stratum: 'PG', share: null, n: 3, suppressed: true }] },
        n: 180, method: 'network.isolation_report', as_of: '2026-08-24T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: [], checks: [], caveats: ['PG cell suppressed below the k = 5 anonymity floor'], insufficient_data: false,
        n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'probability', params_hash: 'ae02c711', contract_version: 1
      },
      privacyNote: 'First-years show the highest isolation share, which answers the real question a club president has: are they integrating? The service cannot and will not name which first-years.'
    }
  }
}

export const comparisonPack = {
  'vaikunth-heights': {
    leaderboard: {
      title: 'Vendor resolution rate', subtitle: 'empirical-bayes shrunk · ranked by posterior lower bound, not raw rate',
      evidence: {
        value: {
          rows: [
            { name: 'Shreeya Plumbing Works', closed: 47, total: 52, raw: 0.904, shrunk: 0.881, interval: [0.792, 0.940], n: 52 },
            { name: 'Sai Electricals', closed: 32, total: 38, raw: 0.842, shrunk: 0.824, interval: [0.710, 0.906], n: 38 },
            { name: 'Pune Civil Co.', closed: 30, total: 39, raw: 0.769, shrunk: 0.761, interval: [0.634, 0.861], n: 39 },
            { name: 'Nashik Elevator Services', closed: 3, total: 3, raw: 1.0, shrunk: 0.798, interval: [0.551, 0.952], n: 3, flag: '3 of 3' },
            { name: 'Green STP Solutions', closed: 16, total: 26, raw: 0.615, shrunk: 0.639, interval: [0.478, 0.782], n: 26 }
          ]
        },
        n: 158, method: 'bayes.beta_binomial_shrinkage', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: ['Outcomes within a vendor are exchangeable'], checks: [], caveats: [], insufficient_data: false,
        n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'probability', params_hash: 'b7e21c05', contract_version: 1
      },
      why: 'Nashik Elevator Services resolved 3 of 3, a perfect record and almost no evidence: its posterior runs from 55% to 95%, lower bound 55.1%. Shreeya Plumbing resolved 47 of 52, a lower point estimate but a far narrower posterior, lower bound 79.2%, so it ranks first. Ranking by raw rate would put a three-job vendor above a fifty-job one.'
    }
  },
  'aavartan-robotics': {
    leaderboard: {
      title: 'Event vendor reliability', subtitle: 'empirical-bayes shrunk · catering, printing and AV vendors pooled within trade',
      evidence: {
        value: {
          rows: [
            { name: 'Campus Print Co.', closed: 18, total: 19, raw: 0.947, shrunk: 0.868, interval: [0.71, 0.95], n: 19 },
            { name: 'Deccan Catering', closed: 22, total: 27, raw: 0.815, shrunk: 0.802, interval: [0.66, 0.90], n: 27 },
            { name: 'Sound & Light Crew', closed: 2, total: 2, raw: 1.0, shrunk: 0.71, interval: [0.42, 0.92], n: 2, flag: '2 of 2' },
            { name: 'QuickTents Rentals', closed: 9, total: 15, raw: 0.6, shrunk: 0.629, interval: [0.41, 0.81], n: 15 }
          ]
        },
        n: 63, method: 'bayes.beta_binomial_shrinkage', as_of: '2026-08-29T02:00:00Z', interval: null, interval_kind: 'none',
        assumptions: ['Outcomes within a vendor are exchangeable'], checks: [], caveats: [], insufficient_data: false,
        n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'probability', params_hash: '4f10ac82', contract_version: 1
      },
      why: 'Sound & Light Crew is 2 for 2, which is almost no evidence: its posterior lower bound is 42%, well below its raw rate. Campus Print Co. has done nearly ten times as many jobs at a similar raw rate and ranks first on the lower bound.'
    }
  }
}
