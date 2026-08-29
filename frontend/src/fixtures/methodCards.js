// Local stand-in for GET /api/methods/{method_id} (docs/STATS_API.md §4).
// Not tenant-scoped: a Method Card is a property of the mathematics.

export const methodCards = {
  'survival.median_resolution_days': {
    id: 'survival.median_resolution_days', name: 'Median resolution days (Kaplan-Meier)',
    one_liner: 'How long half of requests take to resolve, with still-open requests counted as censored rather than dropped.',
    assumes: ['Censoring is independent of resolution speed', 'Requests entering the window are exchangeable'],
    wrong_when: ['Open requests are systematically the hard ones (informative censoring)', 'Fewer than 30 resolution events have occurred'],
    min_n: 30,
    interval_meaning: 'Greenwood 95%: the range in which the true population median plausibly falls, given sampling variability alone.',
    references: ['Kaplan, Meier (1958) JASA 53:457']
  },
  'conformal.mondrian_eta': {
    id: 'conformal.mondrian_eta', name: 'Conformalised survival ETA',
    one_liner: 'A distribution-free interval for one open request, calibrated so the true resolution time falls inside it a stated fraction of the time.',
    assumes: ['Past intervals are exchangeable with this request', 'The calibration set is refreshed on a stable cadence'],
    wrong_when: ['A category has fewer than the calibration minimum', 'The coverage backtest check fails'],
    min_n: 100,
    interval_meaning: 'Conformal 90%: across many requests like this one, 90% resolve inside the stated bound. Not a per-request probability.',
    references: ['Candes, Lei, Ren (2023) JRSS-B 85:24']
  },
  'queueing.littles_law': {
    id: 'queueing.littles_law', name: "Little's Law backlog wait",
    one_liner: 'Turns a visible queue length into an expected wait using the arrival rate, with no model fitting.',
    assumes: ['The system is in steady state over the measurement window'],
    wrong_when: ['Arrivals or service rates are changing quickly within the window'],
    min_n: 10,
    interval_meaning: 'Exact, not an estimate: L = λW is an identity given the two inputs.',
    references: ["Little (1961) Operations Research 9:383"]
  },
  'queueing.erlang_c': {
    id: 'queueing.erlang_c', name: 'Erlang-C staffing',
    one_liner: 'How many active resolvers are needed to close a target share of requests within a target time.',
    assumes: ['Poisson arrivals', 'Exponential service times', 'c interchangeable servers'],
    wrong_when: ['Service times are heavy-tailed rather than exponential', 'Resolvers are not interchangeable across categories'],
    min_n: 20,
    interval_meaning: 'None: the output is a staffing count at a stated service-level target, not a confidence interval.',
    references: ['Erlang (1917) Elektroteknikeren']
  },
  'survival.kaplan_meier': {
    id: 'survival.kaplan_meier', name: 'Kaplan-Meier survival curve',
    one_liner: 'The fraction of requests still unresolved at each elapsed day, with censoring handled correctly.',
    assumes: ['Censoring is independent of resolution speed'],
    wrong_when: ['Fewer than 30 resolution events have occurred'],
    min_n: 30,
    interval_meaning: 'Greenwood 95% pointwise band around the survival curve.',
    references: ['Kaplan, Meier (1958) JASA 53:457']
  },
  'spc.ewma': {
    id: 'spc.ewma', name: 'EWMA control chart',
    one_liner: 'Flags a small sustained shift in weekly request volume that a raw run chart would miss.',
    assumes: ['At least 20 periods of baseline', 'The baseline period itself is in control'],
    wrong_when: ['A known calendar effect (festival, exam break) has not been excluded from the baseline'],
    min_n: 20,
    interval_meaning: 'Control limits are a decision boundary tuned to a target average run length, not an estimate of anything.',
    references: ['Roberts (1959) Technometrics 1:239']
  },
  'survival.cox_ph': {
    id: 'survival.cox_ph', name: 'Cox proportional hazards',
    one_liner: 'Hazard ratios per covariate: how much faster or slower a category resolves relative to a baseline.',
    assumes: ['Hazards stay proportional over time'],
    wrong_when: ['The Schoenfeld residual test rejects proportionality (as here: p = 0.003)'],
    min_n: 10,
    interval_meaning: 'Profile likelihood 95% on the hazard ratio, when the proportionality check passes.',
    references: ['Cox (1972) JRSS-B 34:187']
  },
  'bayes.beta_binomial_shrinkage': {
    id: 'bayes.beta_binomial_shrinkage', name: 'Beta-binomial shrinkage ranking',
    one_liner: 'Ranks small-sample rates by posterior lower bound instead of raw rate, so a 3-of-3 vendor cannot outrank a 47-of-52 one.',
    assumes: ['Outcomes within a vendor are exchangeable', 'The prior is estimated from the pooled group'],
    wrong_when: ['Fewer than 5 groups exist to estimate the prior from'],
    min_n: 5,
    interval_meaning: 'Credible 95%: the posterior probability the true rate falls in this range, given the pooled prior and this vendor\'s record.',
    references: ['Efron, Morris (1975) JASA 70:311']
  },
  'forecast.dues_collection': {
    id: 'forecast.dues_collection', name: 'Seasonal dues collection forecast',
    one_liner: 'Projects next cycle\'s collection total with a prediction interval, backtested against a seasonal-naive baseline.',
    assumes: ['At least two full seasonal cycles of history', 'The seasonal pattern is stable'],
    wrong_when: ['MASE against seasonal-naive exceeds 1 (the model does not beat naive)'],
    min_n: 24,
    interval_meaning: 'Predictive 80%: the range the next observation is expected to fall in, not a confidence interval on a parameter.',
    references: ['Hyndman, Koehler (2006) IJF 22:679']
  },
  'conformal.eta_calibration': {
    id: 'conformal.eta_calibration', name: 'ETA interval coverage backtest',
    one_liner: 'Checks that the stated coverage rate for conformal ETAs is actually observed on resolved requests.',
    assumes: ['The backtest window is representative of current conditions'],
    wrong_when: ['Observed coverage drifts more than a few points from the target'],
    min_n: 50,
    interval_meaning: 'Normal 95% around the observed coverage rate.',
    references: ['Candes, Lei, Ren (2023) JRSS-B 85:24']
  },
  'segmentation.gmm_select_k': {
    id: 'segmentation.gmm_select_k', name: 'Engagement segmentation (Gaussian mixture)',
    one_liner: 'Finds naturally occurring engagement clusters, choosing the number of clusters by BIC rather than a fixed guess.',
    assumes: ['At least 50 members with sufficient activity history'],
    wrong_when: ['Cluster structure is indistinguishable from noise below the member floor'],
    min_n: 50,
    interval_meaning: 'None on cluster assignment itself; each cluster\'s size carries its own count.',
    references: ['Fraley, Raftery (2002) JASA 97:611']
  },
  'network.isolation_report': {
    id: 'network.isolation_report', name: 'Isolation report (aggregate only)',
    one_liner: 'Share of members with no or few interaction edges, reported by stratum, never as an individual list.',
    assumes: ['Interaction edges are observed at co-attendance, co-request or reply granularity'],
    wrong_when: ['A stratum cell falls below the k-anonymity floor (suppressed, not shown)'],
    min_n: 5,
    interval_meaning: 'Wilson 95% on the isolated share per stratum.',
    references: ['Freeman (1978) Social Networks 1:215']
  },
  'voting.schulze': {
    id: 'voting.schulze', name: 'Schulze method',
    one_liner: 'A Condorcet-consistent ranking from pairwise ballots; a cycle is disclosed rather than hidden behind the winner.',
    assumes: ['The declared rule was Schulze before ballots were cast'],
    wrong_when: ['A committee wants a different rule after seeing the result (the declared rule is binding)'],
    min_n: 1,
    interval_meaning: 'None: a tabulation of a closed ballot has exactly one correct answer.',
    references: ['Schulze (2011) Social Choice and Welfare 36:267']
  }
}

export function methodCard(id) {
  return methodCards[id] || null
}
