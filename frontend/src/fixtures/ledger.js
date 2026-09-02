// ledger stream fixtures, per docs/DATA_SPINE.md §3. Money is signed minor
// units; receipts are frequently uncollected in the interview evidence, so
// that gap is a first-class figure, not a footnote.

export const ledgerSummary = {
  'vaikunth-heights': {
    duesOwed: {
      value: 18400000, n: 12, method: 'ledger.sum_exact', as_of: '2026-08-29T04:15:00Z',
      interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [],
      insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
      unit: '', params_hash: '', contract_version: 1
    },
    collectedThisCycle: {
      value: 51200000, n: 202, method: 'ledger.sum_exact', as_of: '2026-08-29T04:15:00Z',
      interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [],
      insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
      unit: '', params_hash: '', contract_version: 1
    },
    currency: 'INR',
    cycleLabel: 'August 2026 maintenance',
    verificationLag: {
      value: 1.8, n: 202, method: 'survival.median_resolution_days', as_of: '2026-08-29T04:15:00Z',
      interval: [1.2, 2.6], interval_kind: 'greenwood-95',
      assumptions: ['Verification lag is independent of payment size'], checks: [],
      caveats: [], insufficient_data: false, n_censored: 6, n_excluded: 0, exclusion_reason: '',
      unit: 'days', params_hash: 'a4e91c02', contract_version: 1
    },
    receiptGap: {
      value: 0.18, n: 202, method: 'proportion.wilson_interval', as_of: '2026-08-29T04:15:00Z',
      interval: [0.135, 0.234], interval_kind: 'normal-95',
      assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 0, n_excluded: 0,
      exclusion_reason: '', unit: 'probability', params_hash: 'd10bf774', contract_version: 1
    }
  },
  'aavartan-robotics': {
    duesOwed: {
      value: 420000, n: 7, method: 'ledger.sum_exact', as_of: '2026-08-29T04:15:00Z',
      interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [],
      insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
      unit: '', params_hash: '', contract_version: 1
    },
    collectedThisCycle: {
      value: 3860000, n: 84, method: 'ledger.sum_exact', as_of: '2026-08-29T04:15:00Z',
      interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [],
      insufficient_data: false, n_censored: 0, n_excluded: 0, exclusion_reason: '',
      unit: '', params_hash: '', contract_version: 1
    },
    currency: 'INR',
    cycleLabel: 'Semester membership fee',
    verificationLag: {
      value: 0.6, n: 84, method: 'survival.median_resolution_days', as_of: '2026-08-29T04:15:00Z',
      interval: [0.3, 1.1], interval_kind: 'greenwood-95',
      assumptions: [], checks: [], caveats: [], insufficient_data: false, n_censored: 1, n_excluded: 0,
      exclusion_reason: '', unit: 'days', params_hash: '2f7c8e19', contract_version: 1
    },
    receiptGap: {
      value: null, n: 8, method: 'proportion.wilson_interval', as_of: '2026-08-29T04:15:00Z',
      interval: null, interval_kind: 'none', assumptions: [], checks: [], caveats: [],
      insufficient_data: true, n_censored: 0, n_excluded: 0, exclusion_reason: '', unit: 'probability',
      params_hash: '', contract_version: 1, min_n: 30
    }
  }
}

export const ledgerEntries = {
  'vaikunth-heights': [
    { entry_ref: 'LE-9931', at: '2026-08-27T00:00:00Z', amount_minor: 850000, currency: 'INR', category: 'maintenance_dues', direction: 'inflow', member_ref: 'Meera Kulkarni · C-704', instrument: 'upi', status: 'settled', verified_at: '2026-08-28T10:00:00Z', receipt_issued_at: '2026-08-28T10:05:00Z', receipt_collected_at: null },
    { entry_ref: 'LE-9928', at: '2026-08-26T00:00:00Z', amount_minor: 850000, currency: 'INR', category: 'maintenance_dues', direction: 'inflow', member_ref: 'Suhas Patwardhan · D-201', instrument: 'bank_transfer', status: 'settled', verified_at: '2026-08-27T09:00:00Z', receipt_issued_at: '2026-08-27T09:10:00Z', receipt_collected_at: '2026-08-29T18:00:00Z' },
    { entry_ref: 'LE-9920', at: '2026-08-24T00:00:00Z', amount_minor: -620000, currency: 'INR', category: 'stp_maintenance', direction: 'outflow', counterparty_ref: 'Green STP Solutions', instrument: 'bank_transfer', status: 'settled', verified_at: '2026-08-24T00:00:00Z', receipt_issued_at: null, receipt_collected_at: null },
    { entry_ref: 'LE-9912', at: '2026-08-20T00:00:00Z', amount_minor: 850000, currency: 'INR', category: 'maintenance_dues', direction: 'inflow', member_ref: 'Vikram Iyer · A-12', instrument: 'cash', status: 'pending', verified_at: null, receipt_issued_at: null, receipt_collected_at: null },
    { entry_ref: 'LE-9905', at: '2026-08-15T00:00:00Z', amount_minor: -85000, currency: 'INR', category: 'penalty_late_fee', direction: 'outflow', member_ref: 'refund', counterparty_ref: null, instrument: 'adjustment', status: 'reversed', verified_at: '2026-08-16T00:00:00Z', receipt_issued_at: null, receipt_collected_at: null }
  ],
  'aavartan-robotics': [
    { entry_ref: 'LE-0442', at: '2026-08-25T00:00:00Z', amount_minor: 50000, currency: 'INR', category: 'membership_fee', direction: 'inflow', member_ref: 'Priya Nair', instrument: 'upi', status: 'settled', verified_at: '2026-08-25T12:00:00Z', receipt_issued_at: '2026-08-25T12:05:00Z', receipt_collected_at: '2026-08-25T12:06:00Z' },
    { entry_ref: 'LE-0439', at: '2026-08-22T00:00:00Z', amount_minor: -1800000, currency: 'INR', category: 'equipment_purchase', direction: 'outflow', counterparty_ref: 'RoboMart Supplies', instrument: 'bank_transfer', status: 'settled', verified_at: '2026-08-22T00:00:00Z', receipt_issued_at: null, receipt_collected_at: null },
    { entry_ref: 'LE-0431', at: '2026-08-15T00:00:00Z', amount_minor: 2500000, currency: 'INR', category: 'college_grant', direction: 'inflow', member_ref: null, counterparty_ref: 'Student Activity Council', instrument: 'bank_transfer', status: 'settled', verified_at: '2026-08-16T00:00:00Z', receipt_issued_at: '2026-08-16T00:00:00Z', receipt_collected_at: '2026-08-16T00:00:00Z' },
    { entry_ref: 'LE-0428', at: '2026-08-10T00:00:00Z', amount_minor: 50000, currency: 'INR', category: 'membership_fee', direction: 'inflow', member_ref: 'Karthik Menon', instrument: 'cash', status: 'expected', verified_at: null, receipt_issued_at: null, receipt_collected_at: null }
  ]
}

export function ledgerFor(slug) {
  return { summary: ledgerSummary[slug] || null, entries: ledgerEntries[slug] || [] }
}

export function formatMinor(minor, currency) {
  const value = minor / 100
  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })
  return `${sign}${currency === 'INR' ? '₹' : currency + ' '}${abs}`
}
