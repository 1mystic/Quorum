# The canonical data spine

*Card A.2. Status: draft 1. Depends on `docs/EVIDENCE_CONTRACT.md`.*

Six streams. Every statistical service in `docs/STATS_CATALOG.md` is written once, against a
stream, never against a vertical. A housing society's plumbing complaint, a campus club's issue
ticket, an NGO's case file and a guild's membership application are the same object to
`app/stats/survival.py`, because all four are a `RequestSpell`.

---

## 0. What a stream is, and what it is not

A stream is **not** a table. It is a typed, frozen, in-memory shape that pure statistical code
consumes. The database may store it in five tables or one; the adapter's job is to produce the
shape. `backend/app/stats/streams/` holds the dataclasses and the reducers; the per-vertical
adapters live in `backend/app/verticals/` and are the only place a domain word like "complaint" or
"case" appears.

Three layers, and the boundary between them is the purity rule:

```
  Postgres rows                            (services / repository, impure)
        |  adapter: vertical -> canonical  (backend/app/verticals/*.py, impure at the edges)
        v
  Stream ATOMS: append-only events         (frozen dataclasses)
        |  reducer: atoms -> analysis units (backend/app/stats/streams/*.py, PURE)
        v
  Stream UNITS: spells, periods, features  (frozen dataclasses)
        |  service function                (backend/app/stats/*.py, PURE)
        v
  Evidence
```

**The reducers are pure and are where the correctness lives.** Censoring is decided in a reducer,
not in a SQL `WHERE` clause. That is deliberate: a `WHERE resolved_at IS NOT NULL` in a repository
is invisible to the test suite, whereas a reducer that mis-censors fails a known-answer test.

### Universal rules

| # | Rule |
|---|---|
| S1 | Every timestamp is timezone-aware UTC. Local calendar bucketing uses `StreamWindow.timezone` and nothing else. |
| S2 | No stream dataclass carries `tenant_id`. Tenant scoping happened upstream, in the repository. A pure function that could see a tenant id could leak one. |
| S3 | Every person is an opaque `member_ref: str`, a per-tenant stable pseudonym, never an email, phone or name. |
| S4 | Money is `int` minor units plus an ISO-4217 `currency`. Never a float, ever, anywhere. |
| S5 | Free text and identity are separable by construction. Text services consume `TextDoc`, which has no `member_ref` field to leak. |
| S6 | Nothing in `app/stats/` reads a clock. "Now" arrives as `StreamWindow.end`. A function that called `datetime.utcnow()` would be non-deterministic and would silently change every `params_hash`. |
| S7 | Ordinal responses are stored as `int` on a declared scale. The spine has no field in which a mean of a Likert item could be stored. |
| S8 | Missing is `None`, never a sentinel, never zero, never the epoch. |

### The window context, passed with every stream

```python
@dataclass(frozen=True)
class StreamWindow:
    start: datetime            # inclusive, UTC. Analysis window opens here.
    end: datetime              # exclusive, UTC. THE observation boundary and the censoring time.
    timezone: str              # IANA name, e.g. "Asia/Kolkata". Calendar bucketing only.
    complete_through: datetime # data is believed complete up to here; <= end
    calendar: tuple[CalendarMark, ...] = ()   # holidays, festivals, term breaks, monsoon months

@dataclass(frozen=True)
class CalendarMark:
    at: date
    kind: str                  # "holiday" | "festival" | "term_break" | "season_start"
    label: str
```

`complete_through` exists because reporting lag is real: the last week of a `ledger` series is
partial until the treasurer finishes reconciling, and a forecaster fitted through `end` will read
that partial bucket as a collapse in collections. **Every periodised service truncates at
`complete_through` and records the gap as a caveat.** Nothing else in the spine protects against
this, and no vertical would naturally supply it, so it is a first-class field.

---

## 1. `member_lifecycle`

Who is in the community, since when, in what stratum, and how they left.

### Atom

```python
MemberEventKind = Literal[
    "join",        # record created
    "activate",    # first meaningful action; separates registered from actually present
    "lapse",       # became inactive by the vertical's rule (dues unpaid, no login, term ended)
    "reinstate",   # returned from lapse
    "exit",        # left for good: moved out, graduated, resigned, deceased, removed
    "role_change",
    "stratum_change",  # moved block, changed cohort, changed membership tier
]

@dataclass(frozen=True)
class MemberEvent:
    member_ref: str
    at: datetime
    kind: MemberEventKind
    reason: str | None = None          # controlled vocabulary per vertical
    role: str | None = None            # for role_change: the role AFTER the change
    group_ref: str | None = None
    strata: Mapping[str, str] = ()     # frozen; see below
    source: str = "app"                # "app" | "import" | "admin" | "adapter_backfill"
```

