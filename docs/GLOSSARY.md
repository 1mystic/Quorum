# Glossary

Two jobs: stop agents guessing at domain names, and stop them guessing at statistics.

---

## Product vocabulary

| Term | Meaning |
|---|---|
| **Tenant** | One community using the platform. Has a `slug`, a `vertical`, and a set of enabled packs. The unit of data isolation. |
| **Vertical** | A *kind* of community — `rwa_society`, `campus_club`, `ngo_volunteer`, `alumni_chapter`, `housing_coop`, `sports_club`, `professional_guild`. Configuration, not code: labels, default packs, categories, roles, auth mode. |
| **Member** | A person in a tenant. Replaces Campus Connect's `Student`. |
| **Group** | A sub-unit within a tenant — a club, a committee, a block, a working group. Replaces `Club`. |
| **Request** | Anything with an `open → assign → progress → resolve/close` lifecycle: a complaint, a maintenance ticket, a volunteer task, a membership application. Replaces `Issue`, generalized. |
| **Stream** | One of the six canonical, vertical-agnostic data shapes every statistic is written against. See `docs/DATA_SPINE.md`. |
| **Insight Pack** | A togglable bundle of statistical services with declared required streams, min-n and cadence. What the tenant slug actually switches on. |
| **Evidence** | The envelope every statistic travels in: value, interval, n, method, assumption checks, `insufficient_data`, `as_of`, `params_hash`. See `docs/EVIDENCE_CONTRACT.md`. |
| **Method Card** | The per-service disclosure: assumptions, when it is wrong, minimum n, references. A service without one is not done. |
| **Insight run** | A materialized computation of one service for one tenant, cached in `insight_runs` and served by the API. |

## The Campus Connect rename table

`reference/campus-connect/` uses campus vocabulary throughout. When porting, apply this pass
consistently — model, schema, service, repository, route, store, component, test, and copy.

| Campus Connect | Ours | Note |
|---|---|---|
| `College` | `Tenant` | Keeps `slug`. Gains `vertical`, `enabled_packs`, `settings`. Loses `email_suffix` (moves into the vertical manifest as an optional membership rule). |
| `Student` | `Member` | |
| `CampusAdmin` | `TenantAdmin` | |
| `Club` | `Group` | |
| `Issue` | `Request` | Generalized onto the `request_flow` stream. |
| `Membership` | `Membership` | Unchanged. |
| `Event` | `Event` | Unchanged. Feeds `participation`. |
| `Announcement` | `Announcement` | Unchanged. |
| `Notification` | `Notification` | Unchanged. |
| `Certificate` | `Certificate` | Unchanged, but becomes a togglable module. |
| `EventRegistration` | `EventRegistration` | Unchanged. Feeds `participation`. |
| `Leaderboard` (fixed point weights) | *replaced* | Becomes a Pack 2 service — empirical-Bayes shrunk, ranked by posterior lower bound, not `events × 40 + members × 5`. |
| `college_id` | `tenant_id` | Every table. |
| `COLLEGE_TIMEZONE` | `TENANT_TIMEZONE` | Per-tenant setting, not global config. |
| — | `Ledger` | **New.** Due, Payment, Receipt, Contribution, Expense → the `ledger` stream. |
| — | `Decision` | **New.** Poll, Ballot, Allocation → the `decision` stream. |
| — | `Survey` | **New.** Ordinal + free-text responses → the `signal` stream. |
| — | `InsightRun` | **New.** Materialized statistics. |

**Port with minimal change** (these are good and generic already):
`app/core/*` · `app/exceptions/*` · the auth stack · `app/agent/*` (loop, budget, grounding,
providers, memory, intent) · `frontend/src/composables/*` · the router and store skeleton.

---

## Statistical vocabulary

Written for the agent that needs to know what it is implementing, not for a textbook.

### Survival / reliability

| Term | Meaning here |
|---|---|
| **Right-censoring** | A request that is still open has an unknown resolution time — we only know it exceeds today's age. Dropping it (the naive dashboard bug) systematically *understates* resolution time. It must be included as censored. |
| **Kaplan–Meier** | Non-parametric estimate of "fraction still unresolved at day *t*", handling censoring correctly. |
| **Log-rank test** | Do two survival curves differ more than chance? Used across categories, blocks, assignees. |
| **Cox proportional hazards** | Regression on time-to-event giving a **hazard ratio** per covariate — "monsoon multiplies the plumbing hazard by 2.1". Assumes hazards stay proportional over time. |
| **Schoenfeld residuals** | The automatic check on that proportionality assumption. If it fails, the HR is not interpretable and we must say so. |
| **Competing risks / Aalen–Johansen** | When a request can exit by resolution *or* escalation *or* withdrawal, treating the others as censoring is wrong. This handles it. |

### Process control

