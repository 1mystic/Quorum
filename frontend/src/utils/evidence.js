// Shared logic for reading an Evidence envelope (docs/EVIDENCE_CONTRACT.md).
// Every function here is pure and takes the envelope whole - no component
// may unwrap, round or derive a new figure from one on its own.

export const RENDER_STATES = {
  ESTIMATE: 'estimate',
  QUALIFIED: 'qualified',
  NOT_INTERPRETABLE: 'not-interpretable',
  INSUFFICIENT_DATA: 'insufficient-data'
}

/**
 * The blocking check, if any. Its presence is what moves an Evidence from
 * "qualified" to "not interpretable" - the value must be suppressed.
 */
export function blockingCheck(evidence) {
  if (!evidence || !evidence.checks) return null
  return evidence.checks.find((check) => check.blocking && check.status === 'FAIL') || null
}

/**
 * Every check worth surfacing inline: a non-blocking FAIL, or any WARN.
 */
export function qualifyingChecks(evidence) {
  if (!evidence || !evidence.checks) return []
  return evidence.checks.filter((check) => {
    if (check.status === 'WARN') return true
    return check.status === 'FAIL' && !check.blocking
  })
}

/**
 * Decides which of the four render states in contract §3 applies. This is
 * decided by the data, never by the component that calls it.
 */
export function renderState(evidence) {
  if (!evidence) return RENDER_STATES.INSUFFICIENT_DATA
  if (evidence.insufficient_data) return RENDER_STATES.INSUFFICIENT_DATA
  if (blockingCheck(evidence)) return RENDER_STATES.NOT_INTERPRETABLE
  if (qualifyingChecks(evidence).length > 0) return RENDER_STATES.QUALIFIED
  return RENDER_STATES.ESTIMATE
}

const INTERVAL_LABELS = {
  none: '',
  'normal-95': 'CI 95',
  'bootstrap-bca-95': 'bootstrap 95',
  'greenwood-95': 'greenwood 95',
  'profile-95': 'profile 95',
  'credible-95': 'credible 95',
  'credible-89': 'credible 89',
  'conformal-90': 'conformal 90',
  'conformal-95': 'conformal 95',
  'predictive-80': 'predictive 80',
  'predictive-95': 'predictive 95',
  'control-limits': 'control limits'
}

export function intervalLabel(intervalKind) {
  return INTERVAL_LABELS[intervalKind] || intervalKind || ''
}

export function formatInterval(evidence) {
  if (!evidence || !evidence.interval) return ''
  const [lo, hi] = evidence.interval
  return `${lo}–${hi}`
}

export function methodCardHref(method) {
  if (!method) return '#'
  return `/methods/${method}`
}