`strata` is the small controlled dictionary a vertical declares in its manifest: for
`rwa_society`, `{"block": "B", "unit_type": "3BHK", "ownership": "owner", "tenure_band": "2-5y"}`.
It is the key to post-stratification, sortition, fairness reports and every k-anonymity cell.
**Strata values are low-cardinality by contract.** A stratum with as many values as members is a
re-identifier, and the adapter must refuse it.

### Units

```python
@dataclass(frozen=True)
class MemberSpell:                      # the survival record for churn and retention
    member_ref: str
    entered_at: datetime                # join or reinstate
    at_risk_from: datetime              # max(entered_at, window.start); see censoring below
    left_truncated: bool                # entered_at < window.start
    exited_at: datetime | None
    exit_kind: str | None               # "lapse" | "exit" | None
    event_observed: bool                # a terminal exit fell inside the window
    duration_days: float                # (min(exited_at, window.end) - at_risk_from) in days
    strata_at_entry: Mapping[str, str]
    covariates: Mapping[str, float | str]

@dataclass(frozen=True)
class RosterSnapshot:                   # the denominator for turnout, raking, k-anonymity
    as_of: datetime
    counts_by_stratum: Mapping[tuple[str, ...], int]   # stratum key tuple -> headcount
    total: int
    roles: Mapping[str, int]            # role -> headcount, feeds queueing server counts
```

`RosterSnapshot` is a *population frame*, not a sample. It is what turns "62 people voted" into
"62 of 340 eligible, and Block C is under-represented by 11 points".

### Consumers

`survival.*` (churn), `segmentation.*`, `voting.turnout_representativeness`,
`survey.raking_weights`, `sortition.stratified_panel`, `privacy.k_anonymity_suppress`,
`queueing.*` (via `roles`).

---

## 2. `request_flow`

**The stream the product's correctness claim rests on.** Everything with an
`open -> assign -> progress -> resolve/close` lifecycle.

### Atom

```python
RequestEventKind = Literal[
    "opened", "acknowledged", "assigned", "reassigned", "status_change",
    "comment", "paused", "resumed",
    "resolved", "escalated", "withdrawn", "merged",   # terminal
    "reopened", "closed",
]

@dataclass(frozen=True)
class RequestEvent:
    request_ref: str
    at: datetime
    kind: RequestEventKind
    actor_ref: str | None = None        # who did it
    assignee_ref: str | None = None     # who it is on, after this event
    category: str | None = None         # set at opened, may change; changes are events
    subcategory: str | None = None
    priority: str | None = None         # controlled per vertical
    channel: str | None = None          # "app" | "whatsapp" | "walk_in" | "phone" | "email"
    group_ref: str | None = None        # committee, sub-team
    location_ref: str | None = None     # block / tower / floor / site. A stratum, and a small cell.
    parent_ref: str | None = None       # for merged: the surviving request
    at_precision: Literal["exact", "day", "bracketed"] = "exact"
    at_upper: datetime | None = None    # when at_precision == "bracketed"
    attributes: Mapping[str, float | str] = ()
```

### Unit: `RequestSpell`, and the censoring rules

```python
CensoringKind = Literal[
    "none",             # a terminal event was observed inside the window
    "administrative",   # still open at window.end
    "interval",         # terminal known only to fall in [interval_lo, interval_hi]
    "competing",        # exited by a cause other than the one under analysis
    "lost",             # request abandoned by the system, last seen at last_seen_at
]

@dataclass(frozen=True)
class RequestSpell:
    request_ref: str
    opened_at: datetime
    at_risk_from: datetime               # max(opened_at, window.start)
    left_truncated: bool
    duration_hours: float                # at_risk_from -> min(terminal_at, window.end)
    duration_active_hours: float | None  # duration_hours minus paused_hours
    event_observed: bool
    outcome: Literal["resolved", "escalated", "withdrawn", "merged"] | None
    terminal_at: datetime | None
    censoring: CensoringKind
    interval_lo_hours: float | None
    interval_hi_hours: float | None
    first_response_hours: float | None    # opened -> first acknowledged/comment by a non-author
    paused_hours: float
    reopened_count: int
    duplicate_count: int                  # requests merged INTO this one
    category: str
    subcategory: str | None
    priority: str | None
    channel: str | None
    location_ref: str | None
    group_ref: str | None
    assignee_ref: str | None              # the assignee at terminal, or current
    n_reassignments: int
    covariates: Mapping[str, float | str]
```

#### The censoring rules. These are normative.

