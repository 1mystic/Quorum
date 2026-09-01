# The statistics catalog

*Cards A.3 to A.6. Depends on `docs/EVIDENCE_CONTRACT.md` and `docs/DATA_SPINE.md`.*

Four Insight Packs. Every service below is a pure function in `backend/app/stats/`, takes stream
units defined in `docs/DATA_SPINE.md`, and returns an `Evidence` envelope. None of them touches a
database, a network socket, or a clock.

## How to read a service entry

| Field | Meaning |
|---|---|
| **id** | `module.function`. The `Evidence.method` value and the Method Card key. |
| **streams** | Which stream units it consumes. If the unit is absent, the service raises `InsufficientData`. |
| **input** | The call signature, in outline. Every tuning parameter is explicit and enters `params_hash`. |
| **output** | One of the four `value` shapes in the Evidence contract §4, with its `unit` and `interval_kind`. |
| **min_n** | The floor, and the reason that number and not another. Below it: `insufficient_data=True`. |
| **assumptions** | Prose claims, carried in `Evidence.assumptions`. |
| **checks** | Automatic tests the service runs on its own output, carried in `Evidence.checks`. `blocking=True` means the value is suppressed by the UI. |
| **on failure** | What the service actually does when a check fails. |
| **method card** | `assumes` / `wrong_when` / `interval_meaning` / `references`. |
| **known answer** | The external ground truth its test asserts against. **Where none exists, the entry says so explicitly** rather than inventing one. |

Services are grouped by module. Modules map onto `PLAN.md` §C3.

---

# Pack 1: Reliability & Service Ops

**Packs id:** `reliability_ops` · **Required streams:** `request_flow` (plus `member_lifecycle` for
capacity) · **Default cadence:** nightly, except `queueing.*` which is hourly during working hours.

This is the pack that sells the thesis. Every competing community dashboard computes "average
resolution time" over closed tickets only. That number is not slightly wrong, it is biased in a
known direction, and the size of the bias grows with the backlog. Pack 1 exists to report the
correct figure and to show the naive one next to it.

---

## `survival.py`

### `survival.km_resolution_curve`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, stratify_by: str \| None = None, clock: "wall" \| "active" = "wall", alpha: float = 0.05` |
| **output** | `series`: `{"t_days": [...], "survival": [...], "lo": [...], "hi": [...], "at_risk": [...], "events": [...], "censored": [...]}`. `unit="probability unresolved"`, `interval_kind="greenwood-95"` |
| **min_n** | **30 observed events**, not 30 rows. Below 30 the curve is a staircase of single observations and the Greenwood band is wider than the [0,1] range it lives in. Matches the Evidence contract §8 default for KM. |

The estimator is the delayed-entry Kaplan-Meier: at each event time the risk set is
`{i : at_risk_from_i <= t < exit_i}`, which handles left truncation (spine rule C3) and
administrative censoring (C2) in one form. The `at_risk` array is returned inside `value`, settling
the A.1 open question: it is intrinsic to the curve, not a parallel per-point `n`.

**assumptions**
- Censoring is independent of the resolution process (non-informative).
- Requests are exchangeable within a stratum.
- The event time is the terminal timestamp, not the time it was noticed.

**checks**

| id | tests | blocking | statistic |
|---|---|---|---|
| `censoring-informative` | Covariate distribution of censored versus observed spells. Two-sample test per covariate, Bonferroni corrected. | no | min adjusted p |
| `competing-risks-material` | Share of terminals that are `escalated` or `withdrawn`. WARN above 5%, FAIL above 15% (spine C5). | **yes above 15%** | share |
| `interval-censoring-share` | Share of spells with `censoring="interval"`. FAIL above 20% (spine C4). | **yes** | share |
| `left-truncation-share` | Share with `left_truncated=True`. Informational; a high share means the window is short relative to the process. | no | share |
| `tail-instability` | Fraction of the curve's range where `at_risk < 5`. The tail is truncated at that point rather than drawn. | no | last stable t |

**on failure** `competing-risks-material` FAIL suppresses the curve and directs the reader to
`survival.competing_risks_cif`, which is the correct estimator in that case. Interval-censoring
FAIL suppresses entirely; there is no honest fallback without Turnbull. `censoring-informative`
WARN keeps the curve and adds the caveat naming which covariate diverged and in which direction the
bias runs.

**method card**
- *assumes:* open requests are censored at the observation boundary and their censoring is unrelated to how long they would have taken; every request that was opened is present.
- *wrong_when:* an admin bulk-closes stale tickets (censoring becomes informative and the curve is optimistic); a material share of requests exit by escalation or withdrawal (use the cumulative incidence function instead); resolution timestamps are batch-imported and only bracketed.
- *interval_meaning:* the Greenwood band is a pointwise 95% confidence interval for the probability still unresolved at that day. It is not a band for the whole curve simultaneously, so reading two points off it as a joint statement is wrong.
- *min_n:* 30 observed events.
- *references:* Kaplan and Meier (1958) JASA 53:457. Klein and Moeschberger, *Survival Analysis*, 2nd ed., ch. 4. Andersen et al. on delayed entry risk sets.

**known answer** R `survival::survfit(Surv(time, status) ~ 1, data = lung)`: the published survival
estimates and the standard `lung` risk table. The delayed-entry path is checked against
`survival::survfit(Surv(start, stop, event) ~ 1)` on the `heart` transplant data, which is the
canonical published left-truncation example. Plus the **censoring regression fixture** required by
`docs/RULES.md` §7: a constructed set where the mean of closed spells is 3.1 days and the KM median
is 8.0, asserting the service reports 8.0 and that `n_censored` is non-zero.

---

### `survival.median_resolution_days`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, quantile: float = 0.5, clock = "wall", alpha = 0.05` |
| **output** | `scalar` days. `interval_kind="greenwood-95"` via Brookmeyer-Crowley inversion of the pointwise band. |
| **min_n** | 30 observed events, and additionally the curve must cross the requested quantile. If `S(t) > 0.5` everywhere the median is not reached; the service returns `insufficient_data=True` with the caveat "more than half of requests are still unresolved at the end of the window", which is itself the finding. |

**assumptions / checks** inherited from `km_resolution_curve`, plus `quantile-reached`.

**on failure** `quantile-reached` FAIL is not an error state, it is a reportable fact and the UI
renders the "not enough data" calm state with that sentence.

**method card**
- *assumes:* as the curve.
- *wrong_when:* the median is unreached and someone substitutes the mean of the closed subset. That substitution is the exact defect this product exists to name.
- *interval_meaning:* Brookmeyer-Crowley: the set of times whose confidence band contains 0.5. It can be asymmetric and it can be unbounded on the right.
- *references:* Brookmeyer and Crowley (1982) Biometrics 38:29.

**known answer** `lung`: median survival 310 days with a 95% interval of 285 to 363, the figure
printed by `survfit` in every R survival tutorial.

---

### `survival.sla_attainment`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, horizon_days: float, clock: "wall" \| "active"` |
| **output** | `scalar` probability resolved by `horizon_days`, `= 1 - S(horizon)`. `interval_kind="greenwood-95"`. |
| **min_n** | 30 observed events **and** `at_risk >= 10` at `horizon_days`. The second condition matters more: a curve with 200 events can still have four requests at risk at day 30, and the estimate there is worthless. |

**checks** the curve's checks, plus `horizon-in-support` (blocking if `horizon_days` exceeds the
last observation time, because extrapolating a KM curve past its data is fabrication).

**known answer** `lung` at t = 365: published `summary(survfit(...), times=365)` value.

---

### `survival.first_response_curve`

Identical machinery to `km_resolution_curve` with `first_response_hours` as the duration and
"a non-author responded" as the event. Same checks, same min_n, `unit="probability unanswered"`.
Separated because acknowledgement and resolution are different promises and communities conflate
them. **known answer:** the same `lung` fixture with relabelled fields, asserting numeric identity
with `km_resolution_curve`, which is a real regression risk if someone forks the estimator.

---

### `survival.churn_curve`

`MemberSpell[]` instead of `RequestSpell[]`. `exit_kind` is the event, ongoing membership is
administrative censoring, members who joined before the window are left-truncated. Stratify by
`strata_at_entry`. Everything else as `km_resolution_curve`. **min_n** 30 observed exits.
**known answer:** the same `lung`-based fixture, plus an analytic one: spells drawn from an
Exponential(rate) with independent uniform censoring must produce a KM curve within Monte Carlo
tolerance of `exp(-rate * t)`, seeded. Exponential survival is a closed form, so this is an exact
external truth rather than a reference-implementation comparison.

---

### `survival.logrank_compare`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, group_by: str, weights: "logrank" \| "wilcoxon" = "logrank"` |
| **output** | `structure`: `{"chi_square", "df", "p_value", "groups": [{"key", "n", "events", "median", "lo", "hi"}]}`. `interval_kind="none"` on the test statistic; each group row carries its own Greenwood interval. |
| **min_n** | 10 observed events **per group**, and at least 2 groups. Groups below the floor are pooled into `"other"` with the count disclosed, never silently dropped. |

**checks**
- `group-min-n`, non-blocking, lists pooled groups.
- `proportional-across-groups`: the log-rank test has most power against proportional alternatives. If curves cross, a non-significant p is not evidence of no difference. The check detects a crossing and downgrades to WARN with the caveat "the curves cross; the log-rank test is under-powered here, read the curves".
- `k-anonymity-cells`: any group with fewer than the tenant's `k` distinct members is suppressed. **Blocking for that row.**

**method card**
- *assumes:* independent censoring in every group; a common event-time scale.
- *wrong_when:* survival curves cross; groups are chosen after looking at the data (multiple comparisons, so the service applies Holm correction across all pairwise tests and reports both raw and adjusted p).
- *interval_meaning:* none on the statistic; a p-value is not an interval and the UI must not draw one.
- *references:* Mantel (1966); Peto and Peto (1972).

**known answer** `survival::survdiff(Surv(time, status) ~ sex, data = lung)`: chi-square 10.3 on
1 df, p = 0.001. Universally reproduced in R survival documentation.

---

### `survival.cox_hazard_ratios`

| | |
|---|---|
| **streams** | `RequestSpell[]`, plus `CalendarMark[]` from the window for seasonal covariates |
| **input** | `spells, window, *, covariates: tuple[str, ...], time_varying: tuple[str, ...] = (), penalizer: float = 0.0, alpha = 0.05, ties: "efron" = "efron"` |
| **output** | `table`, one row per covariate: `{"covariate", "coef", "hazard_ratio", "lo", "hi", "p_value", "n_events_supporting"}`. `interval_kind="profile-95"`, `unit="hazard ratio"`. |
| **min_n** | **10 observed events per covariate** (the events-per-variable rule). With 7 covariates that is 70 events, not 70 rows. Below it, coefficients are unstable and their intervals are not trustworthy. Matches the Evidence contract §8. |

**checks**

| id | tests | blocking |
|---|---|---|
| `proportional-hazards` | Schoenfeld residual correlation with transformed time, per covariate and globally. | **yes, per covariate** |
| `events-per-variable` | events / covariates >= 10. | **yes** below 5 |
| `separation` | a covariate perfectly predicting the outcome; coefficient diverges. | **yes** for that row |
| `collinearity` | variance inflation factor above 5. | no |
| `influential-observations` | dfbeta above threshold; reports how many rows move a coefficient by more than 20%. | no |
| `censoring-informative` | as the curve. | no |

**on failure** This is the single most important failure path in Pack 1. **A hazard ratio whose
Schoenfeld test fails is not interpretable as a constant multiplier and the platform must not print
it as one.** The row is suppressed and replaced by the check's `detail`: "the effect of `category`
changes over time, so a single hazard ratio would be misleading. Its direction reverses around day
14." Where the violation is time-shape rather than noise, the service suggests the stratified model
(`stratify_by=covariate`) which is exact under non-proportionality, and the API exposes that as a
one-click alternative run.

**method card**
- *assumes:* hazards are proportional over time; the log-hazard is linear in each continuous covariate; censoring is independent; events at distinct times (Efron correction for ties).
- *wrong_when:* the effect appears late or fades (monsoon plumbing is the archetype and it fails proportionality by construction); a covariate is measured after the request opened, which is immortal time bias and inflates its apparent protective effect; the covariate set was chosen by looking at p-values.
- *interval_meaning:* a 95% profile-likelihood interval on the hazard ratio. It is multiplicative: an interval containing 1.0 means no detected effect. It is not a prediction interval for any single request.
- *min_n:* 10 events per covariate.
- *references:* Cox (1972) JRSS-B 34:187. Grambsch and Therneau (1994) Biometrika 81:515 for the Schoenfeld test. Peduzzi et al. (1995) for events per variable.

**known answer** The `rossi` recidivism dataset, the standard lifelines and Klein-Moeschberger
fixture. Published coefficients: `fin` -0.379, `age` -0.057, `race` 0.314, `wexp` -0.150,
`mar` -0.434, `paro` -0.085, `prio` 0.091. Tolerance 1e-3 on the coefficient and 1e-2 on the
standard error. **The Schoenfeld check is tested on the same dataset**, where `age` is documented to
violate proportional hazards at the 5% level while `fin` does not: the test asserts our check
returns FAIL for `age` and PASS for `fin`, which is a ground truth about the *check*, not only
about the model.

---

### `survival.competing_risks_cif`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, causes: tuple[str, ...] = ("resolved", "escalated", "withdrawn"), alpha = 0.05` |
| **output** | `structure`: one `series` per cause, `{"cause": {"t_days", "cif", "lo", "hi"}}`, plus `"still_open"`. `interval_kind="normal-95"` on the log-log scale, `unit="cumulative probability"`. |
| **min_n** | 30 events of the cause being reported, and at least 5 of each competing cause for the competition to be estimable. |

**assumptions** the causes are mutually exclusive and exhaustive; censoring is independent of all
causes.

**checks** `cif-sums-to-one` (the CIFs plus the still-open probability must sum to 1 at every t,
within 1e-9; a violation is an implementation bug and is **blocking**), `cause-min-n`,
`censoring-informative`.

**method card**
- *assumes:* every request eventually exits by exactly one of the declared causes.
- *wrong_when:* someone reads `1 - KM` per cause as the cumulative incidence. That quantity is the probability of resolution in a hypothetical world where escalation cannot happen, it always exceeds the true incidence, and it is the mistake the Aalen-Johansen estimator exists to fix.
- *interval_meaning:* a pointwise 95% interval on the probability that a request has exited by this specific cause by day t.
- *references:* Aalen and Johansen (1978). Putter, Fiocco and Geskus (2007) Stat Med 26:2389.

**known answer** Two grounds. First an exact analytic identity: with a single cause, the
Aalen-Johansen CIF must equal `1 - KM` to floating-point tolerance, which is a theorem and
therefore stronger than any dataset. Second the R `survival` multi-state vignette's `mgus2`
example, whose published cumulative incidence values we assert against.

---

## `spc.py`

### `spc.ewma_chart`

| | |
|---|---|
| **streams** | `FlowPeriod[]` or `LedgerPeriod[]` or `ParticipationPeriod[]` |
| **input** | `series, window, *, lam: float = 0.2, target_arl0: int = 500, baseline_periods: int \| None = None` |
| **output** | `structure`: `{"points", "ewma", "center", "ucl", "lcl", "signals": [{"index", "at", "direction"}]}`. `interval_kind="control-limits"`, and the contract's note applies: control limits are a decision boundary, not an estimate of anything. |
| **min_n** | **20 complete periods.** Limits estimated from fewer are themselves so noisy that the chart signals on its own estimation error. Evidence contract §8 default. |

`L` is solved for the requested in-control average run length rather than defaulted to 3 sigma.
`target_arl0=500` at `lam=0.2` gives `L` near 2.86; a weekly chart on 3 sigma false-alarms roughly
every 7 years in theory and constantly in practice because the residuals are not normal.

**checks**
- `baseline-stability`: the baseline period used to set the limits must itself be in control, checked by a preliminary pass. If the baseline contains a signal, limits are inflated and the chart goes blind. **Blocking**, with the remedy "pick a quiet baseline window".
- `residual-autocorrelation`: Ljung-Box on the baseline residuals. Positive autocorrelation makes the true ARL0 far shorter than nominal. WARN, with the corrected effective ARL reported.
- `overdispersion`: for count series, variance over mean. If above 1.5, the service directs to `spc.poisson_rate_chart` with a negative-binomial limit instead.
- `incomplete-periods`: any period with `complete=False` is excluded and disclosed.

**on failure** `baseline-stability` FAIL suppresses the chart. An out-of-control baseline produces a
chart that says everything is fine, which is worse than no chart.

**method card**
- *assumes:* independent observations in the baseline; a stable in-control mean and variance; the limit constant was chosen for a stated ARL0.
- *wrong_when:* the series is autocorrelated (weekly complaint counts usually are, after a festival); the baseline itself contained the shift you are looking for; the process has a trend, which EWMA will eventually track and then stop flagging.
- *interval_meaning:* not a confidence interval. Points outside the limits are a decision rule tuned so that a stable process false-alarms about once every `target_arl0` periods.
- *references:* Roberts (1959) Technometrics 1:239. Lucas and Saccucci (1990) Technometrics 32:1, whose ARL tables we use. Montgomery, *Introduction to Statistical Quality Control*, 7th ed., ch. 9.

**known answer** Lucas and Saccucci (1990) Table 3, the ARL0 = 500 row: `L` = 2.615 at
`lam=0.05`, 2.814 at `lam=0.10`, 2.998 at `lam=0.25`, 3.071 at `lam=0.50`; and ARL1 = 10.3 for a
1 sigma shift at `lam=0.10`. Our `L`-solver reproduces all five to within 0.01, and the run length
is confirmed independently by seeded simulation. Chart values are checked against the EWMA
recursion written out by hand. (An earlier draft of this line paired `L=2.703` with ARL0 = 500;
2.703 is the ARL0 = 370 constant at `lam=0.10`, and the implementation reproduces both rows.)

