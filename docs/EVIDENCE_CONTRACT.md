# The Evidence contract

*Card A.1. Status: draft 1.*

Every statistic this platform produces travels in one envelope. Not most. Every one.

---

## 1. Why this exists

A community app that shows "average resolution time: 3.2 days" has told you almost nothing. It has
not told you that the figure came from 9 tickets, that 40 more are still open and were silently
dropped, that the 95% interval runs from 1.1 to 11 days, or that last month's number was computed a
different way. Every one of those omissions is the difference between a number a secretary can act
on and a number that quietly misleads a committee into firing a vendor.

The envelope makes those omissions **structurally impossible** rather than a matter of discipline:

- A service that wants to return a float **cannot** — the return type is `Evidence`.
- A component that wants to render a number **cannot** — the prop is `Evidence`.
- An LLM that wants to state a figure **cannot invent one** — its tools return envelopes and the
  grounding layer rejects any number not present in one.

Three separate layers, one type. That is the whole design.

---

## 2. The types

```python
# backend/app/stats/contracts.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

CheckStatus = Literal["PASS", "WARN", "FAIL", "SKIPPED"]

IntervalKind = Literal[
    "none",             # the value is exact — a count, a rank, a sum
    "normal-95",        # asymptotic normal CI
    "bootstrap-bca-95", # bias-corrected accelerated bootstrap
    "greenwood-95",     # Kaplan-Meier pointwise CI
    "profile-95",       # profile likelihood
    "credible-95",      # Bayesian posterior — NOT a confidence interval
    "credible-89",
    "conformal-90",     # distribution-free, guaranteed marginal coverage
    "conformal-95",
    "predictive-80",    # forecast prediction interval
    "predictive-95",
    "control-limits",   # SPC chart limits — a decision boundary, not an estimate
]


@dataclass(frozen=True)
class Check:
    """One automatic assumption test, run by the service on its own output."""
    id: str                      # "proportional-hazards", "seasonality-stable"
    label: str                   # human sentence: "Hazards stay proportional over time"
    status: CheckStatus
    statistic: float | None = None
    p_value: float | None = None
    detail: str = ""             # what a FAIL means for reading this number
    blocking: bool = False       # True → the value must not be read as an estimate at all


@dataclass(frozen=True)
class Evidence:
    value: Any                   # float | int | dict | list — see §4
    n: int                       # observations the estimate actually rests on
    method: str                  # registry id → resolves to a MethodCard
    as_of: datetime              # when the underlying data was read (UTC, tz-aware)

    interval: tuple[float, float] | None = None
    interval_kind: IntervalKind = "none"

    assumptions: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()
    caveats: tuple[str, ...] = ()

    insufficient_data: bool = False
    n_censored: int = 0          # for time-to-event: how many are still open
    n_excluded: int = 0          # dropped for a stated reason
    exclusion_reason: str = ""

    unit: str = ""               # "days", "INR", "requests/week", "probability"
    params_hash: str = ""        # see §7
    contract_version: int = 1


@dataclass(frozen=True)
class MethodCard:
    id: str                      # matches Evidence.method
    name: str
    one_liner: str               # what it answers, in a sentence a secretary understands
    assumes: tuple[str, ...]
    wrong_when: tuple[str, ...]  # the honest failure modes
    min_n: int
    interval_meaning: str        # plain-language reading of THIS interval kind
    references: tuple[str, ...]


class InsufficientData(Exception):
    """Raised only when a service cannot even construct a shaped Evidence."""
    def __init__(self, method: str, n: int, min_n: int, reason: str = ""):
        ...
```

### Why these fields and not others

- **`n` is mandatory and separate from `value`.** It is the single most load-bearing number on the
  screen and it must never be optional.
- **`n_censored` exists as its own field** because for `request_flow` the count of still-open
  requests is not a footnote — it is the field that catches the industry's most common bug. See §6.
- **`checks` are computed by the service, not asserted by the author.** A hand-written
  "assumes proportional hazards" in `assumptions` is a claim. A Schoenfeld test in `checks` is a
  measurement. Both are present; only the second can fail loudly.