| # | Rule |
|---|---|
| **C1** | **Every request opened before `window.end` enters the risk set.** No reducer, repository or query may filter on `terminal_at IS NOT NULL`. Open requests are censored, never absent. Excluding them biases every duration downward, because the slow ones are exactly the ones still open. |
| **C2** | A request with no terminal event by `window.end` gets `event_observed=False`, `censoring="administrative"`, `duration_hours = window.end - at_risk_from`. It counts in `Evidence.n` and in `Evidence.n_censored`. |
| **C3** | A request opened before `window.start` is **left-truncated**, not shifted. `at_risk_from = window.start`, `left_truncated=True`, and the estimator must use the delayed-entry `(entry, exit]` risk set. Treating its clock as starting at `window.start` invents a shorter duration; treating it as starting at `opened_at` while only counting events after `window.start` inflates the denominator. Both are wrong; only the risk-set form is right. |
| **C4** | If the terminal timestamp is only bracketed (a batch sync, a "closed since we last looked" import), `censoring="interval"` with `interval_lo_hours` / `interval_hi_hours` set. **Never impute a midpoint.** Services either use an interval-censored estimator (Turnbull) or report `insufficient_data` if too many rows are interval-censored, controlled by a declared threshold. |
| **C5** | **Competing risks.** For the resolution analysis, `escalated` and `withdrawn` are *not* neutral censoring: a withdrawn request will never resolve. Cause-specific Kaplan-Meier that censors them **overstates** the probability of eventual resolution. Rule: if non-resolution terminals exceed 5% of all terminals, the service must report the Aalen-Johansen cumulative incidence function alongside, and raise the `competing-risks-material` check to WARN. Above 15% the check is FAIL and blocking for any "% resolved by day t" claim. |
| **C6** | **Reopen policy is a declared parameter, not a convention.** `reopen_policy="new_spell"` (default): a reopen closes the first spell as `resolved` and starts a child spell with `parent_ref`. `reopen_policy="extend"`: the original spell stays open and `reopened_count` increments. The choice enters `params_hash`, so two tenants with different policies never silently compare. |
| **C7** | A request merged into another is excluded, with `n_excluded` incremented and `exclusion_reason="merged_duplicate"`. The survivor's `duplicate_count` increments. Counting both double-counts the demand; counting neither loses it. |
| **C8** | `duration_hours` is wall clock and is the default for every survival statistic, because the resident experiences wall clock. `duration_active_hours` exists for SLA attainment where the vertical declares that on-hold time stops the clock. **Which one a service used is in its `params_hash` and in its Method Card.** |
| **C9** | Censoring must be independent of the outcome for Kaplan-Meier to be unbiased. It is not automatically true here: an admin bulk-closing stale tickets is informative censoring. Every survival service runs the `censoring-informative` check, comparing the covariate distribution of censored versus observed spells, and downgrades to WARN with an explicit caveat when they diverge. |
| **C10** | Never impute, never interpolate, never carry forward a terminal timestamp. If it is unknown it is censored. |

#### Unit: periodised counts, for SPC, queueing and forecasting

```python
@dataclass(frozen=True)
class FlowPeriod:
    period_start: datetime
    period_end: datetime
    arrivals: int                    # opened_at in period
    terminals: int                   # any terminal in period
    resolutions: int                 # outcome == "resolved"
    backlog_end: int                 # open at period_end. Little's Law L.
    backlog_start: int
    active_servers: float            # see the cross-stream note below
    arrival_rate_per_day: float
    exposure_days: float             # period length, for Poisson rate charts with unequal periods
    complete: bool                   # period_end <= window.complete_through
```

`active_servers` is the one input Pack 1 needs that no single stream produces. It is the count of
distinct people who could work a request in that period, which is a `member_lifecycle` role fact
crossed with `request_flow` assignment activity. It is computed by a declared cross-stream reducer,
`streams.capacity.active_servers(roster, request_events, period)`, with the rule stated in the
Erlang-C Method Card. Flagged explicitly rather than smuggled in: see §7.

### Consumers

`survival.*`, `spc.*`, `queueing.*`, `changepoint.*`, `fairness.*`, `conformal.*`, `forecast.*`,
`bayes.*` (assignee and vendor rates), `text.*` (via `signal`).

---

## 3. `ledger`

Signed money movement. Grounded in the RWA interview evidence: bank transfer, screenshot to
WhatsApp, manual treasurer verification, physical register, receipt frequently never collected.
The spine records that whole path so we can measure it rather than assume it.

### Atom