| Term | Meaning here |
|---|---|
| **EWMA chart** | Exponentially-weighted moving average control chart. Catches small sustained shifts a raw chart misses. |
| **CUSUM chart** | Cumulative sum chart. Fastest at detecting a persistent step change. |
| **ARL** (average run length) | How long before a chart false-alarms. We tune limits to a target ARL rather than defaulting to ±3σ. |
| **Changepoint / PELT** | Finds *when* the series changed, with a significance level. "Something changed on 12 Aug." |

### Queueing

| Term | Meaning here |
|---|---|
| **Little's Law** | `L = λW`. Backlog = arrival rate × wait. Turns a visible queue length into an expected wait with no model fitting. |
| **M/M/c** | c servers, Poisson arrivals, exponential service. The committee-capacity approximation. |
| **Erlang-C** | Given arrival rate, service time and a target service level, how many resolvers do you need. Produces the staffing recommendation. |
| **Gini (on workload)** | How unequally work is distributed across resolvers. 0 = even, 1 = one person doing everything. |

### Bayesian

| Term | Meaning here |
|---|---|
| **Empirical Bayes shrinkage** | A vendor that resolved 3/3 is not better than one that resolved 47/52. Shrink small-sample rates toward the population prior estimated from the data. Rank by **posterior lower bound**, not point estimate. |
| **Beta-Binomial / Gamma-Poisson** | The conjugate pairs used for rates and counts respectively. Closed form, so testable exactly. |
| **Partial pooling** | Estimating the prior across *all* tenants so a new community benefits from the platform's accumulated experience. Requires a privacy review. |
| **Credible interval** | The Bayesian interval. Not a confidence interval — say which one in `interval_kind`. |
| **Thompson sampling** | Bandit policy: sample from each arm's posterior, play the winner. Used for reminder timing/channel, with a freeze-and-report mode so a committee can explain the choice. |
| **Bradley–Terry / Elo** | Ranking from pairwise comparisons. |

### Forecasting & calibration

| Term | Meaning here |
|---|---|
| **STL** | Seasonal-Trend decomposition by Loess. Separates "it is festival season" from "we have a problem". |
| **MASE** | Mean Absolute Scaled Error, scaled against a seasonal-naive baseline. **< 1 means the model beats naive.** A forecaster that does not beat naive does not ship. |
| **Rolling-origin CV** | Backtesting that respects time order. Never a random split on a time series. |
| **Calibration** | A "30% risk" bucket must actually default ~30% of the time. Achieved with isotonic or Platt scaling *after* fitting. |
| **Brier score** | The calibration metric we gate on. AUC measures ranking, not honesty — it is not enough. |
| **Reliability diagram** | Predicted probability vs observed frequency. The picture behind the Brier score. |
| **Conformal prediction** | Distribution-free intervals with a *guaranteed* coverage rate. How we show a resident "2–9 days" instead of a fake point ETA. |
| **PSI / KS drift** | Population Stability Index and Kolmogorov–Smirnov on feature distributions. Flags a model whose world has moved on. |

### Social choice & surveys

| Term | Meaning here |
|---|---|
| **Condorcet winner** | The option that beats every other head-to-head. May not exist. |
| **Condorcet cycle** | A beats B, B beats C, C beats A. We **disclose** this rather than hiding it behind whichever rule breaks the tie. |
| **Schulze method** | A Condorcet-consistent rule that always produces a winner via strongest paths. Our default. |
| **STV** | Single Transferable Vote — for multi-seat committee elections. |
| **Method of Equal Shares** | Participatory budgeting rule with proportional fairness guarantees. Beats greedy knapsack on representing minority preferences. |
| **Raking / post-stratification** | Reweighting a skewed respondent set to match the known population. Turns "of those who voted" into an honest population estimate. |
| **Design effect** | How much the weighting inflates the variance. Reported so a 12% turnout poll is not presented as fact. |
| **Sortition** | Stratified random selection of a representative committee. |

### Segmentation, network, text, privacy

| Term | Meaning here |
|---|---|
| **RFM** | Recency / Frequency / Monetary — the classic engagement feature triple, adapted to participation. |
| **BIC + silhouette** | How we choose *k*. Never a hard-coded cluster count. |
| **Louvain** | Community detection on the member interaction graph. |
| **Betweenness centrality** | Finds informal connectors — the people who hold sub-communities together. |
| **MinHash / LSH** | Cheap near-duplicate detection at scale, for "3 neighbours already reported this". |
| **NMF topic mining** | Non-negative matrix factorization over resolved-request text → emergent themes. |
| **Ordinal logistic** | The right model for Likert responses. Treating a 1–5 scale as a continuous mean is the common mistake. |
| **k-anonymity** | Suppress any cell representing fewer than *k* members. |
| **Differential privacy / Laplace noise** | Calibrated noise on published aggregates so a per-block figure cannot re-identify a household. |