- **`interval_kind` is not decoration.** A credible interval and a confidence interval mean
  different things and the UI must be able to say which it is showing. `"none"` is a legitimate
  value for exact quantities — a count has no interval and pretending otherwise is worse than
  omitting it.
- **`blocking` on a `Check`** separates "read this with care" from "this number is not
  interpretable". Only the second suppresses the value.

---

## 3. The four render states

The UI has exactly four ways to display an `Evidence`, and every component must handle all four.
These are decided by the data, never by the component.

| State | Condition | Render |
|---|---|---|
| **Estimate** | `not insufficient_data`, no `FAIL` check | Value, unit, interval, `n`. The normal case. |
| **Qualified** | a non-blocking `FAIL` or any `WARN` | Value shown, with the failing check's `label` and `detail` inline. Not hidden, not styled as clean. |
| **Not interpretable** | any `FAIL` with `blocking=True` | Value **suppressed**. The check's `detail` shown in its place. |
| **Not enough data** | `insufficient_data` | Calm empty state naming what is needed: "needs 30 closed requests, has 11". Never an error colour, never an exclamation mark. |

**The not-enough-data state is the one that decides whether people trust this product.** A tenant in
its first month will see it constantly. If it reads as a failure, users learn that honesty looks
broken and start preferring tools that lie. It must look deliberate and calm. Design it first.

---

## 4. Shapes of `value`

`value` is typed by the service, not free-form. Four shapes, and services declare which one:

| Shape | `value` | Example |
|---|---|---|
| `scalar` | `float \| int` | median resolution days; collection rate |
| `series` | `{"x": [...], "y": [...], "lo": [...], "hi": [...]}` | a Kaplan-Meier curve with its Greenwood band |
| `table` | `[{...}, ...]` — homogeneous rows, each with its own `n` | shrunk vendor ranking; per-category hazard ratios |
| `structure` | a named dict specific to the method | a control chart (`{"points", "center", "ucl", "lcl", "signals"}`) |

**A `table` row carrying a per-row statistic carries its own `n` and interval.** A ranked list where
only the outer envelope has an `n` is a bug — the whole point of the shrinkage services is that row
5 rests on 3 observations and row 1 on 200.

---

## 5. Wire format

Snake-case JSON, `datetime` as ISO-8601 UTC. Nothing is dropped when serializing — a field the
frontend currently ignores is still sent, because the Method Card page and the agent both read them.

```json
{
  "value": 4.1,
  "n": 187,
  "method": "survival.median_resolution_days",
  "as_of": "2026-08-29T04:15:00Z",
  "interval": [3.2, 5.6],
  "interval_kind": "greenwood-95",
  "assumptions": ["Censoring is independent of resolution speed"],
  "checks": [
    {
      "id": "censoring-informative",
      "label": "Open requests are not systematically the hard ones",
      "status": "WARN",
      "statistic": 0.31,
      "p_value": 0.04,
      "detail": "Requests open past 30 days skew to the plumbing category. The median may be optimistic.",
      "blocking": false
    }
  ],
  "caveats": [],
  "insufficient_data": false,
  "n_censored": 44,
  "n_excluded": 0,
  "exclusion_reason": "",
  "unit": "days",
  "params_hash": "e3f1a9c2",
  "contract_version": 1
}
```

`GET /api/methods/{method}` returns the Method Card. The frontend links every figure to it.

---

## 6. The `n_censored` rule

This is the field the contract exists for.

For any time-to-event statistic over `request_flow`, an open request has an **unknown** resolution
time — we know only that it exceeds its current age. Excluding it does not make the estimate
neutral; it makes it **biased downward**, because slow requests are exactly the ones still open.

Therefore:

1. `n` counts **all** requests entering the estimate, censored ones included.
2. `n_censored` reports how many were censored. The UI shows it whenever it is non-zero.
3. `n_excluded` is only for observations dropped for a stated structural reason (a malformed
   timestamp, a request outside the window), and `exclusion_reason` must say what.