```python
@dataclass(frozen=True)
class LedgerEntry:
    entry_ref: str
    at: datetime                   # value date: when the money moved
    booked_at: datetime            # when it was recorded in the system
    amount_minor: int              # SIGNED. inflow positive, outflow negative.
    currency: str                  # ISO 4217
    category: str                  # "maintenance_dues" | "stp_maintenance" | "festival_fund" | ...
    subcategory: str | None
    direction: Literal["inflow", "outflow"]     # redundant with sign, kept for adapter safety
    member_ref: str | None         # payer or payee if a member
    counterparty_ref: str | None   # vendor, contractor, bank. Pseudonymous.
    group_ref: str | None
    campaign_ref: str | None       # event or fundraiser this belongs to
    instrument: Literal["upi", "bank_transfer", "cash", "cheque", "card", "in_kind", "adjustment"]
    status: Literal["expected", "pending", "settled", "failed", "reversed", "written_off"]
    due_at: datetime | None        # receivables only
    settled_at: datetime | None
    reversal_of: str | None
    verified_at: datetime | None   # treasurer confirmed it. The WhatsApp-screenshot lag.
    verified_by_ref: str | None
    receipt_issued_at: datetime | None
    receipt_collected_at: datetime | None
    reconciled: bool
    attributes: Mapping[str, float | str] = ()
```

`verified_at`, `receipt_issued_at` and `receipt_collected_at` are not bookkeeping decoration. The
gap between `at` and `verified_at` is the manual-verification lag the ex-Secretary described, and
the gap between issued and collected is the receipt-adoption gap. Both are directly measurable
`request_flow`-shaped durations and both are `rwa_society` headline statistics.

### Units

```python
@dataclass(frozen=True)
class DueSpell:                    # a receivable as a time-to-event record
    due_ref: str
    member_ref: str
    issued_at: datetime
    due_at: datetime
    amount_minor: int
    at_risk_from: datetime
    settled_at: datetime | None
    duration_days: float           # due_at -> min(settled_at, window.end); negative if early
    event_observed: bool           # settled inside the window
    censoring: CensoringKind
    partial_paid_minor: int
    reminders_sent: int
    strata: Mapping[str, str]

@dataclass(frozen=True)
class LedgerPeriod:
    period_start: datetime
    period_end: datetime
    inflow_minor: int
    outflow_minor: int
    net_minor: int
    closing_balance_minor: int | None
    by_category: Mapping[str, int]
    complete: bool                 # respects window.complete_through
```

Rules: **L1** an unpaid due is right-censored, exactly like an open request; the "average days to
pay" of only the paid dues is the same defect as C1. **L2** `expected` entries are forecast inputs,
never actuals; a service mixing them must say so in a caveat. **L3** a reversal is a new signed
entry, never a mutation of the original, so Benford and audit statistics see the true digit
distribution.

### Consumers

`forecast.*`, `montecarlo.runway_shortfall`, `risk.late_payment_risk`, `survival.*` (via
`DueSpell`), `privacy.*`, `budgeting.*` (as the budget envelope), `audit.benford_digits`.

---

## 4. `participation`

Anything a member does that is not a request and not money.

### Atom

```python
ParticipationKind = Literal[
    "rsvp", "rsvp_cancel", "attend", "no_show",
    "login", "post", "comment", "upvote", "read_receipt",
    "volunteer_hours", "training_complete", "in_kind_contribution",
    "nudge_sent", "nudge_delivered", "nudge_opened", "nudge_acted",   # the exposure log; see S7
]

@dataclass(frozen=True)
class ParticipationEvent:
    member_ref: str
    at: datetime
    kind: ParticipationKind
    object_ref: str | None         # event, announcement, request, poll, campaign
    object_kind: str | None
    group_ref: str | None
    weight: float = 1.0            # hours for volunteer_hours, 1.0 otherwise
    channel: str | None = None     # "app" | "whatsapp" | "email" | "sms" | "notice_board"
    arm_ref: str | None = None     # experiment / bandit arm, for nudge_* kinds only
    strata: Mapping[str, str] = ()
```

The `nudge_*` kinds are the **exposure log**, and they are an addition the six-stream sketch did
not have. Pack 2's A/B tests and bandits need to know who was *offered* what, not only who acted.
Without it, a nudge experiment is measuring self-selection. Flagged in §7.

### Units

```python
@dataclass(frozen=True)
class EngagementFeatures:          # RFM, generalised
    member_ref: str
    recency_days: float            # since last participation of any kind
    frequency_90d: int
    breadth: int                   # distinct participation kinds used
    volunteer_hours_365d: float
    tenure_days: float
    contribution_minor: int        # from ledger; the one deliberate cross-stream feature
    channels: frozenset[str]
    strata: Mapping[str, str]

@dataclass(frozen=True)
class InteractionEdge:
    a_ref: str
    b_ref: str                     # undirected, canonically ordered a_ref < b_ref
    weight: float
    basis: Literal["co_attendance", "co_request", "reply", "co_vote", "co_group"]

@dataclass(frozen=True)
class ParticipationPeriod:
    period_start: datetime
    period_end: datetime
    active_members: int
    events_by_kind: Mapping[str, int]
    total_weight: float
    complete: bool
```