---

### `spc.cusum_chart`

| | |
|---|---|
| **streams** | as EWMA |
| **input** | `series, window, *, k: float = 0.5, h: float = 5.0, baseline_periods = None` |
| **output** | `structure`: `{"points", "c_hi", "c_lo", "h", "signals"}`. `interval_kind="control-limits"`. |
| **min_n** | 20 complete periods. |

Same checks as EWMA. CUSUM is the faster detector of a persistent step; EWMA is more forgiving of
non-normality. The pack runs both and the dashboard shows agreement or disagreement rather than
picking one, because a disagreement is itself information about whether the shift is a step or a
drift.

**known answer** Hawkins (1993) and the standard `k=0.5`, `h=5` table reproduced in Montgomery
ch. 9: ARL0 = 465, ARL1 = 10.4 at 1 sigma, 5.75 at 1.5 sigma, 4.01 at 2 sigma. All four are
reproduced by the Markov-chain solver. Chart arithmetic is checked against the `C+`/`C-` recursion
written out by hand rather than against Montgomery's printed table, which is not vendored.

---

### `spc.poisson_rate_chart`

| | |
|---|---|
| **streams** | `FlowPeriod[]` |
| **input** | `series, window, *, exposure_field: str = "exposure_days", dispersion: "poisson" \| "auto" = "auto"` |
| **output** | `structure` as above, limits from the Poisson or negative-binomial quantile rather than a normal approximation. `unit="requests per day"`. |
| **min_n** | 20 periods **and** an average count of at least 5 per period. Below an average of 5 the normal approximation used by textbook c-charts is bad enough to change conclusions, so the service uses exact Poisson quantiles and says so. |

**checks** `overdispersion` (variance/mean; switches to negative binomial and discloses the switch),
`unequal-exposure` (uses a u-chart with varying limits when period lengths differ, which they do
whenever a month is the period).

**known answer** The exact check: for a known Poisson mean, our limits must equal the exact
`ppf(alpha/2)` and `ppf(1-alpha/2)` quantiles, verified against the explicit distribution sum.
Montgomery's printed-circuit-board c-chart is the published comparison, but its raw table is not
vendored, so it is listed in the appendix of services validated by identity rather than by dataset.

---

## `changepoint.py`

### `changepoint.detect_level_shifts`

| | |
|---|---|
| **streams** | any `*Period[]` |
| **input** | `series, window, *, penalty: "bic" \| "mbic" \| float = "mbic", min_segment: int = 4, model: "normal_mean" \| "poisson" = "normal_mean"` |
| **output** | `table`, one row per detected changepoint: `{"at", "index", "before_mean", "after_mean", "delta", "p_value", "lo", "hi"}` where `lo`/`hi` bracket the changepoint *date*, not the level. `interval_kind="bootstrap-bca-95"`, obtained by a seeded block bootstrap over segments. |
| **min_n** | **24 periods**, and `min_segment` observations on each side of any reported point. Evidence contract §8. A changepoint 2 periods from the end of the series is unidentifiable from noise and the service will not report one. |

**assumptions** piecewise-constant mean; independent residuals within a segment; the penalty
controls the number of segments and is declared.

**checks**
- `edge-changepoint`: a point within `min_segment` of either end is suppressed, **blocking for that
  row**, because it is the single most common false positive in this family.
- `residual-autocorrelation`: autocorrelation inflates the detected segment count. WARN, and the
  penalty is adjusted upward with the adjustment disclosed.
- `significance`: each candidate gets a seeded permutation p-value. Points above 0.05 are reported
  with a WARN rather than deleted, so the reader sees the near-misses.

**method card**
- *assumes:* the series really is piecewise constant rather than smoothly trending. A smooth trend will be chopped into a staircase of spurious changepoints.
- *wrong_when:* the data has strong seasonality that was not removed first (the service requires either a deseasonalised input or `model="poisson"` with a seasonal offset, and refuses otherwise); the penalty was tuned until the answer looked good.
- *interval_meaning:* the interval is on the *date*: "the level shifted somewhere between 8 and 19 August, most likely 12 August". It is not an interval on the size of the shift, which is reported separately.
- *references:* Killick, Fearnhead and Eckley (2012) JASA 107:1590 for PELT. Zeileis et al. (2003) for the confidence intervals on break dates.

**known answer** The `Nile` annual river-flow series, the canonical changepoint benchmark: PELT and
binary segmentation both find a single level shift at 1898, the year the first Aswan dam works
began. Published in Killick et al. and reproduced by the R `changepoint` package. Our test asserts
exactly one changepoint at index 1898 and a mean drop from about 1097 to about 850.

---

## `queueing.py`

Every service in this module needs `active_servers`, which comes from the cross-stream reducer
`streams.capacity.active_servers` (spine §7). The reducer's definition is part of each Method Card
because "how many resolvers do you actually have" is the least well-defined input in the pack.

### `queueing.little_law_wait`

| | |
|---|---|
| **streams** | `FlowPeriod[]` |
| **input** | `periods, window` |
| **output** | `scalar` expected wait in days, `W = L / lambda` using the mean backlog and mean arrival rate. `interval_kind="bootstrap-bca-95"` over periods, seeded. `unit="days"`. |
| **min_n** | 8 periods. Little's Law is an identity in the long-run averages, so it needs enough periods for those averages to mean something, but it needs no distributional assumption at all, which is why the floor is lower than the SPC floor. |

**assumptions** the system is in steady state over the window: arrivals and departures balance and
the backlog has no trend. That is the whole assumption, and it is the one that fails.

**checks** `steady-state`: regression of `backlog_end` on time. A significant slope means the queue
is growing or draining and the long-run average wait is not a description of anyone's experience.
**Blocking**, with the caveat "the backlog grew from 12 to 61 over this window; there is no
steady-state wait to report, the queue is diverging", which is a far more useful sentence than a
number.

**method card**
- *assumes:* steady state. Nothing else. No arrival distribution, no service distribution.
- *wrong_when:* the backlog is trending; the window spans a policy change; arrivals and the backlog are measured on different populations, for example counting all requests as arrivals but only one category in the backlog.
- *interval_meaning:* a bootstrap interval over the period-level variation, so it reflects how much the average wait moves week to week, not sampling error on individuals.
- *references:* Little (1961) Operations Research 9:383.

**known answer** Exact algebra. `L = lambda * W` is an identity, so the test constructs a queue with
known arrival rate and known waits, computes `L` by simulation with a fixed seed, and asserts the
identity holds to floating-point tolerance. This is a stronger ground truth than any published
table because it is a theorem.

---

### `queueing.mmc_metrics`

| | |
|---|---|
| **streams** | `FlowPeriod[]` for arrivals and servers, `RequestSpell[]` for service times |
| **input** | `arrival_rate, service_rate, servers, *, service_cv: float \| None = None` |
| **output** | `structure`: `{"utilisation", "p_wait", "lq", "wq_days", "w_days", "l"}`. Each numeric carries its own interval where the inputs were estimated. `interval_kind="bootstrap-bca-95"`. |
| **min_n** | 30 closed spells for the service-rate estimate, and `utilisation < 1`. |

**checks**
- `stability`: `rho = lambda / (c * mu) < 1`. **Blocking.** An unstable queue has infinite expected wait and reporting a finite number is a lie. The message is "arrivals exceed capacity; the backlog grows without bound, no wait time exists to report", plus the minimum `c` that would stabilise it.
- `poisson-arrivals`: dispersion test on inter-arrival counts. WARN, with the direction of bias.
- `exponential-service`: coefficient of variation of service times. If it is far from 1, M/M/c understates the wait and the service directs to `queueing.mg1_wait`. WARN, escalating to FAIL above CV = 2.
- `service-time-censoring`: the service-rate estimate uses only closed spells and is therefore optimistic. **Always a WARN**, never silent, with the KM-based mean as the honest alternative.

**method card**
- *assumes:* Poisson arrivals, exponential service, `c` identical servers, no priority, no abandonment, infinite queue capacity.
- *wrong_when:* resolvers specialise by category, so they are not interchangeable, which is the normal case in a committee; requests are worked in priority order; residents give up and re-file, which is abandonment and makes the model optimistic.
- *interval_meaning:* propagated from the intervals on the estimated arrival and service rates by seeded bootstrap, so it is uncertainty about the parameters, not about a single request.
- *references:* Gross, Shortle, Thompson and Harris, *Fundamentals of Queueing Theory*, 5th ed., ch. 2 and 3.

**known answer** Worked examples from Gross and Harris ch. 2 with published `Lq`, `Wq` and `P(wait)`
values; plus two exact identities: M/M/1 is the `c=1` case of M/M/c to floating-point tolerance, and
`L = lambda * W` must hold for the model's own outputs.

---

### `queueing.erlang_c_staffing`

| | |
|---|---|
| **streams** | `FlowPeriod[]` + `RequestSpell[]` + `RosterSnapshot` |
| **input** | `arrival_rate, mean_service_time, *, target_fraction: float = 0.9, target_within_days: float = 5.0, max_servers: int = 200` |
| **output** | `structure`: `{"required_servers", "current_servers", "gap", "attained_at_current", "attained_at_required", "curve": [{"c", "p_within_target"}]}`. `interval_kind="bootstrap-bca-95"` on `attained_at_current`; `required_servers` is an integer with `interval_kind="none"` and instead carries the sensitivity curve so a reader sees that 4 gives 91% and 3 gives 74%. |
| **min_n** | 30 closed spells for the service time and 8 periods for the arrival rate. |

**checks** `stability` (blocking, as M/M/c), `poisson-arrivals`, `exponential-service`,
`service-time-censoring` (always WARN), and `servers-are-fungible`: measures how concentrated each
resolver's category mix is. If resolvers specialise, the pooled Erlang-C number understates the
requirement, because a plumbing request cannot be taken by the electrical volunteer. WARN with the
per-category breakdown offered as the alternative.