4. **Any service that computes a duration by averaging only closed items is a defect**, regardless
   of test coverage. There is a permanent regression test for this — see `docs/RULES.md` §7.

---

## 7. `params_hash` and reproducibility

A short stable digest over: the method id, the method's version, every tuning parameter, the window
bounds, and the filter predicate. Two envelopes with the same `params_hash` and the same `as_of`
must be byte-identical.

It does three jobs: it is the cache key in `insight_runs`; it lets the UI say *"computed differently
from last month"* instead of silently comparing incomparable numbers; and it makes a bug report
reproducible from the screenshot.

**Excluded from the hash:** the tenant id and the data itself. The hash identifies *how* a number
was computed, not *what* it was computed from.

---

## 8. Minimum-n policy

Each service declares `min_n` in its Method Card. Below it, the service returns
`Evidence(insufficient_data=True, n=<actual>)` with a shaped-but-empty `value`. It does **not**
raise, and it does **not** return a number with a wide interval and hope the reader notices.

`InsufficientData` is raised only when a shaped envelope cannot be constructed at all — for example
the stream is entirely absent because the tenant has not enabled that domain.

Defaults, overridable per service with a stated reason:

| Family | `min_n` | Why |
|---|---|---|
| Descriptive scalar | 10 | Below this, an interval is wider than the range of plausible answers |
| Kaplan-Meier curve | 30 events (not rows) | Fewer and the curve is a staircase of single observations |
| Cox regression | 10 events **per covariate** | The standard events-per-variable rule; below it coefficients are unstable |
| SPC control chart | 20 periods | Limits estimated from fewer are themselves too noisy to signal against |
| Changepoint | 24 periods | Needs enough on both sides of any candidate point |
| Seasonal forecast | 2 full seasonal cycles | Cannot estimate a seasonal term you have not seen twice |
| Beta-Binomial shrinkage | 5 groups | The prior is estimated from the groups; fewer and there is nothing to pool |
| Clustering | 50 members | Below this, cluster structure is indistinguishable from noise |
| Any published per-stratum cell | `k = 5` members | k-anonymity floor. Suppressed, not noised, below it |

The last row is a **hard floor that overrides every other consideration**, including a tenant admin
asking to see it. A per-block statistic over three households identifies those households.

---

## 9. Obligations by layer

**A statistics module** (`backend/app/stats/`) — returns `Evidence`, never a bare float. Computes
its own `checks` rather than asserting them in prose. Sets `n`, `n_censored`, `unit`, `method`,
`params_hash`. Stays pure: no DB, no network, deterministic, seeded randomness.

**A service** — fetches stream rows, calls a pure function, stores the returned envelope in
`insight_runs` **whole**. It must not unwrap, round, re-round, recombine, or derive from an
envelope. Deriving a new statistic from two envelopes is a statistics-module job, not a service job,
because it needs its own interval and its own `n`.

**An API route** — serializes the envelope entire. No trimming for payload size.

**A frontend component** — takes `evidence: Evidence`, never `value: number`. Handles all four
states in §3. Shows `n`; shows `n_censored` when non-zero; shows the interval; links `method` to its
card.

**The AI agent** — its tools return envelopes. It may quote a value, its interval and its `n`; it
may explain a failing check. It must not do arithmetic on envelopes, combine them, compare two into
a new claim, or state a figure absent from one. Enforced by a grounding test, not by the prompt.

---

## 10. Versioning

`contract_version` is on every envelope. A materialized `insight_run` from an older version is
served with a "computed under an older method" marker rather than silently mixed into a trend. When
a method's mathematics changes, its **version changes**, which changes `params_hash`, which
invalidates the cache — automatically and without a migration.

---

## Open questions for A.2

- Does `series` need a per-point `n` for the survival curve's risk table, or is a parallel
  `at_risk` array cleaner? *Leaning: an `at_risk` array inside `value`, since it is intrinsic to
  the curve.*
- Should `Check` carry a suggested remedy for the tenant admin, or is that the Method Card's job?
  *Leaning: Method Card — the remedy is a property of the method, not of this run.*