**Edge construction rule.** Co-attendance is a bipartite projection and must be normalised:
an event with `m` attendees contributes `1/(m-1)` to each pair, not `1`. Without it a 200-person
annual general meeting makes every member a connector and betweenness centrality becomes noise.
The normalisation constant is a declared parameter and enters `params_hash`.

### Consumers

`segmentation.*`, `network.*`, `experiments.*`, `bandits.*`, `forecast.*` (attendance),
`risk.member_disengagement_risk`, `voting.turnout_representativeness`.

---

## 5. `signal`

Free text and ordinal ratings.

### Atoms

```python
@dataclass(frozen=True)
class SignalRecord:                # inside the tenant boundary only
    signal_ref: str
    at: datetime
    source: Literal["request_body", "request_comment", "survey_free_text", "feedback", "minutes"]
    object_ref: str | None         # the request / survey this belongs to
    member_ref: str | None         # pseudonymous. STRIPPED before any text service or LLM call.
    text: str
    language: str | None
    redaction: Literal["raw", "pii_redacted", "unredacted_forbidden"] = "raw"
    category_hint: str | None
    strata: Mapping[str, str] = ()

@dataclass(frozen=True)
class TextDoc:                     # what text services actually receive. No identity field exists.
    doc_ref: str
    at: datetime
    text: str
    tokens: tuple[str, ...]
    embedding: tuple[float, ...] | None    # computed upstream; stats never calls a model
    category_hint: str | None

@dataclass(frozen=True)
class OrdinalResponse:
    response_ref: str
    at: datetime
    item_id: str                   # the survey question
    scale_min: int                 # inclusive
    scale_max: int                 # inclusive
    value: int                     # NOT a float. There is nowhere to put a mean.
    respondent_ref: str
    strata: Mapping[str, str]
    covariates: Mapping[str, float | str] = ()
```

`TextDoc` having no identity field is the mechanism, not a policy. `text.near_duplicate_candidates`
cannot leak an author because it was never handed one. The service layer keeps the
`doc_ref -> member_ref` map and re-attaches names after the statistics are done, under its own
k-anonymity check.

Embeddings arrive precomputed. `app/stats/` never calls an embedding model: that would be network
I/O and would break purity. The vector is an input.

### Consumers

`text.*`, `survey.ordinal_logistic`, `survey.likert_distribution`, `segmentation.*`.

---

## 6. `decision`

Polls, elections, budget allocations, referenda.

### Atoms

```python
@dataclass(frozen=True)
class DecisionSpec:
    decision_ref: str
    kind: Literal["poll", "election", "budget_allocation", "referendum"]
    opened_at: datetime
    closed_at: datetime | None
    declared_rule: str             # "schulze" | "stv" | "approval" | "borda" | "mes" | "greedy"
    seats: int = 1
    quorum_rule: str | None = None # "none" | "fraction:0.25" | "count:50"
    budget_minor: int | None = None
    eligible_strata: Mapping[tuple[str, ...], int] = ()   # from RosterSnapshot at opened_at
    ballot_style: Literal["ranked", "approval", "score", "single", "allocation"] = "ranked"

@dataclass(frozen=True)
class DecisionOption:
    option_ref: str
    decision_ref: str
    label: str
    cost_minor: int | None = None  # budget_allocation only
    tags: tuple[str, ...] = ()
    proposer_ref: str | None = None

@dataclass(frozen=True)
class Ballot:
    ballot_ref: str
    decision_ref: str
    voter_ref: str                 # pseudonymous, and NOT joinable to member_ref outside the
                                   # service layer's sealed map. Secret-ballot verticals drop it.
    cast_at: datetime
    ranking: tuple[tuple[str, ...], ...] = ()   # tuple of tiers; inner tuple = tied options
    approvals: frozenset[str] = frozenset()
    scores: Mapping[str, int] = ()
    allocation: Mapping[str, int] = ()          # option_ref -> minor units
    strata: Mapping[str, str] = ()              # for representativeness only, never per-ballot display
    channel: str | None = None
```

`ranking` is a tuple of tiers, not a flat list, because real ballots have ties and truncation.
An option absent from every tier is unranked, which Borda, Schulze and STV each treat differently;
the treatment is a declared parameter of each service, not an implicit default.

**Rule D1: `declared_rule` is recorded when the decision opens, before any ballot is cast.** The
platform may compute and *disclose* other rules' winners, and must disclose a Condorcet cycle, but
the declared rule decides. This structurally prevents rule-shopping after the fact, which is the
one governance failure a voting module can actually cause.

**Rule D2: per-stratum ballot breakdowns are subject to the vertical's k-anonymity floor with no
override.** "How Block C voted", where Block C is nine households, is a disclosure.

### Consumers