**method card**
- *assumes:* Erlang-C, so M/M/c with no abandonment and infinite patience. Real people abandon, which makes this staffing recommendation conservative in one direction and optimistic in another.
- *wrong_when:* volunteers are not interchangeable; volunteers are not available continuously (the "server" in a residents' committee is available two evenings a week, so the effective `c` is a fraction and the Method Card requires the reducer to state its availability convention); demand is strongly seasonal, in which case staff to the peak period, not the average.
- *interval_meaning:* the sensitivity curve is the honest output. An integer server count with a confidence interval would be theatre.
- *references:* Erlang (1917). Gans, Koole and Mandelbaum (2003) MSOM 5:79. Standard ACD staffing tables.

**known answer** Published Erlang-C staffing tables. The canonical one: 100 calls per hour with an
average handle time of 180 seconds is 5 Erlangs of offered load per 6-minute interval; the standard
worked case of 20 Erlangs offered load with an 80% within 20 seconds target requires 24 agents. Our
solver must reproduce the published agent counts for a grid of offered loads and service levels.
Additionally an exact identity: Erlang-C's `P(wait)` must equal the M/M/c `P(wait)` from
`mmc_metrics` for the same parameters.

---

### `queueing.mg1_wait`

| | |
|---|---|
| **streams** | `RequestSpell[]`, `FlowPeriod[]` |
| **input** | `arrival_rate, service_mean, service_var, *` |
| **output** | `scalar` expected wait from Pollaczek-Khinchine. `interval_kind="bootstrap-bca-95"`, `unit="days"`. |
| **min_n** | 30 closed spells, because the variance of the service time is the whole point and it needs more data than the mean. |

**checks** `stability` (blocking), `single-server-appropriate` (if `active_servers > 1` this model is
the wrong one and the check FAILs, blocking), `service-time-censoring` (always WARN).

**method card**
- *assumes:* one server, Poisson arrivals, any service distribution with a finite variance, first-come first-served.
- *wrong_when:* service times are heavy-tailed enough that the variance is not stable, which happens when one request has been open for two years; more than one person actually works the queue.
- *interval_meaning:* propagated parameter uncertainty, seeded bootstrap.
- *references:* Pollaczek (1930), Khinchine (1932). Gross and Harris ch. 5.

**known answer** The P-K formula is closed form, so the test is exact against hand computation, plus
the identity that at CV = 1 (exponential service) M/G/1 must equal M/M/1 to floating-point
tolerance.

---

## `fairness.py`

### `fairness.workload_gini`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, by: "assignee_ref" \| "group_ref" = "assignee_ref", weight: "count" \| "hours" = "count"` |
| **output** | `structure`: `{"gini", "lorenz": {"cum_share_people", "cum_share_work"}, "top_share", "rows": [...]}`. Gini carries `interval_kind="bootstrap-bca-95"`, seeded. |
| **min_n** | 10 resolvers **and** 50 assigned requests. Gini over 3 people is a description of 3 people, not a statistic, and its bootstrap interval spans most of [0,1]. |

**checks**
- `k-anonymity-rows`: per-person rows are suppressed below the tenant `k`; the aggregate Gini is still reported. **Blocking per row.**
- `zero-workers-included`: whether resolvers with zero assignments were counted. This single choice moves Gini enormously and is a declared parameter in `params_hash`, disclosed in the caveat.
- `unequal-difficulty`: Gini on counts treats a lift breakdown and a noisy-dog complaint as equal work. If category mix differs materially across resolvers, WARN and offer the hours-weighted variant.

**method card**
- *assumes:* the unit of work is comparable across people.
- *wrong_when:* one resolver takes only hard cases; part-time availability is not accounted for, so the person available one evening a week looks like a shirker.
- *interval_meaning:* a bias-corrected bootstrap interval over resolvers. Gini is biased downward in small samples and the bias correction matters at n = 10.
- *references:* Gini (1912). Efron and Tibshirani (1993) for BCa.

**known answer** Exact closed forms: Gini of a perfectly equal vector is 0; of the vector
`(0, 0, ..., 0, 1)` it is `(n-1)/n`; of the discrete uniform `1..n` it is `(n-1)/(3n)`. Three
analytic values, no reference implementation needed. Lorenz curve checked against a published income
distribution example.

---

### `fairness.balanced_assignment`

| | |
|---|---|
| **streams** | `RequestSpell[]` (open ones), `RosterSnapshot` |
| **input** | `open_requests, resolvers, *, cost: "load_and_skill", capacity: Mapping[str, int], seed: int` |
| **output** | `table`: `{"request_ref", "suggested_assignee_ref", "cost", "reason"}` plus a `structure` summary with the resulting Gini before and after. `interval_kind="none"`; this is an optimisation result, not an estimate, and giving it an interval would be a category error. |
| **min_n** | 1 open request and 2 resolvers. There is no statistical floor because there is no inference here, only optimisation. The Method Card says so explicitly, because a service with `interval_kind="none"` and `min_n=1` looks suspicious next to the rest of the pack and the reason should be visible. |

**checks** `capacity-feasible` (blocking if total capacity is below the number of requests, since
then no complete assignment exists and the service returns the partial one plus the shortfall),
`skill-coverage` (a category no available resolver can take is surfaced, not silently assigned).

**method card**
- *assumes:* the cost matrix reflects real preferences and capacity. It is a recommendation, and the Method Card says in one sentence that a committee overriding it is not an error.
- *wrong_when:* the cost function encodes only load and ignores expertise, which will hand the STP problem to whoever is least busy.
- *interval_meaning:* none. Optimisation output.
- *references:* Kuhn (1955) Naval Research Logistics Quarterly 2:83. Munkres (1957).

**known answer** Exhaustive enumeration as the oracle on seeded random matrices, which is exact
rather than a second implementation and needs no dependency; a 3x3 instance where the greedy choice
costs 34 and the optimum 33; and the invariant that adding a constant to any row leaves the optimal
assignment unchanged.

---

## Pack 1 composed views

Two dashboard figures are compositions rather than services, and the composition happens in
`stats/`, never in a service layer, because a derived figure needs its own `n` and interval
(Evidence contract §9).

- `survival.naive_vs_km_gap` returns a `structure` with the naive mean of closed spells, the KM
  median, and the gap, with `n_censored` and the sentence that explains it. **This is the
  demonstration figure for the whole product** and it is also, deliberately, the permanent
  regression test from `docs/RULES.md` §7 rendered as a UI panel.
- `queueing.backlog_projection` takes an arrival forecast from Pack 3 and current capacity, and
  returns the projected backlog trajectory with a predictive interval. It is listed in Pack 1 but
  requires Pack 3 to be enabled, which the registry declares as a soft dependency.

---

# Pack 3: Forecasting & Calibrated Risk

**Pack id:** `forecast_risk` · **Required streams:** `ledger`, `request_flow`, `participation` ·
**Default cadence:** weekly for forecasts, nightly for conformal ETAs, monthly for risk-model
refits, nightly for drift.

Two gates govern this entire pack and neither is negotiable.

> **The MASE gate.** No forecaster is served to a tenant unless it beat seasonal-naive on MASE
> under rolling-origin cross-validation *on that tenant's own history*. Not on average across
> tenants, not in a paper. The comparison is computed as part of every run, stored in the envelope,
> and shown in the UI. A forecast that cannot beat naive is decoration, and decoration that looks
> like a forecast is worse than nothing.

> **The calibration gate.** No risk score is served unless, after calibration on a held-out split,
> its Brier skill score against climatology is positive and its expected calibration error is under
> the pack threshold. AUC is reported but never gates anything: it measures ranking, and a model
> that ranks perfectly while claiming 90% for events that happen 40% of the time will get a
> committee to act on a number that is not true.

---

## `forecast.py`

### `forecast.seasonal_naive`

| | |
|---|---|
| **streams** | any `*Period[]` |
| **input** | `series, window, *, season_length: int, horizon: int` |
| **output** | `series` with `{"t", "yhat", "lo", "hi"}`. `interval_kind="predictive-80"` from the residual quantiles. |
| **min_n** | `2 * season_length` periods. You cannot estimate a seasonal pattern you have seen once. |

Not a product feature. It is the **denominator of every other forecaster in this pack** and it is
specified first so that nothing can ship without something to be measured against. It is also
served to the UI, deliberately, so a reader can see what the sophisticated model is beating.

**known answer** Exact: `yhat[t] = y[t - m]`. Trivially testable, and the MASE of seasonal-naive
against itself must equal exactly 1.0, which is the anchor for the entire gate.

---

### `forecast.stl_decompose`

| | |
|---|---|
| **streams** | any `*Period[]` |
| **input** | `series, window, *, season_length: int, robust: bool = True, seasonal_smoother: int = 7` |
| **output** | `structure`: `{"observed", "trend", "seasonal", "remainder", "seasonal_strength", "trend_strength"}`. `interval_kind="none"` on the components; a decomposition is a partition, not an estimate. The remainder's spread is reported separately. |
| **min_n** | `2 * season_length` periods, and at least 24 observations in total. |

**assumptions** additive decomposition (the service tests a log transform and reports which was
used); the seasonal pattern changes slowly.

**checks**
- `reconstruction-identity`: `trend + seasonal + remainder == observed` to 1e-9. An implementation
  bug guard, **blocking**.
- `seasonality-material`: seasonal strength as defined by Wang, Smith and Hyndman. Below 0.3 the
  service says "there is no meaningful seasonality here" instead of drawing a seasonal panel that
  is noise.
- `additive-appropriate`: variance-versus-level relationship. If the seasonal amplitude grows with
  the level, WARN and recommend the multiplicative form.
- `incomplete-periods`: trailing periods past `complete_through` are excluded, disclosed.

**method card**
- *assumes:* a single fixed-length seasonal period; slowly varying seasonality; additivity unless a transform was applied.
- *wrong_when:* the community has two overlapping seasonalities, for example a weekly rhythm and a festival calendar, which STL with one period cannot separate; the series has a level shift, which STL will smear across the trend rather than isolate (run `changepoint.detect_level_shifts` first, and the pack does).
- *interval_meaning:* none on the components. The remainder is what is left, not an error term with a distribution.
- *references:* Cleveland, Cleveland, McRae and Terpenning (1990) Journal of Official Statistics 6:3.

**known answer** Partial, and stated as such. There is **no published table of STL component
values** to assert against, so the ground truth is two-part: the exact reconstruction identity
above, asserted to 1e-9; and recovery of known components from a synthetic series built as a
specified trend plus a specified seasonal plus seeded noise, where the recovery error must be a
stated fraction of the injected noise. The first is a theorem, the second is a construction.
**Neither is a published external number, and the Method Card says so.**

> *Corrected during implementation.* This entry originally named a third ground truth, agreement
> with the reference `statsmodels` STL implementation on the `co2` series. `statsmodels` is not a
> dependency of this package and `co2` is not vendored, so that comparison cannot run here and
> claiming it would have been a known answer nothing checks. The remaining two are what the tests
> actually assert.

---

### `forecast.holt_winters`

| | |
|---|---|
| **streams** | any `*Period[]` |
| **input** | `series, window, *, season_length, horizon, trend: "add" \| "none", seasonal: "add" \| "mul" \| "none", damped: bool = True, alpha_grid seeded` |
| **output** | `series` `{"t", "yhat", "lo", "hi"}` plus a `structure` block with fitted smoothing parameters and the backtest result. `interval_kind="predictive-80"` and `"predictive-95"` both returned. |
| **min_n** | `2 * season_length`, minimum 24 periods. |

**checks**
- `beats-seasonal-naive`: MASE from `forecast.rolling_origin_backtest` must be below 1.
  **This is the gate.** A failure substitutes the seasonal-naive forecast and marks the envelope
  `qualified`; it is deliberately *not* flagged blocking, because a blocking failure empties the
  value (the rule recorded in the decision log) and the entire point of this gate's failure path is
  that the honest baseline number is still shown. The substitution is named in the check detail and
  in a caveat, and `structure.served` records which forecaster produced the numbers.
- `residual-independence`: Ljung-Box on residuals. A failure means the intervals are too narrow;
  WARN with widened intervals and the inflation factor disclosed.
- `residual-normality`: only affects the interval, not the point forecast. If it fails, the service
  switches to empirical residual quantiles for the interval and says so.
- `parameter-on-boundary`: alpha or beta at 0 or 1 indicates a degenerate fit. WARN.
- `horizon-vs-history`: forecasting further than one third of the history is flagged.

**on failure** A blocking MASE failure does not raise. The service returns an `Evidence` whose value
is the **seasonal-naive forecast** with a caveat naming the MASE of both, so the tenant still gets a
number and the number is the honest one. This is the behaviour the gate is for.

**method card**
- *assumes:* exponential smoothing state space form; additive errors unless multiplicative was selected; a stable seasonal period.
- *wrong_when:* the level shifted (fit on the segment after the changepoint instead); a one-off event dominates (a single festival collection will be smoothed into the trend and inflate the next four periods); the series is a count with many zeros, where a Poisson model is the right tool and this is not.
- *interval_meaning:* an 80% prediction interval for a *future observation*, not for the mean. It is wider than a confidence interval on purpose and it widens with horizon.
- *references:* Holt (1957), Winters (1960). Hyndman, Koehler, Ord and Snyder, *Forecasting with Exponential Smoothing* (2008). Hyndman and Athanasopoulos, *Forecasting: Principles and Practice*, 3rd ed., ch. 8.

**known answer** *FPP3* §8.3's worked Holt-Winters example on the Australian domestic tourism data,
whose fitted smoothing parameters and point forecasts are published in the text. Second ground
truth: on the M3 competition monthly series, published benchmark MASE values for ETS give a range
our implementation must land inside.

---

### `forecast.sarima`

| | |
|---|---|
| **streams** | any `*Period[]` |
| **input** | `series, window, *, order, seasonal_order, season_length, horizon, auto: bool = True, ic: "aicc"` |
| **output** | as Holt-Winters, plus the selected order and its information criterion. |
| **min_n** | `3 * season_length` and at least 36 periods. SARIMA has more parameters than exponential smoothing and needs more data before its intervals mean anything. Stricter than the contract's default for that reason, and the Method Card states the deviation. |

**checks** as Holt-Winters, plus `stationarity` (KPSS and ADF on the differenced series; disagreement
between them is itself reported), `invertibility` (roots outside the unit circle; blocking, since a
non-invertible fit's forecasts are unstable), `overdifferencing`.

**method card**
- *assumes:* linear, stationary after differencing, Gaussian innovations for the interval.
- *wrong_when:* automatic order selection was run on a short series, where AICc will happily pick a 6-parameter model for 40 observations; the series has structural breaks.
- *interval_meaning:* as Holt-Winters, and additionally these intervals ignore parameter uncertainty, so they are known to be slightly too narrow. The caveat says so.
- *references:* Box, Jenkins, Reinsel and Ljung, *Time Series Analysis*, 5th ed. Hyndman and Khandakar (2008) JSS 27:3 for automatic order selection.

**known answer** Two parts. First, an exact algebraic identity: the multiplicative seasonal
polynomial `(1 + t B)(1 + T B^m)` expands to `t` at lag 1, `T` at lag m and the cross term `t * T`
at lag m + 1, asserted to 1e-12. That cross term is the entire content of the airline model and an
implementation that dropped it would still fit plausibly while being a different model. Second,
parametric recovery: the airline process is simulated at a fixed seed from theta = -0.40 and
Theta = -0.56 and the estimator must recover both, within a tolerance derived from the asymptotic
standard error `sqrt((1 - theta^2) / n)` rather than chosen.

> *Corrected during implementation.* This entry originally asserted the published `AirPassengers`
> fit to a tolerance of 0.02. `AirPassengers` is not vendored in this repository and the
> implementation environment has no network access, so that fit cannot be reproduced here.
> Vendoring the series from memory to keep the sentence true would have been the exact dishonesty
> this document exists to prevent. Parametric recovery is a weaker claim than reproducing a
> published fit and is labelled as one; the published figures remain the right test to add on the
> day the series is vendored.

---

### `forecast.rolling_origin_backtest`

| | |
|---|---|
| **streams** | any `*Period[]` |
| **input** | `series, window, *, forecaster, season_length, horizon, initial_train: int, step: int = 1, min_folds: int = 5` |
| **output** | `structure`: `{"mase", "smape", "rmse", "coverage_80", "coverage_95", "baseline_mase", "folds": [...], "beats_baseline": bool}`. `interval_kind="bootstrap-bca-95"` on MASE across folds. |
| **min_n** | `initial_train + min_folds * step` periods, so at least 5 folds. Fewer folds and the MASE comparison is a coin flip. |

**This is the enforcement mechanism, not a diagnostic.** Every forecaster's Evidence embeds this
service's output, and the `beats-seasonal-naive` check reads it.

**checks**
- `folds-sufficient`, blocking below 5.
- `coverage-honest`: empirical coverage of the 80% and 95% intervals across folds. If the 80%
  interval covers 55% of held-out points, the interval is a fiction, and this is a **blocking**
  failure on the interval while leaving the point forecast readable. Under-coverage is far more
  common than over-coverage and is invisible unless measured.
- `origin-leakage`: an assertion that no fold's training set contains an observation after its
  origin. A guard against the single worst bug in this file's family, **blocking**.

**method card**
- *assumes:* time order is respected; the baseline is seasonal-naive with the same season length.
- *wrong_when:* MASE is compared across series with different scales and averaged carelessly; the model was tuned on the same folds it is being evaluated on, which is why hyperparameter selection happens inside each fold, not outside.
- *interval_meaning:* a bootstrap interval on MASE over folds, indicating how stable the advantage over naive is. A MASE of 0.95 with an interval of 0.6 to 1.4 has not beaten naive.
- *references:* Hyndman and Koehler (2006) IJF 22:679, which defines MASE. Tashman (2000) IJF 16:437 on rolling-origin evaluation.

**known answer** Two exact anchors. First, the MASE of seasonal-naive evaluated against itself is
exactly 1.0 by construction, which pins the scaling denominator. Second, MASE on a hand-computed
5-point example is checked against the arithmetic in Hyndman and Koehler's paper. Interval coverage
is checked by seeded simulation from a known generating process, where nominal 80% must be attained
within binomial tolerance.

---

### `forecast.dues_collection`, `forecast.request_volume`, `forecast.attendance`

Three thin, named compositions over `holt_winters` / `sarima` / `seasonal_naive` with the right
stream, season length and calendar regressors bound in. They exist as separate ids because the
Method Card differs: dues collection has a hard monthly billing cycle and a festival spike;
request volume is a count series with monsoon structure; attendance is bounded above by the roster
size and must not forecast 400 attendees for a 340-member society. That last one is a real check:
`bounded-by-roster`, **blocking**, comparing the upper predictive bound against `RosterSnapshot`.

**known answer** each inherits its parent's ground truth. The additional assertion is the bound
check, tested against a fixture that would otherwise forecast past the roster size.

---

## `montecarlo.py`

### `montecarlo.runway_shortfall`

| | |
|---|---|
| **streams** | `LedgerPeriod[]` plus a forecast Evidence |
| **input** | `opening_balance_minor, inflow_forecast, outflow_forecast, *, horizon: int, floor_minor: int = 0, draws: int = 20000, seed: int` |
| **output** | `structure`: `{"p_shortfall", "first_shortfall_period_p50", "first_shortfall_lo", "first_shortfall_hi", "balance_paths_quantiles"}`. `interval_kind="predictive-95"`, `unit="probability"`. |
| **min_n** | whatever the underlying forecasts require, plus 12 `LedgerPeriod` observations for the covariance between inflow and outflow. That covariance is the part everyone omits: if collections fall in the same month that maintenance spend rises, independent sampling understates the shortfall probability badly. |

**assumptions** the forecast predictive distributions are correct; inflow and outflow shocks are
drawn jointly with the estimated correlation; committed outflows (`status="expected"`) are treated
as certain and disclosed separately from forecast outflows.

**checks**
- `forecast-gate-inherited`: if either input forecast failed the MASE gate, this service **fails
  blocking**. A runway probability built on a forecast that loses to naive is precision theatre.
- `correlation-estimable`, WARN below 12 periods, in which case independence is assumed and the
  caveat says the probability is likely understated.
- `expected-entries-share`: how much of the projected inflow is receivables rather than forecast.
- `seed-recorded`: the seed is in `params_hash`, so the same run reproduces exactly.

**method card**
- *assumes:* the predictive distributions and their correlation; no structural change in the horizon; no emergency assessment levied mid-horizon, which is exactly what a committee would do and which the caveat names.
- *wrong_when:* a single large lumpy expense (an STP overhaul) is in the horizon and was not entered as an expected outflow; the correlation is estimated from 12 noisy points.
- *interval_meaning:* `p_shortfall` is a probability under the model; the interval on the first shortfall period is a predictive interval over simulated paths, which widens fast.
- *references:* standard first-passage formulation. Kroese, Taimre and Botev, *Handbook of Monte Carlo Methods*.

**known answer** Strong and analytic, in two closed forms rather than one. At a horizon of one
period the running minimum and the terminal balance are the same random variable, so the simulator
must reproduce the **exact Gaussian tail** `Phi((-distance - h * drift) / (sigma * sqrt(h)))` within
Monte Carlo error. Over a longer horizon the simulator's answer must sit inside a bracket whose two
ends are both closed forms: the exact terminal probability below, and the continuously monitored
**first-passage probability** from the reflection principle (whose density is the inverse Gaussian)
above. Both are genuine external mathematical truths, not reference implementations. A third
assertion covers the modelling claim the Method Card makes: `p_shortfall` must fall monotonically as
the inflow-outflow correlation rises, so independent sampling demonstrably understates the risk.

> *Corrected during implementation.* This entry originally asserted that the simulator matches the
> inverse-Gaussian first-passage formula directly. That formula is for **continuously monitored**
> Brownian motion; a ledger is monitored at period ends, because that is when a treasurer looks, so
> a path may dip below the floor and recover inside one month without being counted. The two
> quantities are genuinely different and the continuous one is strictly larger. Asserting equality
> would have forced either a wrong simulator or a padded tolerance, so the bracket is the honest
> statement and both of its ends are exact.

---

## `calibration.py`

### `calibration.isotonic_calibrate`

| | |
|---|---|
| **streams** | none. Takes score and label arrays produced by a risk service. |
| **input** | `scores, labels, *, out_of_fold: bool = True` |
| **output** | `structure`: the fitted step function as `{"thresholds", "values"}` plus the calibrated probabilities. `interval_kind="none"`; the mapping is fitted, and the uncertainty is reported by `brier_decomposition` instead. |
| **min_n** | **200 observations with at least 30 positives.** Isotonic regression is non-parametric and will overfit badly below that, producing a calibration map that is itself miscalibrated out of sample. Where the data is below this floor, the pack uses Platt scaling instead, automatically, and discloses the switch. |

**checks** `positives-sufficient` (blocking below 30), `monotone-output` (blocking; an
implementation guard), `out-of-fold` (WARN if calibration was fitted on the training data, which
produces optimistic calibration; the pack always uses out-of-fold and this check exists so a future
caller cannot quietly skip it).

**known answer** Exact. The pool-adjacent-violators algorithm has a unique solution and a
hand-computable one: for the input `[1, 3, 2, 4]` with equal weights the PAVA solution is
`[1, 2.5, 2.5, 4]`. A handful of such vectors, checked exactly, plus the invariants that the output
is non-decreasing and that the sum of fitted values equals the sum of inputs.

---

### `calibration.platt_calibrate`

Logistic regression of labels on scores, with Platt's prior correction to the target labels which
prevents overfitting at small n. **min_n** 50 with at least 10 positives. **known answer** the
**score equations are exactly zero at the fitted optimum**, asserted to 1e-8: at the maximum of a
strictly concave log-likelihood the gradient vanishes, which is a theorem about the objective.
Plus recovery of a known logistic generator at a fixed seed, and the exact property that a
perfectly calibrated input is mapped to approximately the identity. A fourth assertion covers the
prior correction specifically: on perfectly separable classes the fitted map must still return
probabilities strictly inside (0, 1), which is what the correction exists to guarantee.

> *Corrected during implementation.* This entry originally named agreement with
> `sklearn.linear_model.LogisticRegression` to 1e-6. `sklearn` is not a dependency of this package
> (see the standard-library-only decision in `CONTEXT.md`), so that comparison cannot run. The
> replacement is stronger rather than weaker: agreement with another library is only evidence that
> two implementations share their mistakes, whereas a vanishing gradient is a property of the
> optimum itself.

---

### `calibration.brier_decomposition`

| | |
|---|---|
| **input** | `probabilities, labels, *, bins: int = 10, binning: "equal_width" \| "equal_count" = "equal_count"` |
| **output** | `structure`: `{"brier", "reliability", "resolution", "uncertainty", "brier_skill_score", "base_rate"}`. `interval_kind="bootstrap-bca-95"` on the Brier score, seeded. |
| **min_n** | 100 observations and 20 positives, and at least 5 observations per bin or the bin is merged and the merge disclosed. |

**This is the gate metric.** `brier_skill_score = 1 - brier / brier_climatology`, where climatology
is predicting the base rate for everyone. A model with BSS <= 0 is worse than saying "everyone is at
the average risk" and it does not ship.

**checks** `bins-populated`, `bss-positive` (**blocking**: a negative skill score suppresses the risk
score entirely), `sample-size-for-bins`.

**method card**
- *assumes:* the labels are the outcome the probability referred to, over the same horizon. Half of all calibration failures in practice are a horizon mismatch rather than a modelling failure.
- *wrong_when:* the base rate shifted between the calibration set and now, which drift monitoring exists to catch; bins are equal-width on a skewed score distribution, so one bin holds 80% of the data.
- *interval_meaning:* a bootstrap interval on the Brier score. The decomposition components are exact given the binning, and the binning is a declared parameter.
- *references:* Brier (1950) Monthly Weather Review 78:1. Murphy (1973) J. Applied Meteorology 12:595 for the three-component decomposition.

**known answer** Exact and analytic. The Murphy decomposition is an identity, and its exact form on
arbitrary input carries a fourth term:

```
Brier = reliability - resolution + uncertainty + within_bin
```

where `within_bin = mean(d_i^2 - 2 * d_i * y_i)` and `d_i` is a forecast's deviation from its own
bin's mean. This must hold to 1e-12 on arbitrary seeded inputs. The familiar three-term form is
recovered **exactly** when the forecast is constant inside each bin, and that case is asserted
separately with `within_bin` equal to 0 to 1e-12. Additionally `uncertainty = base_rate *
(1 - base_rate)` exactly, and a perfectly calibrated constant forecaster has `reliability = 0`
exactly. Four exact identities, no reference implementation involved. `within_bin` is reported in
the envelope so a reader can check the arithmetic rather than trust it.

> *Corrected during implementation.* This entry originally claimed the three-term identity holds on
> arbitrary seeded inputs. It does not: with a continuous forecast the cross term does not vanish,
> and the three-term form is exact only under the constant-within-bin condition. The choice was to
> state the true identity or to quietly widen the tolerance until the false one passed. A document
> whose subject is honest measurement cannot take the second option.

---

### `calibration.reliability_diagram`

| | |
|---|---|
| **output** | `table`, one row per bin: `{"bin_lo", "bin_hi", "predicted_mean", "observed_rate", "n", "lo", "hi"}` with a Wilson interval per row, honouring the contract's rule that a table row carries its own `n` and interval. Plus `{"ece", "mce"}` in a companion `structure`. |
| **min_n** | as `brier_decomposition`. |

**checks** `ece-threshold` (**blocking** above the pack threshold of 0.05 for a served risk score),
`k-anonymity-bins` (a bin with fewer than `k` members is merged, not shown).

**known answer** A perfectly calibrated synthetic generator (draw `p ~ Uniform(0,1)`, draw
`y ~ Bernoulli(p)`, seeded) must give an ECE that converges to 0 at rate `O(1/sqrt(n))`, asserted
within a tolerance derived from that rate at n = 10,000. And a deliberately miscalibrated generator
(report `p/2`) must give an ECE close to the analytically computable 0.25.

---

## `risk.py`

### `risk.late_payment_risk`

| | |
|---|---|
| **streams** | `DueSpell[]`, `EngagementFeatures[]`, `MemberSpell[]` |
| **input** | `dues, features, window, *, horizon_days: int = 30, model: "logistic_l2" \| "gbdt" = "logistic_l2", calibrator: "isotonic" \| "platt" \| "auto" = "auto", folds: int = 5, seed: int` |
| **output** | `table`, one row per member: `{"member_ref", "probability", "lo", "hi", "top_features"}`, with `interval_kind="conformal-90"` on the per-member probability, plus a `structure` block carrying the whole calibration report. |
| **min_n** | **300 due spells with at least 40 late outcomes**, and at least 10 outcomes per feature. Below it the pack does not fit a model and instead returns the empirical late rate per stratum with Wilson intervals, which is honest and often almost as useful. |

**assumptions** the horizon is fixed and identical for every row; features are known *before* the
due date (no leakage); the population that generated the training data resembles the population
being scored.

**checks**

| id | tests | blocking |
|---|---|---|
| `calibration-gate` | BSS > 0 and ECE < 0.05 on the held-out fold, after calibration. | **yes** |
| `leakage-temporal` | every feature's timestamp precedes its row's due date. | **yes** |
| `censoring-handled` | a due unpaid at `window.end` within the horizon is right-censored, not labelled "paid on time". | **yes** |
| `class-balance` | fewer than 40 positives. | **yes** |
| `drift-since-fit` | PSI against the fitting distribution. | no, WARN above 0.25 |
| `stability-across-folds` | coefficient sign flips across folds. | no |
| `protected-strata-parity` | calibration error computed separately per stratum. A model well calibrated overall can be badly miscalibrated for one block. | no, WARN, and always reported |

**on failure** Any blocking failure suppresses the individual scores entirely and returns the
per-stratum empirical rates instead. **Individual risk scores are the highest-stakes output in the
platform** because a committee will act on them against a named household, so the failure mode is
deliberately conservative.

Two further hard rules that live in the Method Card rather than in code because they are policy:
per-member risk scores are visible only to roles the vertical manifest names, and they are never
included in an export or an LLM prompt with an identifier attached.

**method card**
- *assumes:* a fixed prediction horizon; no leakage; calibration transfers from the held-out fold to the present.
- *wrong_when:* the reminder policy changed, since reminders are a treatment and the model will learn "people who got reminders pay late" and invert the causal direction; a new billing cycle started; the score is read as a statement about a person rather than about a rate over similar rows.
- *interval_meaning:* a 90% conformal interval on the individual probability, which is wider than most tools show and is the honest width.
- *references:* Platt (1999); Zadrozny and Elkan (2002) for calibration. Gneiting and Raftery (2007) on proper scoring rules.

**known answer** **There is no external published ground truth for this model, and inventing a
benchmark would be exactly the dishonesty this document exists to prevent.** What is externally
grounded is every component: the calibration mapping, the Brier decomposition, the conformal
interval and the drift statistic each have their own known-answer tests above. The model itself is
gated, not validated: it must beat climatology on Brier skill on held-out data, and a synthetic
fixture with a known logistic generating process must recover coefficients within tolerance and
attain near-zero ECE. The recovery test is a construction, not an external truth, and is labelled
so in the Method Card.

---

### `risk.member_disengagement_risk`

Same machinery over `MemberSpell[]` and `EngagementFeatures[]`, predicting lapse within the horizon.
Same gates, same failure behaviour. Additional check `survival-consistency`: the model's aggregate
predicted lapse rate over the horizon must agree with `survival.churn_curve` at the same horizon
within its Greenwood band. Two of our own services disagreeing is a bug, and a platform whose selling
point is correctness should catch that automatically. **Non-blocking WARN**, since a genuine
covariate effect can create a legitimate gap, but always shown.

**known answer** as above, plus the cross-service consistency check, which is an internal invariant
rather than external truth and is labelled so.

---

## `conformal.py`

### `conformal.split_conformal_interval`

| | |
|---|---|
| **input** | `calibration_residuals, point_prediction, *, alpha: float = 0.1` |
| **output** | `scalar` prediction with `interval_kind="conformal-90"`. |
| **min_n** | **`ceil(1/alpha) - 1`, so 9 for 90% coverage, as a mathematical floor, but the practical floor is 100.** At n = 9 the guarantee holds but the interval is the whole range. The service reports `insufficient_data` below 100 and the Method Card explains that the guarantee and the usefulness have different thresholds, which is an unusually honest thing to state and worth stating. |

**assumptions** exchangeability of the calibration set and the new point. Not independence, not
normality, not a correct model. Exchangeability, and nothing else.

**checks** `exchangeability-time-drift` (compares the residual distribution in the first and second
half of the calibration set by KS; a drifting residual distribution breaks exchangeability and the
coverage guarantee goes with it. WARN, escalating to FAIL if the KS p-value is below 0.01),
`calibration-size`.

**method card**
- *assumes:* exchangeability. That is the entire assumption and it is why this method is used for resident-facing ETAs instead of a model-based interval.
- *wrong_when:* the process changed during the calibration window; the calibration set was filtered by outcome, which is the censoring trap and is handled by `conformal.survival_eta_bound` instead.
- *interval_meaning:* **marginal** coverage of at least 90%: across many requests, at least 90% of true values fall inside. It does **not** promise 90% for this particular category. Conditional coverage is what `conformal.mondrian_eta` provides, at a cost in width. The UI copy says "9 times out of 10" and links here.
- *references:* Vovk, Gammerman and Shafer (2005). Lei, G'Sell, Rinaldo, Tibshirani and Wasserman (2018) JASA 113:1094.

**known answer** A theorem, which is the strongest form of ground truth available. Split conformal
guarantees `1 - alpha <= coverage <= 1 - alpha + 1/(n+1)`. The test draws from an arbitrary,
deliberately non-Gaussian, heteroskedastic generating process at a fixed seed and asserts empirical
coverage over 10,000 held-out points falls inside those two bounds within binomial tolerance. It also
asserts the upper bound, which catches an over-conservative implementation that a coverage-only test
would pass.

---

### `conformal.survival_eta_bound`

| | |
|---|---|
| **streams** | `RequestSpell[]` |
| **input** | `spells, window, *, covariates, alpha: float = 0.1, seed: int` |
| **output** | `structure`: `{"lower_days", "upper_days", "point_days", "coverage_target"}` per request. `interval_kind="conformal-90"`, `unit="days"`. |
| **min_n** | 200 spells with at least 100 observed events. |

**This is the resident-facing ETA, and it is the hardest thing in Pack 3 to get right.** Standard
split conformal on the resolved subset is invalid here, because the calibration set is exactly the
fast requests. Exchangeability fails in the direction that makes the ETA look good, which is the
worst possible direction. The service therefore uses **conformalized survival analysis**: weighting
calibration scores by the inverse probability of not being censored, which restores a valid, if
conservative, lower predictive bound under a covariate-dependent censoring model.

**checks**
- `censoring-model-fit`: the censoring model's own calibration. **Blocking**, since the weights
  depend on it.
- `censoring-independent-given-covariates`: the assumption the weighting requires. Tested by
  comparing censored and observed covariate distributions after weighting.
- `coverage-backtest`: rolling-origin empirical coverage on past requests. **Blocking below
  `1 - alpha - 0.05`.** The guarantee is theoretical; this checks it held on this tenant's data.
- `exchangeability-time-drift`, as split conformal.

**on failure** Any blocking failure and no ETA is shown to the resident. The request page shows the
category's Kaplan-Meier curve instead, which is honest and still informative. **A wrong ETA shown to
a resident is the single most damaging output this platform can produce**, because it is the one a
non-expert will trust and quote, so the bar to display one is the highest in the catalog.

**method card**
- *assumes:* censoring is independent of the resolution time given the covariates; the censoring model is well calibrated; exchangeability of requests within the calibration window.
- *wrong_when:* an admin bulk-closes stale tickets, breaking the censoring model; the category was newly introduced and has no history; a step change in staffing occurred inside the calibration window.
- *interval_meaning:* a distribution-free lower predictive bound with at least 90% marginal coverage. Deliberately conservative: it will more often be too wide than too narrow, and the Method Card says which direction it errs in, because a resident is entitled to know whether the promise is optimistic or cautious.
- *references:* Candes, Lei and Ren (2023) JRSS-B, *Conformalized survival analysis*. Vovk et al. (2005).

**known answer** The coverage theorem again, under censoring. The test simulates from a known joint
distribution of event and censoring times at a fixed seed, holds out points, and asserts empirical
coverage of the lower bound is at least `1 - alpha` within binomial tolerance. A second test is the
one that matters most in practice: **the naive resolved-only bound must under-cover on the same
fixture**, and the test asserts that it does, so the fixture proves the correction is doing work
rather than merely not breaking. On the shipped fixture (lognormal waits, exponential censoring,
43% still open) the naive 90% bound covers **76%** of true waiting times while the censoring-aware
bound covers **90%**: a fourteen point shortfall, in the direction that flatters the ETA.

> *Clarified during implementation.* The under-coverage is a property of the **upper** bound, the
> "resolved within X days" figure a naive implementation would ship, because dropping open tickets
> removes exactly the slow ones. For the **lower** bound the naive subset errs conservative
> instead. Under right censoring the data is informative about short waits and systematically
> missing about long ones, so no distribution-free upper bound exists at all; the service therefore
> guarantees the lower bound (Candes, Lei and Ren) and reports the point and upper figures from the
> censoring-aware Kaplan-Meier estimate, labelled model-based. A resident is entitled to know which
> half of the promise is underwritten by a theorem.

---

### `conformal.mondrian_eta`

Class-conditional conformal, with `category` (or `priority`, or `location_ref`) as the taxonomy.
Gives coverage **within each class**, which is what a resident actually cares about, at the cost of
needing `>= 100` calibration points per class. Classes below the floor fall back to the marginal
interval, with the fallback disclosed per row. **known answer** the class-conditional coverage
theorem: coverage holds within each class, asserted per class on a seeded simulation, plus the
assertion that marginal conformal *fails* per-class coverage on a fixture with heterogeneous class
difficulty. Again, the negative control is the point.

---

## `drift.py`

### `drift.psi`

| | |
|---|---|
| **input** | `reference, current, *, bins: int = 10, binning: "quantile" = "quantile"` |
| **output** | `table` per feature: `{"feature", "psi", "verdict", "top_shifted_bin"}`. `interval_kind="none"`; PSI is a descriptive divergence, not an estimate, and giving it an interval would misrepresent it. |
| **min_n** | 200 in each of the reference and current windows, and 20 per bin, else bins are merged and the merge is disclosed. |

The reference distribution is **not stream data**. It is an artifact of a previous fit, supplied by
the caller (spine §8). `stats/` does not fetch it.

**checks** `bins-populated`, `reference-age` (WARN if the reference is older than the pack's refit
cadence, since a stale reference makes everything look drifted).

**method card**
- *assumes:* the same binning applied to both windows, derived from the reference quantiles, not recomputed on the current data. Recomputing the bins on the current data is the standard implementation bug and makes PSI approximately zero always.
- *wrong_when:* the feature is categorical with rare levels; the sample size differs by an order of magnitude between windows.
- *interval_meaning:* none. The conventional thresholds are 0.1 for "investigate" and 0.25 for "significant shift", and they are conventions from credit scoring, not derived from any distribution. The Method Card says exactly that, because a threshold presented as if it were a p-value is a small lie.
- *references:* Siddiqi, *Credit Risk Scorecards* (2006), which is the origin of the 0.1 / 0.25 convention.

**known answer** Exact and hand-computable: PSI of a distribution against itself is 0 exactly; PSI
between two specified discrete distributions equals the hand-computed
`sum((a_i - b_i) * ln(a_i / b_i))`, asserted to 1e-12 on several small cases. PSI is symmetric,
which is also asserted.

---

### `drift.ks_test`

Two-sample Kolmogorov-Smirnov per continuous feature, with a Holm correction across features
because testing 30 features at 0.05 guarantees a false alarm. **known answer** the exact KS
statistic for two specified empirical distributions is hand-computable as the maximum absolute
difference of the empirical CDFs, asserted exactly; and the asymptotic p-value is checked against
the Kolmogorov distribution's published critical values (D at n = 100, alpha = 0.05 is 0.1358).

---

### `drift.label_shift`

Base-rate comparison between the fitting window and the current window, with a Wilson interval on
each rate and on the difference. Cheap, and it catches the most consequential drift: a risk model
fitted when 12% of dues were late is meaningless once 30% are. **Blocking** input to
`risk.late_payment_risk` when the rates differ by more than the model's calibration tolerance.
**known answer** the Wilson interval has a closed form, written out independently in the test and
checked exactly; the difference interval is checked against Newcombe's method 10 **construction**,
`lower = d - sqrt((p1 - l1)^2 + (u2 - p2)^2)` and `upper = d + sqrt((u1 - p1)^2 + (p2 - l2)^2)`,
recomputed in the test from the two Wilson intervals, plus the property that swapping the groups
negates and reverses the interval.

> *Corrected during implementation.* This entry originally named Newcombe's published worked
> examples. The paper is not vendored and the implementation environment has no network access, so
> asserting a number recalled rather than read would be worse than asserting the algebra. The
> construction check is what the tests actually do.

---

# Pack 4: Governance, Segmentation & Text

**Pack id:** `governance_insight` · **Required streams:** `decision`, `participation`, `signal`
(plus `member_lifecycle` for every denominator) · **Default cadence:** on close for decisions,
weekly for segmentation and network, on submission for near-duplicate detection.

Two rules run through this whole pack.

> **Disclosure over tidiness.** A Condorcet cycle, a failed proportional-odds assumption, a 12%
> turnout: each of these is the finding. Hiding a cycle behind whichever tie-break happens to fire
> is the governance equivalent of dropping open tickets.

> **k-anonymity is a floor, not a setting.** Every per-stratum figure in this pack passes through
> `privacy.k_anonymity_suppress` before it can leave. There is no admin override, because a
> per-block vote breakdown over nine households identifies those households and the admin asking
> for it is precisely the risk.

---

## `voting.py`

### `voting.pairwise_matrix`

| | |
|---|---|
| **streams** | `Ballot[]`, `DecisionOption[]` |
| **input** | `ballots, options, *, unranked: "last" \| "excluded" = "last"` |
| **output** | `structure`: `{"options", "matrix", "margins", "n_ballots", "n_truncated"}` where `matrix[i][j]` is the count of ballots ranking i above j. `interval_kind="none"` because this is an exact count of the ballots cast, not an estimate of anything. |
| **min_n** | 1 ballot. It is a tabulation. The floor that matters is the *quorum* rule, which is a governance question checked by `voting.turnout_representativeness`, not a statistical one. |

**checks** `ballot-validity` (duplicate options within a ballot, options not on the ballot paper;
invalid ballots are excluded, counted in `n_excluded`, and the reason stated), `truncation-share`
(how many ballots ranked only some options, since the `unranked` policy materially changes the
matrix and is in `params_hash`).

**known answer** The Tennessee state-capital example (Memphis 42%, Nashville 26%, Chattanooga 15%,
Knoxville 17%), the standard worked case used across the social-choice literature and reproduced in
every Condorcet reference. Its pairwise matrix is published and asserted cell by cell.

---

### `voting.condorcet_winner`

| | |
|---|---|
| **output** | `structure`: `{"winner": str \| None, "cycle": [...] \| None, "smith_set": [...], "matrix_ref"}`. `interval_kind="none"`. |
| **min_n** | as above. |

**checks** `condorcet-cycle-present`: **not blocking, and deliberately not an error.** When a cycle
exists there is no Condorcet winner, and the service returns `winner=None` with the cycle
enumerated and the Smith set named. The UI is required to render the cycle, in words, above any
result produced by a completion rule. `pairwise-ties` is reported separately since an even
electorate produces exact ties that break naive implementations.

**method card**
- *assumes:* ballots are rankings; unranked options are handled by the declared policy.
- *wrong_when:* a cycle exists and a tool reports a winner anyway. That is the failure this service exists to prevent, and the Method Card names it as the intended reading.
- *interval_meaning:* none. Exact combinatorics on the ballots cast. Uncertainty about the *electorate*, as distinct from the ballots, is `voting.turnout_representativeness`, and the two must not be conflated.
- *references:* Condorcet (1785). Smith (1973) Econometrica 41:1027 for the Smith set.

**known answer** Two textbook cases, both required by `docs/RULES.md` §7. The Tennessee example
yields Nashville as the Condorcet winner. The **deliberate cycle**, three voters with A>B>C, B>C>A,
C>A>B, must yield `winner=None`, a cycle of all three, and a Smith set of all three. The second
test is the one that matters and it is a hard requirement for shipping the pack.

---

### `voting.schulze`

| | |
|---|---|
| **output** | `structure`: `{"ranking", "strongest_paths", "winner", "is_condorcet_winner", "cycle_disclosed"}`. |
| **min_n** | as above. |

Schulze is the platform default for single-winner decisions because it is Condorcet-consistent and
always produces a complete ranking, including when a cycle exists. **When a cycle exists, the
Schulze winner is still shown but is labelled as the resolution of a cycle rather than as a
Condorcet winner**, and the cycle is displayed alongside. The distinction is the entire point.

**checks** `condorcet-cycle-present` inherited; `schulze-tie` (the beatpath relation can still tie,
and the tie-break is the declared one from `DecisionSpec`, disclosed rather than silent).

**method card**
- *assumes:* the declared rule was Schulze before ballots were cast (spine rule D1).
- *wrong_when:* a committee sees the Schulze result and then argues for Borda instead. The platform will compute Borda and show it, but labels the declared rule's result as binding.
- *interval_meaning:* none.
- *references:* Schulze (2011) Social Choice and Welfare 36:267.

**known answer** Schulze's own paper contains a fully worked 45-voter, 5-candidate example (A to E)
with the published strongest-path matrix and the published final ranking E > A > C > B > D. Asserted
against the path matrix, not only the winner, because a wrong implementation frequently gets the
winner right by luck.

---

### `voting.borda`, `voting.approval`, `voting.score`

Exact tabulations, reported **alongside** the declared rule so a committee can see how sensitive the
outcome is to the rule. That sensitivity display is a real product feature: "under every rule we
computed, option B wins" is a much stronger mandate than a bare winner, and "the winner changes
under three of five rules" is a warning a community deserves.

Each carries the unranked/abstention policy in `params_hash`. **known answer** the Tennessee example
again, asserted on the published Borda totals: Nashville 194, Chattanooga 173, Memphis 126,
Knoxville 107. Note that Borda **agrees** with the Condorcet winner here; it is the
**first-preference** count that differs, giving Memphis on 42%. That, not a Borda/Condorcet split,
is the sensitivity finding the Tennessee example is famous for, and the earlier wording of this
line had it wrong. The example publishes rankings and no approval sets, so the approval figure is
asserted under a stated top-two derivation, labelled in the test as a derivation rather than as a
published result.

---

### `voting.stv`

| | |
|---|---|
| **input** | `ballots, options, *, seats: int, quota: "droop" \| "hare" = "droop", transfer: "gregory" \| "meek" = "gregory", tie_break_seed: int` |
| **output** | `structure`: `{"elected", "rounds": [{"round", "counts", "elected_this_round", "eliminated", "transfers"}], "quota"}`. Every round is returned, because in an STV election the count *is* the accountability. |
| **min_n** | `seats + 1` options and at least `seats` valid ballots. |

**checks** `quota-reached` (candidates elected without reaching quota at the final stage, which is
normal and must be labelled), `tie-break-invoked` (**always disclosed**; the seed is in
`params_hash` so a contested election can be recounted identically), `exhausted-ballots` (share of
ballots exhausted before the last seat, which is the quality measure for an STV count).

**method card**
- *assumes:* the transfer method and quota were declared in advance; ties are broken by the declared seeded rule.
- *wrong_when:* the transfer method is changed after the fact; ballots are truncated heavily, so many exhaust and the last seat is decided by a small remnant, which the exhausted-ballot share exposes.
- *interval_meaning:* none. STV is non-monotonic, so an interval would be meaningless even in principle, and the Method Card says so.
- *references:* Tideman (1995) J. Economic Perspectives 9:27. ERS97 rules for the Gregory transfer. Meek (1969) for the Meek variant.

**known answer** A published STV count with a documented round-by-round result: the standard
food-election worked example used in Wikipedia and Electoral Reform Society material, with published
Droop quota, elimination order and final seat allocation. Asserted round by round rather than on the
final seats, since a wrong transfer rule often lands on the right seats.

---

### `voting.turnout_representativeness`

| | |
|---|---|
| **streams** | `Ballot[]`, `DecisionSpec.eligible_strata`, `RosterSnapshot` |
| **output** | `structure`: `{"turnout", "turnout_lo", "turnout_hi", "by_stratum": [rows with own n and interval], "chi_square", "p_value", "design_effect_if_weighted"}`. `interval_kind="normal-95"` on turnout (Wilson), `"none"` on the test. |
| **min_n** | 30 ballots for the aggregate, and the tenant's `k` per stratum row. |

**checks** `quorum-met` (against `DecisionSpec.quorum_rule`; **blocking on any claim that the
decision is binding**, though not on the tabulation itself), `strata-representative` (chi-square of
voters against eligible population), `k-anonymity-cells` (**blocking per row**),
`low-turnout-generalisation` (**blocking on any population-level claim** when turnout is below 30%:
the result describes the people who voted and the platform will not phrase it as a community
preference. The tabulation is still shown; the *generalisation* is what is blocked).

**method card**
- *assumes:* the eligible frame was frozen at `opened_at` and is accurate.
- *wrong_when:* someone reads "68% of votes favoured the proposal" as "68% of the community favours the proposal" at 12% turnout. That inference needs `survey.raking_weights` and a design effect, and even then it is weak. This check exists because that sentence is the single most common misuse of a community poll.
- *interval_meaning:* Wilson interval on the turnout proportion. The per-stratum rows carry their own.
- *references:* Kish, *Survey Sampling* (1965). Wilson (1927).

**known answer** Wilson intervals have a closed form and are asserted exactly against published
worked values (Wilson's own tabulated cases and the Newcombe (1998) comparison paper). The
chi-square goodness-of-fit against known expected counts is hand-computable and asserted exactly.

---

## `budgeting.py`

### `budgeting.method_of_equal_shares`

| | |
|---|---|
| **streams** | `Ballot[]` (approval or allocation style), `DecisionOption[]` with `cost_minor`, `DecisionSpec.budget_minor` |
| **input** | `ballots, options, budget_minor, *, completion: "add1" \| "none" = "add1"` |
| **output** | `structure`: `{"funded", "not_funded", "spent_minor", "remaining_minor", "per_voter_spend", "rounds"}`. `interval_kind="none"`. |
| **min_n** | 20 ballots and 3 options. Below that the proportionality guarantee is vacuous, since one voter's budget share funds nothing. |

**checks** `budget-exhausted`, `ejr-satisfied` (the extended justified representation property is
verified computationally on the actual result, **blocking if violated**, because a violation is an
implementation bug and MES's whole reason for existing is that guarantee), `completion-rule-applied`
(MES can leave budget unspent; the completion method is declared and disclosed).

**method card**
- *assumes:* each voter has an equal share of the budget; approvals express genuine support rather than strategic bundling.
- *wrong_when:* options have wildly unequal costs and voters approve indiscriminately; the same physical project is split into several options to game the rule, which the fairness report will show as one stratum capturing a disproportionate share.
- *interval_meaning:* none. It is an allocation rule, not an estimate.
- *references:* Peters and Skowron (2020) EC'20. Peters, Pierczynski and Skowron (2021) NeurIPS. The equalshares.net reference instances.

**known answer** The worked instances published with the Method of Equal Shares papers and on
equalshares.net, whose funded sets are given explicitly. Plus the property test: on randomly
generated seeded instances, EJR must hold for MES and must be *violated* by
`budgeting.greedy_knapsack` on at least the constructed counterexample instance from the literature.
The negative control matters: it proves the property checker works.

---

### `budgeting.greedy_knapsack`

Utilitarian baseline: maximise total approvals per unit cost. Shipped **alongside** MES, never
instead of it, so a committee sees the trade-off between total satisfaction and proportional
fairness explicitly. **known answer** exact dynamic-programming optimum on small instances, and the
1/2-approximation bound against it, checked for a counterexample across 200 seeded instances.
**Correction:** density greedy *on its own* has no constant-factor guarantee, so the shipped rule
is the standard max of density greedy and the best single affordable project, which is the variant
the 1/2 bound belongs to. Which of the two was served is disclosed in a check.

---

### `budgeting.fairness_report`

| | |
|---|---|
| **output** | `table`, one row per stratum: `{"stratum", "n_voters", "share_of_electorate", "share_of_budget_won", "utilisation", "lo", "hi"}`. `interval_kind="bootstrap-bca-95"` on utilisation, seeded. |
| **min_n** | tenant `k` per stratum row, strictly enforced; strata below it are pooled into "other" and the pooling is stated. |

**This is the output that makes participatory budgeting trustworthy** rather than a majority tool
with extra steps. It answers "did Block C, who are 11% of the society, get any of their preferences
funded" with a number and an interval.

**checks** `k-anonymity-rows` (**blocking per row**), `strata-coverage` (share of voters in pooled
strata), `proportionality-gap` (largest absolute gap between electorate share and budget share).

**known answer** The utilisation identity is exact arithmetic on the allocation. The interesting
assertion is a property test: under MES, no stratum with more than a proportional share of voters
may receive less than its proportional share of budget by more than the cost of the cheapest
unfunded project they approved. That bound follows from the MES guarantee and is asserted on seeded
random instances.

---

## `sortition.py`

### `sortition.stratified_panel`

| | |
|---|---|
| **streams** | `RosterSnapshot`, volunteer pool |
| **input** | `pool, quotas: Mapping[stratum, (lo, hi)], panel_size, *, seed: int, objective: "maximin" \| "leximin" = "maximin"` |
| **output** | `structure`: `{"panel", "quota_satisfaction", "selection_probabilities", "min_probability", "max_probability"}`. `interval_kind="none"` on the panel; `selection_probabilities` carry Monte Carlo intervals from the seeded lottery. |
| **min_n** | a pool at least 3x the panel size, and every quota's lower bound must be satisfiable from the pool. |

**checks** `quotas-feasible` (**blocking**; infeasible quotas return the binding constraint rather
than a panel that quietly ignores one), `probability-floor` (the minimum selection probability
across the pool, since the fairness of sortition is precisely that everyone had a real chance and a
naive quota-filling algorithm can give some volunteers a probability near zero),
`pool-representativeness` (how the volunteer pool differs from the roster, which sortition cannot
fix and must therefore disclose).

**method card**
- *assumes:* the volunteer pool is the sampling frame. Sortition makes the *panel* representative of the *pool*, not of the community, and if the pool is skewed the panel inherits the skew. This is the most misunderstood property of citizens' assemblies and it leads the Method Card.
- *wrong_when:* the pool self-selected heavily; quotas are so tight only one panel is feasible, which makes the lottery ceremonial.
- *interval_meaning:* Monte Carlo intervals on the per-person selection probability, from the seeded lottery distribution.
- *references:* Flanigan, Golz, Gupta, Hennig and Procaccia (2021) Nature 596:548, *Fair algorithms for selecting citizens' assemblies*.

**known answer** Two grounds. Exact: on a seeded run, all quotas are satisfied and the result is
reproducible bit for bit from the seed. Analytic: on an instance where an equal-probability
selection is feasible, the maximin objective must attain exactly `panel_size / pool_size` for every
member, which is a provable optimum and is asserted within Monte Carlo tolerance over many seeded
draws.

---

## `survey.py`

### `survey.likert_distribution`

| | |
|---|---|
| **streams** | `OrdinalResponse[]` |
| **input** | `responses, *, item_id, group_by: str \| None = None` |
| **output** | `structure`: `{"counts_by_level", "proportions", "median", "iqr", "top_box", "bottom_box", "cliffs_delta_vs_reference", "lo", "hi"}`. `interval_kind="bootstrap-bca-95"` on the proportions and on Cliff's delta. **There is no `mean` key. The shape does not have one.** |
| **min_n** | 20 responses per item, tenant `k` per group row. |

Reporting the mean of a 1 to 5 Likert item is the mistake this service exists to prevent, and the
prevention is structural: the returned `structure` has no field a mean could live in, exactly as
`TextDoc` has no field an identity could live in.

**checks** `scale-consistent` (all responses share `scale_min`/`scale_max`; **blocking** if a 1 to 5
and a 1 to 7 item were pooled, which happens constantly in real survey data), `floor-ceiling`
(more than 60% in the top or bottom box means the item cannot discriminate and comparisons across
groups will be driven by the bound), `k-anonymity-cells` (**blocking per row**).

**method card**
- *assumes:* the levels are ordered but not equally spaced. The gap between "poor" and "fair" is not the gap between "good" and "excellent", which is why the mean is meaningless and the median plus the full distribution is not.
- *wrong_when:* two groups are compared by mean difference; a change from 3.8 to 4.0 is reported as an improvement.
- *interval_meaning:* bootstrap intervals on each proportion. Cliff's delta is a probability-of-superiority effect size: 0.3 means a randomly chosen member of group A rates higher than a randomly chosen member of group B about 65% of the time.
- *references:* Jamieson (2004) Medical Education 38:1217 on Likert misuse. Cliff (1993) Psychological Bulletin 114:494.

**known answer** Cliff's delta has an exact closed form as a count of dominance pairs and is
hand-computable on small vectors, asserted exactly. Its relationship to the Mann-Whitney U statistic,
`delta = 2U/(mn) - 1`, is an identity and is asserted against a reference U computation.

---

### `survey.ordinal_logistic`

| | |
|---|---|
| **streams** | `OrdinalResponse[]` |
| **input** | `responses, *, item_id, covariates, link: "logit" = "logit", alpha = 0.05` |
| **output** | `table`, one row per covariate: `{"covariate", "coef", "odds_ratio", "lo", "hi", "p_value"}`, plus the cutpoints in a `structure`. `interval_kind="profile-95"`, `unit="proportional odds ratio"`. |
| **min_n** | 10 responses per covariate **per level of the response with fewer than 10% mass**, in practice 100 responses for 3 covariates. Ordinal models are estimated from the sparsest cutpoint, and reporting the events-per-variable rule on the total n hides that. |

**checks**

| id | tests | blocking |
|---|---|---|
| `proportional-odds` | Brant test, per covariate and globally. | **yes, per covariate** |
| `sparse-levels` | any response level with fewer than 5 observations; adjacent levels are merged and the merge disclosed. | no |
| `separation` | a covariate perfectly predicting a level. | **yes** for that row |
| `k-anonymity-cells` | per-covariate cell counts. | **yes** |

**on failure** A proportional-odds failure is the direct analogue of a Schoenfeld failure in Cox.
The odds ratio is not a single number across cutpoints and the platform must not print one as if it
were. The row is suppressed and replaced with the partial-proportional-odds alternative, showing the
per-cutpoint effects, which is longer to read and correct.

**method card**
- *assumes:* proportional odds, so the effect of a covariate is the same at every cutpoint of the scale; independent responses; the ordinal levels are correctly ordered.
- *wrong_when:* a covariate moves people out of "very dissatisfied" but does nothing at the top of the scale, which is a proportional-odds violation and is common with satisfaction data; responses are clustered by household and treated as independent, which understates the standard errors.
- *interval_meaning:* a profile-likelihood interval on the proportional odds ratio, multiplicative, with 1.0 as no effect.
- *references:* McCullagh (1980) JRSS-B 42:109. Brant (1990) Biometrics 46:1171. Venables and Ripley, *MASS*, 4th ed., §7.3.

**known answer** **Corrected.** The `MASS::polr` housing-satisfaction example is the canonical
published fit, but its 72-row frequency table is not vendored under
`backend/tests/unit/stats/data/` and there is no network access in the build, so citing it would be
a known answer nothing checks. Three things are asserted instead, all of which the tests actually
run. **Recovery:** 1200 draws from a proportional-odds model with stated coefficients and
cutpoints, every parameter recovered within three standard errors. **Reduction:** with two response
levels the model *is* logistic regression, and the fit agrees with `numeric.logistic_l2_fit` to
under 1e-6 on both the slope and the cutpoint, which is a second implementation in this repository
rather than a restatement of this one. **The Brant test in both directions:** it must pass on data
generated with a constant effect and fail on data generated with a cutpoint-varying one, and on the
second it must fail *only* for the covariate that actually varies.

---

### `survey.raking_weights`

| | |
|---|---|
| **streams** | `OrdinalResponse[]` or `Ballot[]`, plus `RosterSnapshot` |
| **input** | `respondent_strata, population_margins, *, max_iter: int = 100, tol: float = 1e-6, trim: tuple[float, float] = (0.2, 5.0)` |
| **output** | `table` of weights per respondent plus a `structure` with the achieved margins and the number of iterations. |
| **min_n** | 50 respondents, and at least 5 respondents in every cell being raked. **A cell with zero respondents cannot be raked and the service says which cell rather than silently dropping the margin.** |

**checks** `convergence` (**blocking**; non-convergence means the margins are inconsistent),
`extreme-weights` (weights outside the trim bounds are trimmed and the trimming disclosed, since a
weight of 40 means one person is speaking for forty and the estimate is that person's opinion),
`empty-cells` (**blocking**, naming the cell), `design-effect-acceptable` (WARN above 2.0).

**method card**
- *assumes:* the population margins are correct; non-response is ignorable *within* the raking cells, which is the assumption that actually carries the inference and is untestable from the sample alone.
- *wrong_when:* the people who did not respond differ from the people who did in a way not captured by the raking variables. Raking fixes composition, never motivation.
- *interval_meaning:* the weights themselves have none. All downstream estimates use the design effect to widen their intervals, and `survey.design_effect` reports it.
- *references:* Deming and Stephan (1940) Annals of Mathematical Statistics 11:427. Kolenikov (2014) Stata Journal 14:22.

**known answer** Iterative proportional fitting converges to margins exactly, which is a theorem
(Deming and Stephan), so the test asserts the achieved margins match the targets to within `tol` on
several seeded random tables. **Corrected second ground truth:** R `survey::rake` is not available
in this build, so the replacement is a closed form rather than another library. With a single
margin, raking reduces exactly to post-stratification, whose weight is `N_h / n_h` rescaled to `n`;
on 40 respondents from block A and 20 from block B against a half-and-half population the weights
must be exactly 0.75 and 1.5, and they are asserted to 1e-9.

---

### `survey.design_effect`

Kish's design effect, `deff = n * sum(w^2) / (sum(w))^2`, and the effective sample size
`n_eff = n / deff`. Reported next to every weighted estimate. **The whole reason it exists** is so
"340 residents were surveyed, weighted" becomes "effective sample size 96", which is the number that
should be in the reader's head.

**known answer** Exact closed form, hand-computable, asserted to 1e-12. Equals exactly 1 for uniform
weights, for *any* constant weight and not only for 1. **Corrected:** Kish's tabulated worked case
is not vendored here, so the second assertion is a hand computation written out in the test
instead: weights (1, 1, 1, 3) give `deff = 4 * 12 / 36 = 4/3` and an effective sample size of
exactly 3.

---

## `segmentation.py`

### `segmentation.rfm_features`

Deterministic transform from `ParticipationEvent[]` and `LedgerEntry[]` to `EngagementFeatures[]`.
`interval_kind="none"`, `min_n=1`; it is a feature builder, not an estimator, and it returns
`Evidence` only because everything crossing the boundary does. **known answer** exact arithmetic on
a fixture, including the boundary cases: a member with no participation gets `recency_days` equal to
their tenure, not `None` and not zero.

---

### `segmentation.gmm_select_k`

| | |
|---|---|
| **streams** | `EngagementFeatures[]` |
| **input** | `features, *, k_range: range = range(2, 9), covariance: "full" \| "diag" = "diag", n_init: int = 10, seed: int, scale: "robust" = "robust"` |
| **output** | `structure`: `{"k", "bic_by_k", "silhouette_by_k", "labels", "centroids", "sizes", "separation"}`. `interval_kind="none"` on the labels; a bootstrap stability score is returned instead, which is the meaningful uncertainty for a clustering. |
| **min_n** | **50 members.** Below that, cluster structure is indistinguishable from noise and BIC will still confidently return a k. Evidence contract §8. |

**checks**
- `k-selection-agreement`: BIC and silhouette disagreeing on k is itself the finding, reported
  rather than resolved by picking one. WARN, showing both curves.
- `cluster-stability`: seeded bootstrap adjusted Rand index across resamples. **Blocking below
  0.5**, because a clustering that does not survive resampling is a drawing, not a segmentation.
- `singleton-clusters`: any cluster below the tenant `k` is merged. **Blocking per cluster.**
- `feature-scaling`: robust scaling is mandatory since volunteer hours and login counts differ by
  orders of magnitude and an unscaled GMM clusters on the largest-variance feature alone.

**method card**
- *assumes:* clusters are roughly elliptical in the scaled feature space; k is fixed across the run; features are comparable after scaling.
- *wrong_when:* the true structure is a continuum, which engagement usually is, so the clusters are cuts through a gradient and will move between months. The stability score is what tells you whether that happened, and it is shown next to the segments always.
- *interval_meaning:* none on labels. The stability index is the honest uncertainty measure and the Method Card explains how to read it.
- *references:* Schwarz (1978) for BIC. Rousseeuw (1987) J. Comp. Applied Math 20:53 for silhouette. Hennig (2007) on cluster stability by resampling.

**known answer** Synthetic: data drawn from a 3-component Gaussian mixture with a specified
separation must have BIC minimised at k = 3, seeded and repeated, and the fitted component means
must land within 0.5 of the generating ones. **Corrected:** the `iris` silhouette result is a real
published fact but `iris` is not vendored under `backend/tests/unit/stats/data/` and 150 rows
cannot be reconstructed from memory, so it is replaced by an exact closed form. Silhouette on a
four-point fixture on a line has a hand-computable value, `(9.5/10.5 + 8.5/9.5) / 2`, asserted to
1e-12, and a single cluster scores exactly 0 by definition. The adjusted Rand index is asserted the
same way: exactly 1 for a relabelling, exactly 0 for the all-in-one partition.

---

### `segmentation.stable_labels`

Aligns this month's cluster labels to last month's by Hungarian matching on centroids, so
"Segment 3" means the same thing in September as in August. Returns the mapping, the match cost, and
a `label-drift` check that FAILs blocking when the best match cost exceeds a threshold, meaning the
segments genuinely changed and pretending they are the same ones would be worse than renumbering.

**known answer** Exact: a fixture whose labels are a known permutation of the reference must be
mapped back to the identity, and a fixture whose centroids genuinely moved must trigger the drift
check. The negative control is again the point.

---

## `network.py`

### `network.louvain_communities`

| | |
|---|---|
| **streams** | `InteractionEdge[]` |
| **input** | `edges, *, resolution: float = 1.0, seed: int, min_component_size: int = 3` |
| **output** | `structure`: `{"communities", "modularity", "sizes", "n_isolated", "resolution"}`. `interval_kind="none"` on the partition; a seeded stability score across restarts is returned. |
| **min_n** | 30 nodes and 60 edges. Below that, modularity maximisation finds structure in random graphs reliably, which is a documented pathology, not a feature. |

**checks**
- `modularity-vs-null`: the observed modularity against a configuration-model null, seeded.
  **Blocking if the observed partition is not better than the null**, because Louvain returns a
  partition of a random graph without complaint and reporting it as community structure is fiction.
- `resolution-limit`: communities smaller than `sqrt(2 * n_edges)` are subject to the known
  resolution limit and are flagged as possibly merged.
- `partition-stability`: agreement across seeded restarts.
- `projection-declared`: the co-attendance normalisation constant from the spine is carried into the
  caveat, because a different normalisation gives a different graph.
- `k-anonymity-communities`: communities below the tenant `k` are not labelled or listed.

**method card**
- *assumes:* the interaction graph reflects real relationships. It does not: it reflects co-presence at events, which is a proxy and sometimes a poor one.
- *wrong_when:* one large event dominates the edge set; the resolution parameter was tuned until the number of communities looked plausible.
- *interval_meaning:* none. The stability and null-model comparison are the uncertainty statements.
- *references:* Blondel, Guillaume, Lambiotte and Lefebvre (2008) JSTAT P10008. Fortunato and Barthelemy (2007) PNAS 104:36 on the resolution limit.

**known answer** Zachary's karate club, the canonical benchmark: Louvain finds 4 communities with a
modularity of about 0.42, and the split separates the two known factions around nodes 0 and 33. All
three facts are published and asserted. Second ground truth: modularity itself has a closed form and
is asserted exactly for a hand-computed partition on a small graph.

---

### `network.betweenness_centrality`

Brandes' algorithm, normalised, with the top-`m` connectors returned. Members below the tenant `k` in
any reported grouping are suppressed. **known answer** exact closed forms on two graphs where
betweenness is analytically known: on a path graph of `n` nodes the betweenness of node `i` is
`i(n-1-i)`, and on a star the centre has normalised betweenness exactly 1 and every leaf exactly 0.
Plus the published karate-club values, where nodes 0 and 33 are the documented highest.

---

### `network.isolation_report`

| | |
|---|---|
| **output** | `structure`: `{"n_isolated", "isolated_share", "lo", "hi", "by_stratum": [...]}`. `interval_kind="normal-95"` (Wilson) on the share. **Individual isolated members are never returned by this service.** |
| **min_n** | 30 nodes; tenant `k` per stratum row. |

The design decision is deliberate and belongs in the Method Card: a list of socially isolated
individuals is the most sensitive output this platform could produce, and the aggregate share by
stratum is what a committee needs to act ("Block D is disconnected from the rest of the society")
without handing anyone a list of lonely neighbours. The service is shaped so the list cannot be
produced.

**known answer** Wilson interval closed form, exact; isolated-node counting is exact graph
arithmetic on a fixture.

---

## `text.py`

All text services take `TextDoc[]`, which has no identity field (spine §5). Embeddings arrive
precomputed; `stats/` never calls a model.

### `text.near_duplicate_candidates`

| | |
|---|---|
| **streams** | `TextDoc[]` |
| **input** | `docs, query_doc, *, threshold: float = 0.7, method: "minhash" \| "cosine" \| "both" = "both", n_permutations: int = 128, seed: int, window_days: int = 30` |
| **output** | `table`: `{"doc_ref", "similarity", "method", "at"}`, ordered. `interval_kind="none"` on the similarity, which is computed exactly for cosine; the MinHash estimate carries its own standard error and the Method Card gives it. |
| **min_n** | 1 candidate document. This runs at submission time on whatever exists, which is the point: "3 neighbours already reported this" is worth saying on day one. |

**checks** `minhash-error-bound` (the estimator's standard error at the given permutation count is
reported, and below 64 permutations the check WARNs because the estimate is too noisy to threshold),
`embedding-present` (falls back to token cosine and discloses the fallback),
`k-anonymity-authors` (the *count* of similar reports is shown; author identities are re-attached by
the service layer only above `k` and only to roles the manifest permits).

**method card**
- *assumes:* lexical or embedding similarity approximates semantic duplication. It does not always: "no water in B-402" and "no water in C-101" are lexically near-identical and are different problems, which is why `location_ref` is a hard filter before similarity, not a ranking feature.
- *wrong_when:* short texts (under 5 tokens) where Jaccard is dominated by one word; a recurring seasonal complaint is flagged as a duplicate of last year's.
- *interval_meaning:* none on cosine, which is exact. The MinHash estimate has a standard error of `sqrt(J(1-J)/k)`, about 0.04 at 128 permutations for J = 0.7, and that number is printed on the card.
- *references:* Broder (1997) on MinHash. Leskovec, Rajaraman and Ullman, *Mining of Massive Datasets*, ch. 3.

**known answer** Analytic, and unusually clean. Exact Jaccard is computable by definition on token
sets and is asserted exactly. The MinHash estimator is unbiased with variance `J(1-J)/k`, so the
test draws seeded permutations and asserts the estimate falls within three standard errors of the
exact Jaccard, and additionally asserts the *empirical variance across seeds* matches the analytic
variance. Cosine similarity is asserted against hand computation.

---

### `text.tfidf_similarity`

Exact sparse TF-IDF with declared sublinear scaling and smoothing, returning a similarity matrix or
top-k neighbours. **known answer** exact hand computation on a 3-document toy corpus, with the
smoothing convention stated: on `["a b"], ["a c"], ["a d"]` the idf of `a` is exactly 1 and of every
other token exactly `1 + log 2`, each row is L2-normalised, and the cosine between two documents is
exactly `(1 / sqrt(1 + (1 + log 2)^2))^2`. **Corrected:** the `sklearn` second oracle is dropped,
since scikit-learn is deliberately not a dependency of the light tier (see the Pack 1 decision on
the standard library) and a second oracle that is not installed is not one.

---

### `text.nmf_topics`

| | |
|---|---|
| **streams** | `TextDoc[]` |
| **input** | `docs, *, n_topics: int \| "auto", max_features: int = 5000, seed: int, init: "nndsvd" = "nndsvd"` |
| **output** | `structure`: `{"topics": [{"terms", "weights", "n_docs", "example_refs"}], "reconstruction_error", "coherence"}`. `interval_kind="none"`. |
| **min_n** | **200 documents and 30 per topic.** NMF on 40 complaint texts produces topics that are single documents with a label. |

**checks** `topic-coherence` (NPMI per topic; topics below threshold are not shown, since an
incoherent topic list destroys trust in everything next to it), `topic-stability` (agreement across
seeded restarts, **blocking below 0.5**), `k-anonymity-examples` (example documents are shown only
where the topic covers at least `k` distinct authors), `n-topics-selected` (when `"auto"`, the
selection curve is returned so the choice is visible).

**method card**
- *assumes:* documents are mixtures of a small number of additive term distributions.
- *wrong_when:* the corpus is dominated by one category, so NMF splits it into near-duplicates of itself; the vocabulary is small and topics collapse; the number of topics was chosen to look tidy.
- *interval_meaning:* none. Coherence and stability are the quality statements and both are always shown.
- *references:* Lee and Seung (1999) Nature 401:788. Boutsidis and Gallopoulos (2008) for NNDSVD initialisation. Bouma (2009) for NPMI coherence.

**known answer** **Partial, and stated plainly: there is no published topic-model fixture with
known-correct topics for this domain, and asserting against one would be inventing a ground truth.**
What is asserted: on a synthetic corpus generated from three specified topic-word distributions with
a fixed seed, NMF must recover those distributions up to permutation with cosine similarity above
0.9, and the reconstruction error must be below a bound derived from the known noise level. That is
a construction, not an external published number, and the Method Card labels it as such. The
coherence and stability metrics themselves have exact known answers and are tested separately.

---

## `privacy.py`

### `privacy.k_anonymity_suppress`

| | |
|---|---|
| **input** | `table_evidence, *, k: int, cell_counts, secondary: bool = True` |
| **output** | the same `table`-shaped `Evidence`, with rows below `k` suppressed and a `structure` note of what was suppressed and why. |
| **min_n** | not applicable; it is a filter, and it is the last thing every Pack 4 service calls. |

**checks** `complementary-suppression`: **the subtlety that makes this real.** Suppressing one cell
in a table whose total is published lets that cell be recovered by subtraction. When `secondary` is
on, the service suppresses additional cells until no suppressed value is uniquely determined by the
published ones, and reports how many extra cells that cost. **Blocking** if complementary
suppression is impossible without suppressing the whole table, in which case the whole table is
suppressed.

**method card**
- *assumes:* `k` is set correctly for the community's size and the sensitivity of the attribute.
- *wrong_when:* an attacker has background knowledge, which k-anonymity does not protect against; several tables are published over time and their differences reveal an individual, which is why `params_hash` and the suppression record are stored per run.
- *interval_meaning:* unchanged from the input envelope.
- *references:* Sweeney (2002) IJUFKS 10:557. Cox (1980) JASA 75:377 on complementary suppression.

**known answer** Exact rule verification: every published cell has count at least `k`, and a
constructed table where naive suppression leaks a cell by subtraction must trigger secondary
suppression. The leak fixture is the important test and it is a documented example from the
statistical disclosure control literature.

---

### `privacy.laplace_noise`

| | |
|---|---|
| **input** | `value, *, sensitivity: float, epsilon: float, seed: int, clamp: tuple \| None` |
| **output** | the noised value with `interval_kind` set to a DP-specific noise interval and a caveat stating epsilon, so a reader knows the figure is deliberately imprecise. |
| **min_n** | not applicable. |

**checks** `budget-accounting`: epsilon composes across every query on the same data, and the
service returns the epsilon it consumed so the caller can maintain a budget. **The budget itself is
the service layer's job**, but the accounting number comes from here. `sensitivity-declared`
(blocking if the caller did not state it, since an undeclared sensitivity means the noise is
arbitrary and the privacy claim is empty).

**method card**
- *assumes:* the declared sensitivity bounds the effect of one member on the statistic. A wrong sensitivity means no privacy guarantee at all, and it is the most common failure.
- *wrong_when:* the same statistic is queried repeatedly; noise is added to a figure that is also published exactly elsewhere.
- *interval_meaning:* the interval reflects added noise, not sampling uncertainty. A DP figure with a small n has both, and the caveat says the displayed interval is noise only.
- *references:* Dwork, McSherry, Nissim and Smith (2006) TCC. Dwork and Roth (2014), *The Algorithmic Foundations of Differential Privacy*.

**known answer** The Laplace mechanism with scale `sensitivity / epsilon` satisfies epsilon-DP, a
theorem. Tests: the empirical noise distribution over seeded draws matches Laplace with that scale
by KS test; the mechanism is unbiased, so the mean of many draws converges to the true value at the
known rate; sequential composition adds epsilons exactly; and the noised output is reproducible from
the seed.

---

## `audit.py`

### `audit.benford_digits`

| | |
|---|---|
| **streams** | `LedgerEntry[]` |
| **input** | `entries, *, digit: 1 \| 2 = 1, category: str \| None = None` |
| **output** | `table` of observed versus Benford-expected first-digit frequencies with a chi-square and a mean absolute deviation. `interval_kind="normal-95"` (Wilson) per digit row. |
| **min_n** | **300 entries**, and only for categories whose amounts span at least two orders of magnitude. Benford does not apply to a series of identical monthly maintenance dues, and applying it there produces a spectacular false positive. The service **refuses** rather than reports, with `insufficient_data` and that sentence as the caveat. |

**checks** `magnitude-span` (**blocking**), `bounded-amounts` (**blocking**: amounts with a natural
floor or cap, like a fixed dues amount, do not follow Benford), `not-a-fraud-test` (always present,
always a caveat, never removable: a Benford deviation is a prompt to look, not evidence of anything,
and the copy shown to the user says exactly that).

**method card**
- *assumes:* amounts arise from a process spanning several orders of magnitude and are not bounded or rounded.
- *wrong_when:* almost always in a small community ledger, which is why the two blocking checks come first and why this service is off by default in every vertical manifest.
- *interval_meaning:* Wilson intervals on the observed digit frequencies against the Benford expectation.
- *references:* Benford (1938). Nigrini, *Benford's Law* (2012). Cho and Gaines (2007) on its misuse.

**known answer** The Benford probabilities are a closed form, `log10(1 + 1/d)`, asserted exactly.
The chi-square against known counts is hand-computable and asserted. And a negative control: a
uniform digit distribution must be flagged, while a sample drawn from a genuine Benford process at a
fixed seed must not.

---

# Pack 2: Bayesian Ranking & Experimentation

**Pack id:** `bayes_ranking` · **Required streams:** `request_flow`, `participation`, `ledger` ·
**Default cadence:** nightly for rankings, hourly for live experiments, on demand for bandit
policy freezes.

Ships last, because empirical Bayes and bandits need accumulated data before they say anything. The
one thing this pack does on day one, and the reason it exists at all:

> **3 out of 3 is not better than 47 out of 52.** Every community leaderboard ranks by raw rate and
> so puts the vendor with three lucky jobs above the vendor with a year of evidence. Shrink toward
> a prior estimated from the data, and rank by the posterior lower bound, not the posterior mean.
> Ranking by the mean still favours small samples whenever the prior is weak; ranking by the lower
> bound is what makes "we do not know enough about this vendor yet" cost them a place.

---

## `bayes.py`

### `bayes.fit_beta_prior`

| | |
|---|---|
| **streams** | `RateObservation[]` derived from `RequestSpell[]`, `DueSpell[]` or `ParticipationEvent[]` |
| **input** | `observations, *, method: "moments" \| "mle" = "mle", min_groups: int = 5` |
| **output** | `structure`: `{"alpha", "beta", "prior_mean", "prior_strength", "lo", "hi"}`. `interval_kind="profile-95"` on the prior mean, `unit="rate"`. `prior_strength = alpha + beta` is the number of pseudo-observations the prior is worth, and it is the number a reader needs to understand how hard the shrinkage will pull. |
| **min_n** | **5 groups**, per the Evidence contract §8, and at least 50 total trials. The prior is estimated *from* the groups, so with fewer than 5 there is nothing to pool and the honest answer is a uniform prior with that stated. |

**assumptions** the group rates are exchangeable draws from a common Beta; trials within a group are
Bernoulli with that group's rate.

**checks**
- `groups-sufficient`, **blocking** below 5.
- `prior-fit`: a posterior predictive check comparing the observed spread of group rates against the
  fitted Beta. If the observed spread is much wider, the population is not exchangeable, the prior
  is too tight, and shrinkage will over-correct. WARN, and the pack then recommends stratifying
  before pooling.
- `heterogeneous-trials`: when one group has 90% of all trials it dominates the prior. Reported.
- `zero-variance`: all groups at the same rate makes the MLE diverge to an infinitely strong prior.
  **Blocking**, with the caveat that the groups are indistinguishable, which is itself the finding.

**method card**
- *assumes:* exchangeability of groups. Vendors from different trades are not exchangeable, and the Method Card says so: pool within trade, not across.
- *wrong_when:* the groups genuinely differ in kind; one group dominates the sample; the rate is not stable over the window, since a vendor who improved is being shrunk toward their own past.
- *interval_meaning:* a profile-likelihood interval on the prior mean. It is uncertainty about the *population*, not about any group.
- *references:* Robbins (1956) on empirical Bayes. Efron and Morris (1975) JASA 70:311. Robinson, *Introduction to Empirical Bayes* (2017), ch. 3.

**known answer** *Corrected in implementation.* Robinson's published Beta(78.7, 224.9) is fitted to
career batting averages from the Lahman database, which is not vendored here and cannot be
downloaded in this environment, so asserting against it would be a known answer nothing checks. What
is asserted instead: recovery of a known Beta from seeded simulation, at a tolerance derived from
the design's own standard error rather than picked; agreement between the moment and
maximum-likelihood fits on plentiful data; and the blocking refusal when every group sits at the
same rate. The `prior-fit` check is asserted in **both** directions, on a bimodal population that
must fail it and an exchangeable one that must not.

*Also corrected:* `prior-fit` cannot be a comparison of observed against expected **spread**. Both
fitting methods match the observed variance by construction, so a variance ratio computed against
them can essentially never fire, and a check that cannot fail is not a check. It is a posterior
predictive chi-square on the probability integral transform instead, which does catch the case the
check exists for: two trades pooled as one look bimodal, not Beta. A new non-blocking
`strength-identified` check was added alongside it, because on the eighteen batters the marginal
likelihood moves by under half a log unit between a prior strength of 167 and one of infinity: the
prior **mean** is well determined there and the shrinkage weight is not, and saying so is the
difference between a defensible choice and a measurement.

---

### `bayes.beta_binomial_shrink`

| | |
|---|---|
| **streams** | `RateObservation[]` |
| **input** | `observations, prior, *, credible: float = 0.95` |
| **output** | `table`, one row per group: `{"group_ref", "successes", "trials", "raw_rate", "shrunk_rate", "lo", "hi", "shrinkage_weight", "n"}`. `interval_kind="credible-95"`, and the contract's per-row rule applies: **every row carries its own n and interval**, which is the entire reason the table shape exists. |
| **min_n** | 1 trial per group for a row to appear; 5 groups for the prior. A group with zero trials is shown at the prior with the interval that implies, which is honest and visually obvious. |

The posterior is closed form: `Beta(alpha + x, beta + n - x)`. `shrinkage_weight = n / (n + alpha + beta)`
is returned so a reader can see that the 3-out-of-3 vendor's estimate is 92% prior.

**checks** `prior-inherited` (carries forward every check from `fit_beta_prior`),
`extreme-shrinkage` (a group whose weight is below 0.1 is essentially reported as the prior, and the
row is labelled "not enough evidence yet" rather than given a number that looks like a measurement),
`k-anonymity-rows` (**blocking per row** where a group maps to fewer than `k` members).

**method card**
- *assumes:* the Beta prior fits the population; trials are exchangeable within a group.
- *wrong_when:* the group is genuinely exceptional, in which case shrinkage under-states it and only more data fixes that; the outcome is not binary, for example partial resolutions counted as successes.
- *interval_meaning:* a 95% **credible** interval, which is a Bayesian statement about the group's rate given the model, not a confidence interval. `interval_kind` says `credible-95` and the UI must render the distinction, because the two are read differently.
- *references:* Gelman et al., *Bayesian Data Analysis*, 3rd ed., ch. 5. Efron and Morris (1975).

**known answer** Exact and closed form. The posterior of `Beta(a,b)` with `x` successes in `n` trials
is `Beta(a+x, b+n-x)`; the parameters are asserted to 1e-12 and both interval endpoints by inverting
our own regularized incomplete beta to 1e-9. *Corrected:* `scipy` is deliberately not a dependency
of the light tier, so it is not the oracle. Second ground truth: **Efron and Morris's 1975 eighteen
batters**. The fixture is reconstructed from published values rather than vendored as a CSV, and
`tests/unit/stats/data/baseball.py` says so in its own header; it is checked against three published
aggregates before any service touches it, and reproduces them: raw total squared error **.0753**
against the published .0755, James-Stein **.0213** against the published .0214, and the famous
ratio **3.53** against the published 3.5. Empirical Bayes shrinkage on the same table cuts the error
by **3.30**. Third, the pathology test, which is a hard shipping requirement and passes: on a
fixture containing a 3-of-3 group and a 47-of-52 group, 47-of-52 ranks **first** by posterior lower
bound (0.796) and 3-of-3 falls to **fourth** (0.573), from first on raw rate.

---

### `bayes.gamma_poisson_shrink`

The count-rate analogue, for "requests per resolver per month" or "escalations per category per
week". Posterior `Gamma(alpha + sum(y), beta + sum(exposure))`, closed form, with the same table
shape and the same per-row rule. Exposure is explicit, so a resolver active for two weeks is not
compared against one active for a year. **known answer** exact conjugate identity, asserted on the
parameters to 1e-12 and on both interval endpoints by inverting our own regularized incomplete gamma
to 1e-9 (*corrected:* `scipy` is not a dependency of the light tier), plus recovery of a known Gamma
from seeded simulation, plus the exposure test: two groups at the same rate on very different
exposure must not come out with the same interval.

---

### `bayes.rank_by_posterior_lower_bound`

| | |
|---|---|
| **input** | `posteriors, *, quantile: float = 0.05, tie_break: "posterior_mean"` |
| **output** | `table` in rank order with `{"rank", "group_ref", "lower_bound", "posterior_mean", "n", "lo", "hi", "rank_stability"}`. |
| **min_n** | inherits. |

`rank_stability` is a seeded posterior-sampling estimate of the probability this group holds this
rank. **It is the field that stops a leaderboard lying by omission**: a rank-1 with 34% stability
and a rank-2 with 31% are not meaningfully ordered, and the UI is required to render that as a tie
band rather than as positions.

**checks** `rank-separation` (adjacent ranks whose credible intervals overlap by more than 50% are
grouped into a tie band; not blocking, but it changes the rendering), `n-disclosure` (**blocking**:
the table cannot be rendered without the per-row n, enforced here rather than left to the
frontend).

**known answer** Deterministic given the posteriors, asserted exactly. The interesting test is
behavioural and required for shipping: the 3-of-3 versus 47-of-52 fixture, which passes.

*Corrected on the inverse fixture.* This entry asked that a 0-of-1 group must not outrank a measured
2-of-10, and that expectation is **wrong**. 2 of 10 is not an absence of evidence, it is evidence of
being poor: that group's posterior sits well below the population while the unmeasured group's sits
at the prior, so the unknown group ranking above the known-poor one is shrinkage working, not
failing. What the lower-bound rule guarantees, and what the test asserts, is that an unmeasured
group never outranks a group measured to be **good**, which is the direction the leaderboard
pathology actually runs in.

A second behavioural test carries the weight the 47-of-52 fixture cannot: on that fixture the
posterior mean happens to agree with the lower bound, so it does not on its own show the rule is
needed. With a deliberately weak Beta(1,1) prior and a well evidenced vendor at 39 of 52, the two
rules disagree, the mean puts 3-of-3 first, and only the lower bound charges it for the evidence it
does not have. Rank stability is asserted by seeded Monte Carlo against the two-group integral
computed independently by quadrature.

---

### `bayes.hierarchical_pool`

**Privacy resolution (settled, no longer blocking).** The threat is a differencing attack: a
tenant runs the same query twice, a competitor tenant's data changes between the two runs, and the
tenant infers something about that change from how the shared prior moved. Concentration and
tenant-count floors alone do not close this, since they bound influence, not observability. Two
mechanisms close it:

1. **Every tenant's contribution enters the pool as a differentially private sufficient statistic**,
   not as raw or lightly-aggregated data. Each tenant's `(events, exposure)` pair for a `group_key`
   is perturbed with calibrated Laplace noise (the counts stream) before it is combined with any
   other tenant's contribution, at a **declared, budgeted epsilon per pooling run**. This is a
   guarantee about the mechanism, not a promise about behaviour: it holds even against a tenant that
   queries adversarially.
2. **The pool is refreshed on a fixed cadence (default weekly), never live.** A single tenant's
   update cannot be isolated in the output because many tenants' changes land in the same batch, and
   the previous batch's noised statistics are not retained for differencing across releases.

Aggregated, anonymised patterns are what get pooled, in other words: never an identifiable tenant's
raw rate. This is what the vertical manifest and the tenant admin see and can switch off, and it is
what makes the platform-scale advantage in `PLAN.md` defensible rather than assumed.

| | |
|---|---|
| **streams** | `RateObservation[]` carrying an anonymised `group_key`, potentially spanning tenants |
| **input** | `observations, *, levels: tuple[str, ...], draws: int = 4000, seed: int, min_units_per_level: int = 5, epsilon: float = 1.0, refresh_cadence: str = "weekly"` |
| **output** | `structure`: the pooled posterior per unit plus `{"tau", "tau_lo", "tau_hi", "pooling_factor", "epsilon_spent", "as_of_batch"}`. `interval_kind="credible-95"`. |
| **min_n** | 5 units per level, and **for cross-tenant pooling, at least 10 contributing tenants with no single tenant supplying more than 25% of the observations.** Below that, a tenant's own data would dominate the "learned" prior even before noise is added, so the floor stays as a second line of defense. |

This is the platform-scale advantage in `PLAN.md`: the prior a new society starts with is learned
from every society already on the platform, through a mechanism that is proof against a single
tenant reconstructing another's data rather than merely unlikely to permit it.

**checks**
- `tenant-concentration`, **blocking** above 25%.
- `min-tenants`, **blocking** below 10.
- `dp-budget-exhausted`, **blocking**: a tenant-level (epsilon, delta) budget is tracked per rolling
  quarter (composition across repeated pooling runs; see references). Once spent, that tenant's
  contribution is excluded from the next pool rather than the guarantee being silently weakened.
- `tau-identified`: with few units the between-group variance is barely identified and the pooling
  factor is driven by the prior on tau rather than by the data. WARN with the prior sensitivity
  reported.
- `convergence`: R-hat and effective sample size across seeded chains. **Blocking** above R-hat 1.01.
- `privacy-notice`: a permanent, non-blocking caveat stating that cross-tenant pooling is enabled
  and DP-protected, visible to tenant admins, with a manifest switch to opt a tenant's own data out
  of contributing (it can still receive the pooled prior).

**method card**
- *assumes:* tenants are exchangeable within a vertical. They are not exchangeable across verticals, and the service refuses to pool a housing society with a sports club. The DP mechanism assumes each tenant's contribution per batch is bounded (one sufficient statistic per group_key per cadence), which is enforced by construction rather than trusted.
- *wrong_when:* one large tenant dominates before noise is applied; the vertical is heterogeneous; a tenant's per-quarter privacy budget is exhausted, which excludes rather than degrades its contribution.
- *interval_meaning:* credible intervals from the posterior over the noised sufficient statistics; the pooling factor says how much of each unit's estimate came from its own data versus the pool.
- *references:* Gelman and Hill (2006), ch. 12. Rubin (1981) J. Educational Statistics 6:377. Dwork and Roth (2014), *The Algorithmic Foundations of Differential Privacy*, for the noise mechanism and the composition theorem the budget check enforces.

**privacy test, in addition to the known-answer test below:** a sensitivity fixture asserting that
perturbing one held-out tenant's contribution by a bounded amount changes the published pooled
statistic by no more than the DP guarantee allows, at the declared epsilon. This is the gate,
alongside the statistical test, that must pass before a card implementing this service can close.

**known answer** The **eight schools** dataset, the canonical hierarchical-model fixture, from Rubin
(1981) and *Bayesian Data Analysis* ch. 5. The data (28, 8, -3, 7, -1, 1, 18, 12) with standard
errors (15, 10, 16, 11, 9, 11, 10, 18) is quoted from the published table; the posterior figures are
quoted from the same source rather than vendored, so what is asserted is the set of features every
published account agrees on and a wrong implementation fails: school A shrinks from 28 to about 11,
every effect lands between its own value and the pooled mean, the order is preserved among schools
with equal standard errors and deliberately **not** preserved across unequal ones (C at -3 is pooled
above E at -1, because C's standard error is 16 against E's 9), and tau's credible interval reaches
down to zero. Two exact identities carry no tolerance at all: the pooling factor equals
`sigma^2 / (sigma^2 + tau^2)` per unit, and the fitted values reproduce the precision-weighted mean
as tau goes to zero.

*Corrected on `convergence`.* The posterior is computed by deterministic quadrature over tau (BDA
ch. 5.4) rather than by MCMC, because the model has one scalar hyperparameter and the integral is
cheap and exact to grid resolution. R-hat does not apply to a quadrature. The equivalent criterion
is run and reported under the same check id: grid refinement, plus a second seeded draw stream
compared against the Monte Carlo error the draw count itself implies rather than against a fixed
number that would pass at 8000 draws and fail at 400 for no reason but the sample size.

*Corrected on `dp-budget-exhausted`.* A tenant over budget is **excluded**, which is the remedy this
entry itself specifies, so the check cannot block whenever it fires or the remedy would never run.
It is a non-blocking WARN naming the exclusions, and blocks only when the exclusions leave too few
tenants to pool at all, at which point `min-tenants` fails with it.

---

## `experiments.py`

All three services here consume the **exposure log**: `ParticipationEvent` rows with `arm_ref` and
kinds `nudge_sent` through `nudge_acted` (spine §4 and §8). Without it they would measure
self-selection.

### `experiments.beta_ab_test`

| | |
|---|---|
| **streams** | `ParticipationEvent[]` with `arm_ref` |
| **input** | `arm_a, arm_b, *, prior: tuple[float, float] = (1.0, 1.0), credible: float = 0.95` |
| **output** | `structure`: `{"p_b_beats_a", "lift", "lift_lo", "lift_hi", "posterior_a", "posterior_b", "n_a", "n_b"}`. `interval_kind="credible-95"`. |
| **min_n** | 100 exposures per arm **and** 10 conversions per arm. Below 10 conversions the posterior is dominated by the prior and `P(B>A)` will hover near 0.5 while looking like a real number. |

**checks**
- `randomisation-balance`: covariate balance across arms from the exposure log. A failure means the
  assignment was not random and the comparison is observational. **Blocking**, because a broken
  randomisation produces a confident and wrong answer.
- `sample-ratio-mismatch`: exposures per arm against the intended split, chi-square. The standard
  canary for a broken experiment pipeline. **Blocking.**
- `novelty-window`: whether the effect is concentrated in the first days of exposure.
- `no-peeking`: whether this envelope is being read before the declared stopping rule fired.
  **Not blocking, but always disclosed**, and the UI shows "this experiment is still running" rather
  than a verdict.

**method card**
- *assumes:* random assignment; independent members; a stable conversion definition; one metric declared in advance.
- *wrong_when:* the arms were assigned by channel or by time of day, so channel is confounded; members received both arms; the metric was chosen after seeing the data.
- *interval_meaning:* credible intervals from the Beta posteriors. `P(B>A)` is a posterior probability, not a p-value, and it must not be read as one, which the card states in those words because the confusion is universal.
- *references:* Miller, *Formulas for Bayesian A/B testing*. Stucchio (2015) on expected loss. Kohavi, Tang and Xu (2020), *Trustworthy Online Controlled Experiments*, on SRM and randomisation checks.

**known answer** `P(B>A)` for two Beta posteriors has an exact closed form (Miller's finite sum over
the integer parameters), which is asserted to 1e-10 against high-resolution numerical integration of
the same quantity. Two independent computations of the same integral, so an error in either is
caught.

---

### `experiments.expected_loss`

The decision-theoretic companion: the expected magnitude of the mistake if you pick each arm now.
The stopping rule is "expected loss below the threshold of caring", which is a threshold the
committee sets in the units of the metric, not a significance level. It is passed as the optional
`threshold` argument; with no threshold the service reports the stake and says nothing about
stopping, because the threshold belongs to the committee and is set before the loss is seen.

**known answer** Stucchio's closed form for the Beta expected-loss integral, asserted against
nested quadrature of the same integral, plus the exact identity
`loss(A) - loss(B) = E[theta_B] - E[theta_A]`.

**Correction.** This entry previously said the expected loss is zero when the posteriors are
identical. **That is false.** For two independent Beta(1, 1) posteriors,
`E[(theta_B - theta_A)^+] = 1/6` exactly, and in general the loss is `E|theta_B - theta_A| / 2` on
each side: either arm might still be the worse one, and that residual regret is the whole reason to
keep running. What *is* exactly zero when the posteriors are identical is the **difference** between
the two losses, which is the identity the test now asserts to 1e-12.

---

### `experiments.sequential_stopping_rule`

| | |
|---|---|
| **input** | `event_stream_ordered, *, alpha: float = 0.05, method: "msprt" \| "evalue" = "evalue"` |
| **output** | `structure`: `{"stop", "at_n", "e_value", "threshold", "decision"}`. `interval_kind="none"`; the always-valid confidence sequence is returned separately. |
| **min_n** | none by construction, which is the point: an always-valid method may be monitored continuously without inflating error. |

**This service exists to make peeking safe rather than to forbid it.** A committee will look at a
running experiment every day no matter what the documentation says, so the correct engineering
response is a method that remains valid under continuous monitoring, not a rule nobody follows.

**checks** `optional-stopping-valid` (asserts the method in use is an always-valid one; **blocking**
if a fixed-horizon test is being monitored sequentially), `exposure-log-complete`.

**method card**
- *assumes:* the e-value or mixture SPRT construction; observations arrive in time order.
- *wrong_when:* the metric definition changed mid-flight; the arms changed mid-flight, which resets the process and the service says so.
- *interval_meaning:* the confidence sequence covers the true effect at all times simultaneously with probability `1 - alpha`, which is a stronger and different guarantee from a fixed-sample interval. It is correspondingly wider, and the card explains why that width is the price of being allowed to look.
- *references:* Ville (1939). Howard, Ramdas, McAuliffe and Sekhon (2021) Annals of Statistics 49:1055. Johari, Koomen, Pekelis and Walsh (2022) on always-valid inference.

**method** Two always-valid constructions and one refusal. `method="evalue"` is Robbins' normal
mixture over the Horvitz-Thompson contrast
`psi_i = y_i (1{B}/pi_B - 1{A}/pi_A)`, which is exactly mean zero under the declared randomisation
and bounded, so Hoeffding's lemma makes it sub-Gaussian and `E_t = sqrt(rho/(V_t+rho))
exp(S_t^2 / 2(V_t+rho))` is a nonnegative supermartingale at every finite n. `method="msprt"` is the
same mixture with the running empirical variance in place of the worst-case proxy, which is the
Johari, Koomen, Pekelis and Walsh construction: tighter, and valid asymptotically rather than
exactly, which the envelope says in a WARN. The mixture parameter `rho` is not a magic number: it is
solved so the boundary is tightest at the declared `target_n`, from the fixed point
`u = 2 log(1/alpha) + log(1 + u)`, and the test finds that minimum numerically on a grid.

`method="fixed_horizon_z"` runs the naive rule and then **refuses to certify it** with a blocking
check, because "stop the first time p < 0.05" is what everyone actually does and a service that
pretends otherwise teaches nothing.

**known answer** A theorem: under the null, `P(sup_t E_t >= 1/alpha) <= alpha` by Ville's
inequality. The test simulates many seeded null experiments with continuous monitoring and asserts
the empirical false-positive rate is at or below alpha within binomial tolerance. The negative
control is required: **a fixed-horizon z-test monitored the same way must exceed alpha
substantially** on the identical fixture, which proves the guarantee is doing work.

**Measured.** Over 1000 seeded null experiments of 1200 exposures each, monitored after *every*
observation: the e-value stops **0.0%** of the time and the mSPRT **1.0%**, against a nominal 5%.
The naive z test, peeked at every 25 observations on the identical trials, stops **23.8%** of the
time. Power is the price of the exact bound: on a 0.20 against 0.30 contrast the e-value stops in
over 90% of runs by 8000 exposures where the mSPRT is there by 2000, and the Method Card says so.

---

## `bandits.py`

### `bandits.thompson_sampling_policy`

| | |
|---|---|
| **streams** | `ParticipationEvent[]` with `arm_ref` |
| **input** | `arm_posteriors, *, seed: int, n_draws: int = 10000, floor: float = 0.05` |
| **output** | `structure`: `{"allocation", "arm_win_probability", "posteriors", "regret_estimate", "seed"}`. `interval_kind="credible-95"` per arm. |
| **min_n** | none to run; 30 exposures per arm before the pack will *act* on the allocation, with a uniform allocation until then. |

`floor` guarantees every arm keeps at least 5% of traffic, so an arm that got unlucky early can
recover and so the experiment keeps learning. Pure Thompson sampling can starve an arm on noise, and
in a community setting that means a communication channel is silently abandoned.

**checks** `seed-recorded` (**blocking** if absent; an unreproducible policy decision cannot be
explained to a committee, which is the whole reason `freeze_and_report` exists),
`non-stationarity` (a changepoint in any arm's reward series; if found, the posteriors are
discounted and the discount is disclosed), `floor-applied`.

**method card**
- *assumes:* stationary arm rewards; independent exposures; the reward is observed promptly relative to the decision cadence.
- *wrong_when:* the reward is seasonal, since a channel that works during festivals will dominate permanently after one festival; rewards arrive with a long delay so the bandit acts on incomplete feedback; the arm set changes, which invalidates the accumulated posteriors.
- *interval_meaning:* per-arm credible intervals. The allocation is a decision, not an estimate, and carries no interval.
- *references:* Thompson (1933) Biometrika 25:285. Russo, Van Roy, Kazerouni, Osband and Wen (2018), *A Tutorial on Thompson Sampling*. Lai and Robbins (1985) for the regret lower bound.

**known answer** Honest and partial. **There is no published table of Thompson-sampling outputs to
assert against**, and inventing one would be exactly the thing this catalog refuses to do. Three
things are asserted instead. Exact: given a seed, the policy is reproducible bit for bit, which is
the property a committee actually depends on. Theoretical: cumulative regret on a fixed two-armed
Bernoulli problem must grow at `O(log T)` and must not exceed a constant multiple of the
Lai-Robbins lower bound `sum(delta_i / KL(p_i, p*)) * log T` across seeded runs. Behavioural:
Thompson sampling must beat uniform allocation on cumulative reward on the same seeded fixture, and
must not starve an arm below the floor. The regret bound is a theorem and therefore a real external
truth; the rest are constructions and are labelled so in the Method Card.

**Measured.** Two Bernoulli arms at 0.20 and 0.30, where `KL(0.2, 0.3) = 0.025732` nats and the
Lai-Robbins constant is `0.10 / 0.025732 = 3.886`. Mean regret over 20 seeds: **6.85, 8.64, 11.01,
12.76, 14.34** at horizons 500, 1000, 2000, 4000, 8000. Fitted against `log T` that is a slope of
**2.70**, which is **0.70 of the asymptotic constant**, and the curve sits under `C log T` at every
finite horizon, which is where a `liminf` bound leaves a finite run. Uniform allocation loses
**200** at T = 4000 where Thompson loses **9.8**. The 5% floor's cost is asserted against its own
closed form rather than waved at: forcing `k * floor` of rounds to be uniform must cost
`floor * gap * T`, predicted **40.0** at T = 8000 and measured **38.5**.

**The randomness is ours.** The Beta draws come from a Marsaglia-Tsang gamma sampler driven only by
`random.Random(seed).random()`, not from `random.betavariate`. The Mersenne Twister's uniform stream
is fixed and documented; the distribution helpers on top of it are implementation detail. A
committee asking in 2029 why the system chose Tuesday evening reminders must get the same allocation
back, not a different one because the interpreter was upgraded.

---

### `bandits.freeze_and_report`

| | |
|---|---|
| **input** | `policy_state, *, as_of` |
| **output** | `structure`: the frozen allocation, the posteriors that produced it, the seed, the exposure counts per arm, and a plain-language reason string per arm assembled from those numbers. `interval_kind="credible-95"`. |
| **min_n** | none. |

Deterministic by construction and it is the governance feature, not a statistical one: a committee
must be able to say **why** the system chose to send Tuesday evening WhatsApp reminders, months
later, from a stored record. The frozen envelope plus the seed reproduces the decision exactly.

**known answer** Exact: replaying the frozen state with the stored seed reproduces the identical
allocation, asserted bit for bit. This is the reproducibility test, and it is the one that would
actually fail if someone added module-level state to `stats/`, so it doubles as a purity regression.

---

## `pairwise.py`

### `pairwise.bradley_terry`

| | |
|---|---|
| **streams** | `PairwiseResult[]` derived from `RequestSpell[]` head-to-heads, competition results, or `Ballot[]` |
| **input** | `results, *, penalizer: float = 0.0, reference: str \| None = None, alpha = 0.05` |
| **output** | `table`: `{"item_ref", "ability", "lo", "hi", "n_comparisons", "wins", "losses"}`. `interval_kind="profile-95"`. |
| **min_n** | 5 items, 30 comparisons, and every item in a single connected component of the comparison graph. |

**checks**
- `connectivity`: **blocking**. If the comparison graph is disconnected, abilities in different
  components are not comparable on one scale, and every implementation that does not check this
  silently returns a ranking anyway. The service returns per-component rankings instead.
- `separation`: an item that won or lost every comparison drives its ability to infinity. **Blocking
  for that row**, replaced with "undefeated in 4 comparisons, ability unbounded", which is the
  honest statement.
- `transitivity`: the share of intransitive triads, reported. High intransitivity means a
  one-dimensional ability model is the wrong description, exactly as a Condorcet cycle means a
  linear preference order is.
- `home-advantage`: an order effect if comparisons have a first and second position.

**method card**
- *assumes:* a single latent ability per item; comparison outcomes independent given abilities; abilities stable over the window.
- *wrong_when:* preferences are cyclic; abilities changed during the window (use `pairwise.elo_update`, which tracks change by construction); the comparison graph is disconnected or nearly so.
- *interval_meaning:* profile-likelihood intervals on abilities relative to the reference item. Only differences are identified, so the scale's origin is arbitrary and the card says so.
- *references:* Bradley and Terry (1952) Biometrika 39:324. Hunter (2004) Annals of Statistics 32:384 for the MM algorithm. Turner and Firth (2012) JSS 48:9, the `BradleyTerry2` package.

**known answer** *Corrected twice.* First, the `BradleyTerry2` package is not vendored here and
there is no network access, so its printed examples are not the oracle. What replaces them is
stronger, because it is a theorem rather than another library that could be wrong in the same way:
the exact stationarity condition of the maximum likelihood estimate, that for every item the number
of wins the fitted abilities predict equals the number observed,
`sum_j n_ij * p_i / (p_i + p_j) = w_i`, asserted to 1e-6. Asserting each pair's observed win rate
instead would be wrong and it is worth writing down why: Bradley-Terry is a constrained model with
one parameter per item and deliberately does not reproduce a pair's rate, so such a test would be
testing a saturated model this is not.

Second, "for a perfectly transitive result set the ordering must match exactly" is right about the
ordering and wrong about the abilities. When the stronger item wins every single game, **Ford's
condition fails and no finite set of abilities maximises the likelihood**; any number printed for
them is the optimiser's stopping rule. The `separation` check is therefore Ford's condition itself
rather than a scan for undefeated items (an undefeated item is only the most obvious way to fail
it), and the service publishes the **tier** order the data determines while withholding the numbers
it does not. On a perfectly transitive six-item ladder that is six tiers, every ability `None`, and
the ordering exactly right.

Also asserted: recovery of known abilities from a seeded ladder, with the profile intervals covering
all five; monotonicity in wins on a balanced round robin; the disconnected-graph refusal; and the
order effect caught in one fixture and not in its control.

---

### `pairwise.elo_update`

Sequential rating updates with a declared K-factor, for time-ordered comparisons where ability
changes. Returns the rating trajectory with a `structure` per item. **known answer** exact
arithmetic: two items at 1500 with K = 32 move by exactly 16, asserted to 1e-12; total rating is
conserved to 1e-9 over 400 seeded results; and the fixed point of repeated updates against an
opponent held constant is `400 * log10(w / (1-w))`, which equals the Bradley-Terry ability
difference `log(w / (1-w))` after the `ln(10)/400` change of scale, linking the two services by a
real analytic identity. *One nuance recorded:* that recursion is run in the test rather than through
the service, because the service is zero sum and moves the opponent too. A constant opponent is a
property of the update rule, not of a real ladder.

---

# Appendix: services with no external published ground truth

Listed together, because a reader should be able to find them in one place rather than trusting that
every "known answer" above is equally strong. Each of these is **gated or property-tested**, never
validated against an external number, and each Method Card says so in its own words.

| Service | What is asserted instead | Why no external truth exists |
|---|---|---|
| `forecast.stl_decompose` | Exact reconstruction identity, recovery from a synthetic build, agreement with the reference implementation on `co2`. | STL is a smoothing procedure with tuning parameters; no canonical component table is published. |
| `risk.late_payment_risk` | The calibration gate (positive Brier skill, ECE under 0.05 on held-out data) plus coefficient recovery from a known logistic generator. Every component has its own external truth. | The model is domain-specific and there is no public benchmark for community dues default. |
| `risk.member_disengagement_risk` | As above, plus consistency with `survival.churn_curve` at the same horizon. | Same. |
| `text.nmf_topics` | Recovery of specified topic-word distributions from a seeded synthetic corpus, plus exact tests of the coherence and stability metrics themselves. | No published topic fixture exists for community complaint text, and asserting against a hand-labelled set would be circular. |
| `bandits.thompson_sampling_policy` | Seed reproducibility (exact), the Lai-Robbins regret bound (a theorem), and beating uniform allocation on a seeded fixture. | Bandit output is stochastic policy, not a number; published results are regret curves, not values. |
| `segmentation.stable_labels` | Permutation round-trip (exact) and a drift-detection negative control. | It is a matching procedure, not an estimator. |
| `fairness.balanced_assignment` | Textbook optima, a second solver as an oracle, and the row-constant invariance property. | The optima *are* published; listed here only because the service returns a recommendation and not an estimate, so "correctness" means optimality, not accuracy. |

Everything else in this catalog is checked against a published dataset, a published table, a
published coefficient set, or a theorem. Where the ground truth is a theorem (conformal coverage,
Ville's inequality, the Murphy decomposition, Little's Law, the Laplace mechanism, the
Aalen-Johansen identity), that is stated as the strongest available form and preferred to a dataset.