`voting.*`, `budgeting.*`, `survey.raking_weights`, `sortition.*`, `privacy.*`.

---

## 7. Coverage: what every Pack service consumes

Read this as the acceptance check for A.2. Each service names the stream units it takes. If a
service is not in this table, it does not exist.

### Pack 1, Reliability & Service Ops

| Service | Units consumed | Key fields |
|---|---|---|
| `survival.km_resolution_curve` | `RequestSpell[]` | `duration_hours`, `event_observed`, `at_risk_from`, `left_truncated` |
| `survival.median_resolution_days` | `RequestSpell[]` | as above |
| `survival.sla_attainment` | `RequestSpell[]` | `duration_active_hours` or `duration_hours`, `event_observed` |
| `survival.first_response_curve` | `RequestSpell[]` | `first_response_hours`, `event_observed` |
| `survival.logrank_compare` | `RequestSpell[]` | + `category` / `location_ref` / `assignee_ref` as the strata key |
| `survival.cox_hazard_ratios` | `RequestSpell[]` | + `covariates`, `priority`, `channel`, `CalendarMark` |
| `survival.competing_risks_cif` | `RequestSpell[]` | `outcome`, `terminal_at`, `censoring` |
| `survival.churn_curve` | `MemberSpell[]` | `duration_days`, `event_observed`, `strata_at_entry` |
| `spc.ewma_chart` | `FlowPeriod[]` | `arrivals` or `resolutions`, `exposure_days`, `complete` |
| `spc.cusum_chart` | `FlowPeriod[]` | as above |
| `spc.poisson_rate_chart` | `FlowPeriod[]` | `arrivals`, `exposure_days` |
| `changepoint.detect_level_shifts` | `FlowPeriod[]` \| `LedgerPeriod[]` | the series and `period_start` |
| `queueing.little_law_wait` | `FlowPeriod[]` | `backlog_end`, `arrivals`, `exposure_days` |
| `queueing.mmc_metrics` | `FlowPeriod[]` + service-time summary from `RequestSpell[]` | `active_servers`, `arrival_rate_per_day` |
| `queueing.erlang_c_staffing` | as above | `active_servers`, target SLA |
| `queueing.mg1_wait` | `RequestSpell[]` | `duration_hours` mean and variance for closed spells, plus censoring caveat |
| `fairness.workload_gini` | `RequestSpell[]` | `assignee_ref`, counts |
| `fairness.balanced_assignment` | `RequestSpell[]` + `RosterSnapshot` | `assignee_ref`, `category`, `roles` |

### Pack 2, Bayesian Ranking & Experimentation

| Service | Units consumed | Key fields |
|---|---|---|
| `bayes.fit_beta_prior` | `RateObservation[]` (derived) | `successes`, `trials`, `group_ref` |
| `bayes.beta_binomial_shrink` | `RateObservation[]` | as above |
| `bayes.gamma_poisson_shrink` | `CountObservation[]` (derived) | `events`, `exposure` |
| `bayes.rank_by_posterior_lower_bound` | posteriors from the above | |
| `bayes.hierarchical_pool` | `RateObservation[]` across anonymised tenant keys | `group_key` only, never a tenant id |
| `experiments.beta_ab_test` | `ParticipationEvent[]` with `arm_ref` | `nudge_sent`, `nudge_acted`, `arm_ref` |
| `experiments.expected_loss` | as above | |
| `experiments.sequential_stopping_rule` | as above, ordered by `at` | |
| `bandits.thompson_sampling_policy` | as above + seed | |
| `bandits.freeze_and_report` | posterior state | |
| `pairwise.bradley_terry` | `PairwiseResult[]` (derived from `RequestSpell` head-to-heads or `Ballot`) | `winner_ref`, `loser_ref` |
| `pairwise.elo_update` | as above, time-ordered | |

`RateObservation` and `CountObservation` are thin derived units:
`(group_ref, successes, trials, window)` and `(group_ref, events, exposure, window)`. They are
produced by reducers from `RequestSpell` (vendor resolved-within-SLA rate), `DueSpell` (on-time
payment rate) or `ParticipationEvent` (attendance rate), so one shrinkage implementation serves all
three.

### Pack 3, Forecasting & Calibrated Risk

| Service | Units consumed | Key fields |
|---|---|---|
| `forecast.stl_decompose` | any `*Period[]` | value series, `period_start`, `complete` |
| `forecast.seasonal_naive` | any `*Period[]` | as above |
| `forecast.holt_winters` | any `*Period[]` | as above + `CalendarMark` for holiday regressors |
| `forecast.sarima` | any `*Period[]` | as above |
| `forecast.rolling_origin_backtest` | any `*Period[]` | as above. **The gate.** |
| `montecarlo.runway_shortfall` | `LedgerPeriod[]` + a forecast + seed | `net_minor`, `closing_balance_minor` |
| `risk.late_payment_risk` | `DueSpell[]` + `EngagementFeatures[]` | `event_observed`, `duration_days`, `reminders_sent`, RFM |
| `risk.member_disengagement_risk` | `MemberSpell[]` + `EngagementFeatures[]` | `recency_days`, `frequency_90d`, `breadth` |
| `calibration.isotonic_calibrate` | score/label arrays | |
| `calibration.platt_calibrate` | score/label arrays | |
| `calibration.brier_decomposition` | probability/label arrays | |
| `calibration.reliability_diagram` | probability/label arrays | |
| `conformal.split_conformal_interval` | prediction/residual arrays | |
| `conformal.survival_eta_bound` | `RequestSpell[]` | `duration_hours`, `event_observed`, `covariates`. Censoring-aware. |
| `conformal.mondrian_eta` | `RequestSpell[]` | + `category` as the taxonomy |
| `drift.psi` | feature arrays, reference vs current | |
| `drift.ks_test` | feature arrays | |

### Pack 4, Governance, Segmentation & Text

| Service | Units consumed | Key fields |
|---|---|---|
| `voting.pairwise_matrix` | `Ballot[]`, `DecisionOption[]` | `ranking` |
| `voting.condorcet_winner` | as above | |
| `voting.schulze` | as above | |
| `voting.borda` / `voting.approval` / `voting.score` | as above | `ranking`, `approvals`, `scores` |
| `voting.stv` | as above | `ranking`, `DecisionSpec.seats` |
| `voting.turnout_representativeness` | `Ballot[]` + `DecisionSpec.eligible_strata` | `strata` |
| `budgeting.method_of_equal_shares` | `Ballot[]`, `DecisionOption[]` | `approvals` or `allocation`, `cost_minor`, `budget_minor` |
| `budgeting.greedy_knapsack` | as above | |
| `budgeting.fairness_report` | as above + `RosterSnapshot` | `strata` |
| `sortition.stratified_panel` | `RosterSnapshot` + volunteer pool + seed | `counts_by_stratum` |
| `survey.raking_weights` | `OrdinalResponse[]` + `RosterSnapshot` | `strata` |
| `survey.design_effect` | weights | |
| `survey.ordinal_logistic` | `OrdinalResponse[]` | `value`, `scale_min`, `scale_max`, `covariates` |
| `survey.likert_distribution` | `OrdinalResponse[]` | `value`, `strata` |
| `segmentation.rfm_features` | `ParticipationEvent[]` + `LedgerEntry[]` | see `EngagementFeatures` |
| `segmentation.gmm_select_k` | `EngagementFeatures[]` | |
| `segmentation.stable_labels` | two label assignments + centroids | |
| `network.louvain_communities` | `InteractionEdge[]` | `a_ref`, `b_ref`, `weight` |
| `network.betweenness_centrality` | `InteractionEdge[]` | |
| `network.isolation_report` | `InteractionEdge[]` + `RosterSnapshot` | |
| `text.tfidf_similarity` | `TextDoc[]` | `tokens` |
| `text.near_duplicate_candidates` | `TextDoc[]` | `tokens`, `embedding` |
| `text.nmf_topics` | `TextDoc[]` | `tokens` |
| `privacy.k_anonymity_suppress` | any `table`-shaped `Evidence` + cell counts | |
| `privacy.laplace_noise` | any numeric aggregate + sensitivity + epsilon | |
| `audit.benford_digits` | `LedgerEntry[]` | `amount_minor` |

---

## 8. Fields the packs needed that the six-stream sketch did not have

Recorded honestly, because pretending the spine fell out clean would be the first dishonest thing
in a product whose entire claim is honesty.

| Field / unit | Which service forced it | Why no stream naturally had it |
|---|---|---|
| `StreamWindow.complete_through` | every forecaster, every SPC chart | Reporting lag is a property of the *pipeline*, not of any event. Without it the last partial bucket reads as a collapse. |
| `RequestSpell.at_risk_from` + `left_truncated` | `survival.*` | Delayed entry is invisible if you only store `opened_at` and a window. |
| `RequestSpell.paused_hours` / `duration_active_hours` | `survival.sla_attainment` | Two legitimate clocks exist and picking one silently makes tenants incomparable. |
| `FlowPeriod.active_servers` | `queueing.erlang_c_staffing`, `queueing.mmc_metrics` | Genuinely cross-stream: a roster fact from `member_lifecycle` crossed with assignment activity in `request_flow`. Implemented as a named cross-stream reducer, `streams.capacity.active_servers`, not hidden inside the queueing module. |
| `DecisionSpec.eligible_strata` | `voting.turnout_representativeness` | The denominator is a `member_lifecycle` snapshot frozen at `opened_at`, not a `decision` fact. Frozen at open time so a later move-in cannot change a past turnout figure. |
| `ParticipationEvent` kinds `nudge_sent` / `nudge_delivered` / `nudge_opened` / `nudge_acted` plus `arm_ref` | `experiments.*`, `bandits.*` | The **exposure log**. A nudge that was sent is not a member action, so no purely member-centric participation stream contains it. Without it, an A/B test measures self-selection rather than the nudge. |
| `LedgerEntry.verified_at`, `receipt_issued_at`, `receipt_collected_at` | `rwa_society` headline statistics | Direct from the interview evidence: the screenshot-to-verification lag and the receipt-collection gap. A generic ledger would carry neither. |
| `LedgerEntry.status == "expected"` | `montecarlo.runway_shortfall` | Receivables must be distinguishable from actuals or the runway is fiction. |
| `drift.*` reference distribution | `drift.psi`, `drift.ks_test` | **Not stream data at all.** It is a stored artifact of a previous fit. It arrives as an explicit argument, and the service layer, not `stats/`, is responsible for retrieving it. |
| `InteractionEdge.basis` + projection normalisation constant | `network.*` | The interaction graph is derived, and the derivation rule materially changes the answer, so it is declared and hashed rather than assumed. |

Nothing else in Packs 1 to 4 required a field the six streams do not define.

---

## 9. The adapter contract

A vertical adapter is the only code that knows domain words. It is impure at the repository edge
and its output is validated before it reaches `stats/`.

```python
class VerticalAdapter(Protocol):
    vertical_id: str
    strata_schema: Mapping[str, tuple[str, ...]]   # stratum name -> allowed low-cardinality values
    request_categories: tuple[str, ...]
    request_priorities: tuple[str, ...]
    exit_reasons: tuple[str, ...]
    ledger_categories: tuple[str, ...]
    k_anonymity_threshold: int
    reopen_policy: Literal["new_spell", "extend"]
    sla_clock: Literal["wall", "active"]

    def member_events(self, rows) -> tuple[MemberEvent, ...]: ...
    def request_events(self, rows) -> tuple[RequestEvent, ...]: ...
    def ledger_entries(self, rows) -> tuple[LedgerEntry, ...]: ...
    def participation_events(self, rows) -> tuple[ParticipationEvent, ...]: ...
    def signals(self, rows) -> tuple[SignalRecord, ...]: ...
    def decisions(self, rows) -> tuple[DecisionSpec, ...]: ...
```

**Adapter obligations, checked by a shared conformance test suite every vertical must pass:**

1. Every emitted `category`, `priority`, `reason` and stratum value is in the declared vocabulary.
   An unmapped domain value becomes `"other"` and increments a counter that surfaces as a caveat,
   never a silent drop.
2. Every stratum is low-cardinality: at most `min(20, roster_size // k_anonymity_threshold)` values.
3. Timestamps are UTC and monotonic per entity: no `resolved` before `opened`.
4. `amount_minor` is `int`, currency is uniform per tenant unless the manifest declares otherwise.
5. Terminal events are unique per `request_ref` under the declared `reopen_policy`.
6. `TextDoc` construction strips `member_ref`. The adapter cannot produce a `TextDoc` with identity
   because the type has no field for it.
7. The adapter never filters on outcome. Filtering to closed requests at the adapter is exactly the
   defect C1 exists to prevent, and the conformance suite includes a fixture with open requests that
   must survive the adapter untouched.

A vertical that supports only some streams declares the rest empty. A service whose required stream
is empty returns `InsufficientData`, which the pack registry turns into "this pack needs the ledger
switched on", not an error.

---

## 10. Open questions carried to A.3 and later

- Interval-censored spells (C4) need a Turnbull estimator to be handled properly. Pack 1 ships with
  the threshold rule instead, reporting `insufficient_data` above 20% interval-censored rows.
  Turnbull is a later card, and the Method Card says so rather than pretending the case is covered.
- Cross-tenant hierarchical pooling (`bayes.hierarchical_pool`) receives an anonymised `group_key`.
  **Resolved:** each tenant's contribution is a differentially private sufficient statistic, not
  raw data, at a declared per-quarter epsilon budget, and the pool refreshes on a fixed cadence
  rather than live, so no single update is isolable by differencing. Full mechanism and its blocking
  checks are in `docs/STATS_CATALOG.md` under `bayes.hierarchical_pool`. No longer a blocker; it is
  now a required part of the service's implementation, gated by the sensitivity test alongside the
  usual known-answer test.
- `duration_active_hours` requires paired `paused` / `resumed` events. Verticals that cannot supply
  them declare `sla_clock="wall"` and the alternative is simply unavailable, rather than
  approximated.
