"""
The service registry: every statistic this platform can produce, in one place.

The shape deliberately mirrors `app/agent/tools.py` - a name, a description, a
declared input contract and a callable - so the two read alike. What is
different is what the registry refuses to accept:

1. A `ServiceSpec` whose `method_card` is missing, or whose card has no
   assumptions, no failure modes or no references, **raises at import**. That is
   `docs/RULES.md` section 4 as a load-time error rather than a review
   convention. A service without a Method Card is not done, and here it is not
   even importable.
2. `min_n` on the spec must equal `min_n` on the card. One floor, stated once.
3. `fn` must be annotated to return `Evidence`. A service cannot register a
   function that returns a float.
4. Streams and units must be names the spine defines, so a typo in
   `required_streams` fails the build rather than quietly making a pack look
   unavailable forever.

The registry is data about mathematics, not about a tenant. It contains no
tenant id, no cadence override and no enabled/disabled state: those live in the
vertical manifest (`docs/VERTICALS.md`) and in `Tenant.enabled_packs`, and are
applied on top of this by the service layer.

Catalog and code cannot drift: `tests/unit/stats/test_registry.py` asserts that
every service named in `docs/STATS_CATALOG.md` is registered here and that every
registered service is named there.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.stats import (
    audit,
    bandits,
    bayes,
    budgeting,
    calibration,
    changepoint,
    conformal,
    drift,
    experiments,
    fairness,
    forecast,
    montecarlo,
    network,
    pairwise,
    privacy,
    queueing,
    risk,
    segmentation,
    sortition,
    spc,
    survey,
    survival,
    text,
    voting,
)
from app.stats.contracts import Evidence, MethodCard, ValueShape
from app.stats.streams import STREAM_IDS, UNIT_NAMES

# ---------------------------------------------------------------------------
# Packs
# ---------------------------------------------------------------------------

RELIABILITY = "reliability_ops"
BAYES_RANKING = "bayes_ranking"
FORECAST_RISK = "forecast_risk"
GOVERNANCE = "governance_insight"

CADENCES: frozenset[str] = frozenset(
    {
        "hourly",
        "nightly",
        "weekly",
        "monthly",
        "weekly_platform",     # cross-tenant, runs once for the platform
        "on_demand",
        "on_write",
        "on_submission",
        "on_decision_close",
        "on_survey_close",
        "on_dispatch",
    }
)


@dataclass(frozen=True)
class PackSpec:
    id: str
    name: str
    required_streams: frozenset[str]
    default_cadence: str
    one_liner: str


PACKS: dict[str, PackSpec] = {
    RELIABILITY: PackSpec(
        id=RELIABILITY,
        name="Reliability and Service Ops",
        required_streams=frozenset({"request_flow", "member_lifecycle"}),
        default_cadence="nightly",
        one_liner=(
            "How long things actually take, counting the ones still open. The pack that "
            "sells the thesis."
        ),
    ),
    BAYES_RANKING: PackSpec(
        id=BAYES_RANKING,
        name="Bayesian Ranking and Experimentation",
        required_streams=frozenset({"request_flow", "participation", "ledger"}),
        default_cadence="nightly",
        one_liner="3 out of 3 is not better than 47 out of 52. Shrink, then rank by the lower bound.",
    ),
    FORECAST_RISK: PackSpec(
        id=FORECAST_RISK,
        name="Forecasting and Calibrated Risk",
        required_streams=frozenset({"ledger", "request_flow", "participation"}),
        default_cadence="weekly",
        one_liner=(
            "Forecasts that beat seasonal-naive or do not ship, and risk scores that are "
            "calibrated rather than merely well ranked."
        ),
    ),
    GOVERNANCE: PackSpec(
        id=GOVERNANCE,
        name="Governance, Segmentation and Text",
        required_streams=frozenset({"decision", "participation", "signal", "member_lifecycle"}),
        default_cadence="weekly",
        one_liner="Disclosure over tidiness, and a k-anonymity floor with no admin override.",
    ),
}


# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceSpec:
    """One statistical service, its contract, and the pure function behind it."""

    id: str                                 # "survival.median_resolution_days"
    pack: str
    fn: Callable[..., Evidence]             # the PURE function
    required_streams: frozenset[str]
    required_units: frozenset[str]          # "RequestSpell", "FlowPeriod"
    value_shape: ValueShape
    min_n: int
    default_cadence: str
    scope_dimensions: tuple[str, ...]       # which scope_key values are meaningful
    method_card: MethodCard
    version: int = 1                        # bumping it changes params_hash, invalidating the cache
    soft_depends_on: tuple[str, ...] = ()
    min_n_expression: str = ""              # where the floor is a function of a parameter
    implemented: bool = False

    def __post_init__(self) -> None:
        if self.pack not in PACKS:
            raise ValueError(self.id + " declares unknown pack " + repr(self.pack))
        if self.method_card.id != self.id:
            raise ValueError(
                self.id + " carries a Method Card for " + self.method_card.id
                + "; the card and the service must be the same thing"
            )
        if self.method_card.min_n != self.min_n:
            raise ValueError(
                self.id + " declares min_n " + str(self.min_n) + " but its Method Card says "
                + str(self.method_card.min_n) + "; one floor, stated once"
            )
        unknown_streams = self.required_streams - STREAM_IDS
        if unknown_streams:
            raise ValueError(self.id + " requires unknown streams " + repr(sorted(unknown_streams)))
        unknown_units = self.required_units - UNIT_NAMES
        if unknown_units:
            raise ValueError(self.id + " requires unknown units " + repr(sorted(unknown_units)))
        if self.default_cadence not in CADENCES:
            raise ValueError(self.id + " declares unknown cadence " + repr(self.default_cadence))
        returns = getattr(self.fn, "__annotations__", {}).get("return")
        if returns is not Evidence and returns != "Evidence":
            raise ValueError(
                self.id + " is bound to a function that is not annotated to return Evidence. "
                "No bare numbers cross a boundary."
            )

    @property
    def module(self) -> str:
        return self.id.split(".", 1)[0]

    def to_wire(self) -> dict:
        """What GET /api/methods and the packs endpoint serialize."""
        return {
            "id": self.id,
            "pack": self.pack,
            "required_streams": sorted(self.required_streams),
            "required_units": sorted(self.required_units),
            "value_shape": self.value_shape,
            "min_n": self.min_n,
            "min_n_expression": self.min_n_expression,
            "default_cadence": self.default_cadence,
            "scope_dimensions": list(self.scope_dimensions),
            "version": self.version,
            "soft_depends_on": list(self.soft_depends_on),
            "implemented": self.implemented,
            "method_card": self.method_card.to_wire(),
        }


REGISTRY: dict[str, ServiceSpec] = {}


def _register(spec: ServiceSpec) -> ServiceSpec:
    if spec.id in REGISTRY:
        raise ValueError("service " + spec.id + " is registered twice")
    REGISTRY[spec.id] = spec
    return spec


def _s(
    service_id: str,
    pack: str,
    fn: Callable[..., Evidence],
    *,
    streams: tuple[str, ...],
    units: tuple[str, ...],
    shape: ValueShape,
    min_n: int,
    cadence: str,
    scope: tuple[str, ...] = (),
    name: str,
    one_liner: str,
    assumes: tuple[str, ...],
    wrong_when: tuple[str, ...],
    interval: str,
    refs: tuple[str, ...],
    known: str = "",
    version: int = 1,
    soft: tuple[str, ...] = (),
    min_n_expr: str = "",
    implemented: bool = False,
) -> ServiceSpec:
    """Build and register one service and its Method Card in one place, so the two cannot drift."""
    return _register(
        ServiceSpec(
            id=service_id,
            pack=pack,
            fn=fn,
            required_streams=frozenset(streams),
            required_units=frozenset(units),
            value_shape=shape,
            min_n=min_n,
            default_cadence=cadence,
            scope_dimensions=scope,
            version=version,
            soft_depends_on=soft,
            min_n_expression=min_n_expr,
            implemented=implemented,
            method_card=MethodCard(
                id=service_id,
                name=name,
                one_liner=one_liner,
                assumes=assumes,
                wrong_when=wrong_when,
                min_n=min_n,
                interval_meaning=interval,
                references=refs,
                known_answer=known,
                version=version,
            ),
        )
    )


# Shorthands used repeatedly below.
_REQ = ("request_flow",)
_SPELL = ("RequestSpell",)
_CENSORING_ASSUMPTION = (
    "Open requests are censored at the observation boundary, never dropped (spine rule C1)."
)
_CENSORING_FAILURE = (
    "An admin bulk-closes stale tickets, which makes censoring informative and every "
    "duration optimistic (spine rule C9)."
)
_KM_REFS = (
    "Kaplan and Meier (1958) JASA 53:457",
    "Klein and Moeschberger, Survival Analysis, 2nd ed., ch. 4",
    "Andersen et al. on delayed-entry risk sets",
)


# ===========================================================================
# Pack 1: Reliability and Service Ops
# ===========================================================================

_s(
    "survival.km_resolution_curve", RELIABILITY, survival.km_resolution_curve,
    streams=_REQ, units=_SPELL, shape="series", min_n=30, cadence="nightly",
    scope=("category", "subcategory", "location_ref", "priority", "channel", "assignee_ref"),
    name="Kaplan-Meier resolution curve",
    one_liner="How likely a request is still unresolved after t days, counting the ones still open.",
    assumes=(
        _CENSORING_ASSUMPTION,
        "Censoring is unrelated to how long a request would have taken.",
        "Requests are exchangeable within a stratum.",
        "The event time is the terminal timestamp, not the time it was noticed.",
    ),
    wrong_when=(
        _CENSORING_FAILURE,
        "A material share of requests exit by escalation or withdrawal; the cumulative incidence "
        "function is the correct estimator then, not this one.",
        "Resolution timestamps were batch-imported and are only bracketed.",
    ),
    interval=(
        "The Greenwood band is a pointwise 95% confidence interval for the probability still "
        "unresolved at that day. It is not a band for the whole curve at once, so reading two "
        "points off it as a joint statement is wrong."
    ),
    refs=_KM_REFS,
    known=(
        "R survival::survfit(Surv(time, status) ~ 1, data = lung) estimates and risk table; the "
        "delayed-entry path against survfit(Surv(start, stop, event)) on the heart transplant "
        "data; plus the censoring regression fixture where the naive mean of closed spells is "
        "3.1 days and the Kaplan-Meier median is 8.0, asserting we report 8.0."
    ),
    min_n_expr="30 observed events, not 30 rows",
    implemented=True,
)

_s(
    "survival.median_resolution_days", RELIABILITY, survival.median_resolution_days,
    streams=_REQ, units=_SPELL, shape="scalar", min_n=30, cadence="nightly",
    scope=("category", "subcategory", "location_ref", "priority", "channel", "assignee_ref"),
    soft=("survival.km_resolution_curve",),
    name="Median resolution time",
    one_liner="The day by which half of requests are resolved, with the still-open ones counted.",
    assumes=(
        _CENSORING_ASSUMPTION,
        "The curve crosses the requested quantile inside the observed window.",
    ),
    wrong_when=(
        "The median is unreached and someone substitutes the mean of the closed subset. That "
        "substitution is the exact defect this product exists to name.",
        _CENSORING_FAILURE,
    ),
    interval=(
        "Brookmeyer-Crowley: the set of times whose confidence band contains 0.5. It can be "
        "asymmetric and it can be unbounded on the right."
    ),
    refs=("Brookmeyer and Crowley (1982) Biometrics 38:29",) + _KM_REFS,
    known="lung: median 310 days, 95% interval 285 to 363, the figure survfit prints.",
    min_n_expr="30 observed events, and the curve must reach the quantile",
    implemented=True,
)

_s(
    "survival.sla_attainment", RELIABILITY, survival.sla_attainment,
    streams=_REQ, units=_SPELL, shape="scalar", min_n=30, cadence="nightly",
    scope=("category", "location_ref", "priority"),
    name="SLA attainment",
    one_liner="The share of requests resolved within the promised number of days.",
    assumes=(
        _CENSORING_ASSUMPTION,
        "At least ten requests are still at risk at the horizon, or the estimate there is noise.",
        "The declared clock, wall or active, is the one the promise was made in (spine rule C8).",
    ),
    wrong_when=(
        "The horizon exceeds the last observation time, in which case the figure is "
        "extrapolation, which is fabrication.",
        "A curve with 200 events still has four requests at risk at day 30.",
    ),
    interval="A Greenwood 95% confidence interval on the probability resolved by the horizon.",
    refs=_KM_REFS,
    known="lung at t = 365: the published summary(survfit(...), times=365) value.",
    min_n_expr="30 observed events and at least 10 at risk at the horizon",
    implemented=True,
)

_s(
    "survival.first_response_curve", RELIABILITY, survival.first_response_curve,
    streams=_REQ, units=_SPELL, shape="series", min_n=30, cadence="nightly",
    scope=("category", "location_ref", "priority", "channel", "group_ref"),
    name="First-response curve",
    one_liner="How long a request waits before a human other than the author says anything.",
    assumes=(
        _CENSORING_ASSUMPTION,
        "A request nobody has answered yet is censored at the window boundary, not answered.",
    ),
    wrong_when=(
        "Acknowledgement is conflated with resolution. They are different promises and "
        "communities routinely report one as the other.",
        _CENSORING_FAILURE,
    ),
    interval="Greenwood pointwise 95% band on the probability still unanswered at that hour.",
    refs=_KM_REFS,
    known=(
        "The same lung fixture with relabelled fields, asserting numeric identity with "
        "survival.km_resolution_curve, which is a real regression risk if someone forks the "
        "estimator."
    ),
    min_n_expr="30 observed first responses",
    implemented=True,
)

_s(
    "survival.churn_curve", RELIABILITY, survival.churn_curve,
    streams=("member_lifecycle",), units=("MemberSpell",), shape="series", min_n=30,
    cadence="nightly", scope=("block", "cohort", "role", "membership_tier"),
    name="Membership churn curve",
    one_liner="How long members stay before they lapse or leave, counting those still here.",
    assumes=(
        "Ongoing membership is administrative censoring, not retention forever.",
        "Members who joined before the window are left-truncated and enter the risk set at "
        "window.start (spine rule C3).",
    ),
    wrong_when=(
        "Graduation, or any other structural exit, is treated as churn rather than as a "
        "competing risk. campus_club declares it as one for exactly this reason.",
        "The window is short relative to a membership year, so almost everyone is censored.",
    ),
    interval="Greenwood pointwise 95% band on the probability still a member at that day.",
    refs=_KM_REFS,
    known=(
        "The lung-based fixture, plus an analytic one: spells drawn from an Exponential(rate) "
        "with independent uniform censoring must produce a curve within Monte Carlo tolerance "
        "of exp(-rate * t), seeded. Exponential survival is a closed form, so this is an exact "
        "external truth rather than a reference-implementation comparison."
    ),
    min_n_expr="30 observed exits",
    implemented=True,
)

_s(
    "survival.logrank_compare", RELIABILITY, survival.logrank_compare,
    streams=_REQ, units=_SPELL, shape="structure", min_n=20, cadence="nightly",
    scope=("category", "location_ref", "assignee_ref", "channel"),
    name="Log-rank comparison",
    one_liner="Whether two or more groups of requests really do resolve at different speeds.",
    assumes=(
        "Independent censoring within every group.",
        "A common event-time scale across groups.",
        _CENSORING_ASSUMPTION,
    ),
    wrong_when=(
        "The survival curves cross. The log-rank test has most power against proportional "
        "alternatives, so a non-significant p is then not evidence of no difference.",
        "The groups were chosen after looking at the data, which is why Holm correction is "
        "applied across all pairwise tests and both raw and adjusted p are reported.",
    ),
    interval=(
        "None on the statistic. A p-value is not an interval and the UI must not draw one. Each "
        "group row carries its own Greenwood interval instead."
    ),
    refs=("Mantel (1966) Cancer Chemotherapy Reports 50:163", "Peto and Peto (1972) JRSS-A 135:185"),
    known=(
        "survival::survdiff(Surv(time, status) ~ sex, data = lung): chi-square 10.3 on 1 df, "
        "p = 0.001, universally reproduced in the R survival documentation."
    ),
    min_n_expr="10 observed events per group and at least 2 groups",
    implemented=True,
)

_s(
    "survival.cox_hazard_ratios", RELIABILITY, survival.cox_hazard_ratios,
    streams=_REQ, units=("RequestSpell",), shape="table", min_n=10, cadence="nightly",
    scope=("category", "location_ref"),
    name="Cox proportional-hazards ratios",
    one_liner="Which characteristics make a request resolve faster or slower, and by how much.",
    assumes=(
        "Hazards are proportional over time, which is measured by the Schoenfeld check rather "
        "than assumed.",
        "The log-hazard is linear in each continuous covariate.",
        "Censoring is independent; ties handled by the Efron correction.",
    ),
    wrong_when=(
        "The effect appears late or fades. Monsoon plumbing is the archetype and it fails "
        "proportionality by construction; a single hazard ratio is then not interpretable and "
        "the row is suppressed rather than printed.",
        "A covariate is measured after the request opened, which is immortal time bias and "
        "inflates its apparent protective effect.",
        "The covariate set was chosen by looking at p-values.",
    ),
    interval=(
        "A 95% profile-likelihood interval on the hazard ratio. It is multiplicative: an "
        "interval containing 1.0 means no detected effect. It is not a prediction interval for "
        "any single request."
    ),
    refs=(
        "Cox (1972) JRSS-B 34:187",
        "Grambsch and Therneau (1994) Biometrika 81:515 for the Schoenfeld test",
        "Peduzzi et al. (1995) for events per variable",
    ),
    known=(
        "The rossi recidivism dataset: published coefficients fin -0.379, age -0.057, "
        "race 0.314, wexp -0.150, mar -0.434, paro -0.085, prio 0.091, tolerance 1e-3 on the "
        "coefficient and 1e-2 on the standard error. The Schoenfeld check is tested on the same "
        "data, where age violates proportional hazards at the 5% level and fin does not: the "
        "test asserts FAIL for age and PASS for fin, which is ground truth about the check "
        "itself, not only about the model."
    ),
    min_n_expr="10 observed events per covariate",
    implemented=True,
)

_s(
    "survival.competing_risks_cif", RELIABILITY, survival.competing_risks_cif,
    streams=_REQ, units=_SPELL, shape="structure", min_n=30, cadence="nightly",
    scope=("category", "location_ref", "priority"),
    name="Aalen-Johansen cumulative incidence",
    one_liner="The chance a request has ended by each specific route by day t, resolved or not.",
    assumes=(
        "The declared causes are mutually exclusive and exhaustive.",
        "Censoring is independent of all causes.",
    ),
    wrong_when=(
        "Someone reads 1 minus Kaplan-Meier per cause as the cumulative incidence. That "
        "quantity is the probability of resolution in a hypothetical world where escalation "
        "cannot happen, it always exceeds the true incidence, and it is the mistake this "
        "estimator exists to fix.",
        "One of the competing causes has fewer than five events, so the competition is not "
        "estimable.",
    ),
    interval=(
        "A pointwise 95% interval, on the log-log scale, for the probability a request has "
        "exited by this specific cause by day t."
    ),
    refs=(
        "Aalen and Johansen (1978) Scandinavian Journal of Statistics 5:141",
        "Putter, Fiocco and Geskus (2007) Statistics in Medicine 26:2389",
    ),
    known=(
        "An exact analytic identity first: with a single cause the CIF must equal 1 minus the "
        "Kaplan-Meier estimate to floating-point tolerance, which is a theorem and therefore "
        "stronger than any dataset. Then the R survival multi-state vignette's mgus2 example, "
        "whose published cumulative incidence values are asserted."
    ),
    min_n_expr="30 events of the reported cause and 5 of each competing cause",
    implemented=True,
)

_s(
    "survival.naive_vs_km_gap", RELIABILITY, survival.naive_vs_km_gap,
    streams=_REQ, units=_SPELL, shape="structure", min_n=30, cadence="nightly",
    scope=("category", "location_ref"),
    soft=("survival.km_resolution_curve", "survival.median_resolution_days"),
    name="Naive average against the honest median",
    one_liner=(
        "What the average of closed requests says, what the censoring-aware estimate says, and "
        "how far apart they are."
    ),
    assumes=(
        _CENSORING_ASSUMPTION,
        "The naive figure is computed exactly as a competing dashboard would compute it, so "
        "that the comparison is fair to it.",
    ),
    wrong_when=(
        "The backlog is empty. With nothing censored the two figures agree, and the gap being "
        "zero is the honest answer rather than a broken panel.",
    ),
    interval=(
        "The Greenwood interval belongs to the censoring-aware figure. The naive mean is shown "
        "without one deliberately, because the naive procedure has no honest interval to offer."
    ),
    refs=_KM_REFS,
    known=(
        "The permanent censoring regression fixture from docs/RULES.md section 7: a constructed "
        "set where the mean of closed spells is 3.1 days and the Kaplan-Meier median is 8.0. "
        "The service must report both, must report the gap, and n_censored must be non-zero."
    ),
    min_n_expr="30 observed events",
    implemented=True,
)

_s(
    "spc.ewma_chart", RELIABILITY, spc.ewma_chart,
    streams=("request_flow",), units=("FlowPeriod", "LedgerPeriod", "ParticipationPeriod"),
    shape="structure", min_n=20, cadence="nightly", scope=("category", "location_ref"),
    name="EWMA control chart",
    one_liner="Whether a weekly count has shifted away from its usual level, or is just noisy.",
    assumes=(
        "Independent observations in the baseline period.",
        "A stable in-control mean and variance during that baseline.",
        "The limit constant was solved for a stated in-control average run length, not set to "
        "three sigma out of habit.",
    ),
    wrong_when=(
        "The series is autocorrelated, which weekly complaint counts usually are after a "
        "festival. The true run length is then far shorter than nominal.",
        "The baseline itself contained the shift you are looking for, which inflates the limits "
        "and blinds the chart.",
        "The process has a trend, which EWMA eventually tracks and then stops flagging.",
    ),
    interval=(
        "Not a confidence interval. Points outside the limits are a decision rule tuned so that "
        "a stable process false-alarms about once every target_arl0 periods."
    ),
    refs=(
        "Roberts (1959) Technometrics 1:239",
        "Lucas and Saccucci (1990) Technometrics 32:1",
        "Montgomery, Introduction to Statistical Quality Control, 7th ed., ch. 9",
    ),
    known=(
        "Lucas and Saccucci (1990) Table 3, the ARL0 = 500 row: L = 2.615 at lam=0.05, 2.814 "
        "at lam=0.10, 2.998 at lam=0.25, 3.071 at lam=0.50, and ARL1 = 10.3 for a one-sigma "
        "shift at lam=0.10. The L-solver reproduces all five, and the run length is confirmed "
        "independently by seeded simulation. The chart arithmetic is checked against the EWMA "
        "recursion written out by hand."
    ),
    min_n_expr="20 complete periods",
    implemented=True,
)

_s(
    "spc.cusum_chart", RELIABILITY, spc.cusum_chart,
    streams=("request_flow",), units=("FlowPeriod", "LedgerPeriod", "ParticipationPeriod"),
    shape="structure", min_n=20, cadence="nightly", scope=("category", "location_ref"),
    name="CUSUM control chart",
    one_liner="The faster detector of a persistent step change in a periodised count.",
    assumes=(
        "Independent observations in the baseline period.",
        "A stable in-control mean, since the reference value k is set from it.",
    ),
    wrong_when=(
        "The shift is a slow drift rather than a step, where EWMA is the more forgiving "
        "detector. The pack runs both and shows agreement or disagreement rather than picking "
        "one, because the disagreement is itself information.",
        "The baseline was not in control.",
    ),
    interval="Control limits, not an estimate. The decision boundary is h, in sigma units.",
    refs=(
        "Page (1954) Biometrika 41:100",
        "Hawkins (1993) Journal of Quality Technology 25:97",
        "Montgomery, Introduction to Statistical Quality Control, 7th ed., ch. 9",
    ),
    known=(
        "The standard k=0.5, h=5 table reproduced in Montgomery ch. 9: ARL0 = 465, ARL1 = 10.4 "
        "at one sigma, 5.75 at 1.5 sigma and 4.01 at two sigma, all four reproduced by the "
        "Markov-chain solver. Chart arithmetic against the C+ and C- recursion written out by "
        "hand."
    ),
    min_n_expr="20 complete periods",
    implemented=True,
)

_s(
    "spc.poisson_rate_chart", RELIABILITY, spc.poisson_rate_chart,
    streams=("request_flow",), units=("FlowPeriod",), shape="structure", min_n=20,
    cadence="nightly", scope=("category", "location_ref"),
    name="Poisson rate chart",
    one_liner="A control chart for counts with unequal period lengths, using exact quantiles.",
    assumes=(
        "Counts are Poisson with a rate proportional to exposure, unless the overdispersion "
        "check switches the limits to negative binomial and says so.",
        "Exposure per period is known and is carried on the period, not assumed equal.",
    ),
    wrong_when=(
        "The average count per period is below five, where the normal approximation used by "
        "textbook c-charts is bad enough to change conclusions. Exact Poisson quantiles are "
        "used instead, and the card says so.",
        "The counts are overdispersed, which a fixed monthly denominator makes common.",
    ),
    interval="Control limits from the exact Poisson or negative-binomial quantiles, not a normal band.",
    refs=(
        "Montgomery, Introduction to Statistical Quality Control, 7th ed., ch. 7",
        "Shewhart (1931)",
    ),
    known=(
        "The exact check: for a known Poisson mean the limits equal the exact ppf(alpha/2) and "
        "ppf(1-alpha/2) quantiles, verified against the explicit distribution sum rather than "
        "against another implementation. Montgomery's printed-circuit-board c-chart is cited in "
        "the catalog appendix as a published comparison whose raw table is not vendored here."
    ),
    min_n_expr="20 periods and an average count of at least 5 per period",
    implemented=True,
)

_s(
    "changepoint.detect_level_shifts", RELIABILITY, changepoint.detect_level_shifts,
    streams=("request_flow",), units=("FlowPeriod", "LedgerPeriod", "ParticipationPeriod"),
    shape="table", min_n=24, cadence="nightly", scope=("category", "location_ref"),
    name="Level-shift detection",
    one_liner="When a series stepped to a new level, and how confident we are about the date.",
    assumes=(
        "The series really is piecewise constant rather than smoothly trending.",
        "Residuals are independent within a segment.",
        "The penalty controlling the number of segments is declared, not tuned to taste.",
    ),
    wrong_when=(
        "A smooth trend is present, which will be chopped into a staircase of spurious "
        "changepoints.",
        "Strong seasonality was not removed first, which is why the service requires a "
        "deseasonalised input or a Poisson model with a seasonal offset and refuses otherwise.",
        "The penalty was tuned until the answer looked good.",
    ),
    interval=(
        "The interval is on the DATE: the level shifted somewhere between 8 and 19 August, most "
        "likely 12 August. It is not an interval on the size of the shift, which is reported "
        "separately."
    ),
    refs=(
        "Killick, Fearnhead and Eckley (2012) JASA 107:1590",
        "Zeileis et al. (2003) Computational Statistics and Data Analysis 44:109",
    ),
    known=(
        "The Nile annual river-flow series, the canonical benchmark: one level shift at 1898, "
        "the year the first Aswan works began, with a mean drop from about 1097 to about 850."
    ),
    min_n_expr="24 periods, and min_segment observations on each side of any reported point",
    implemented=True,
)

_s(
    "queueing.little_law_wait", RELIABILITY, queueing.little_law_wait,
    streams=_REQ, units=("FlowPeriod",), shape="scalar", min_n=8, cadence="hourly",
    scope=("category", "group_ref"),
    name="Little's Law expected wait",
    one_liner="The average time a request spends in the system, from the backlog and the arrival rate.",
    assumes=(
        "The system is in steady state over the window: arrivals and departures balance and the "
        "backlog has no trend. That is the whole assumption, and it is the one that fails.",
    ),
    wrong_when=(
        "The backlog is trending. There is then no steady-state wait to report, and saying the "
        "queue is diverging is far more useful than a number.",
        "The window spans a policy change.",
        "Arrivals and the backlog are measured on different populations, for example all "
        "requests as arrivals but one category in the backlog.",
    ),
    interval=(
        "A seeded bootstrap interval over the period-level variation, so it reflects how much "
        "the average wait moves week to week, not sampling error on individuals."
    ),
    refs=("Little (1961) Operations Research 9:383",),
    known=(
        "Exact algebra. L = lambda * W is an identity, so the test constructs a queue with known "
        "arrival rate and known waits, computes L by seeded simulation, and asserts the identity "
        "to floating-point tolerance. A theorem is a stronger ground truth than any table."
    ),
    min_n_expr="8 periods",
    implemented=True,
)

_s(
    "queueing.mmc_metrics", RELIABILITY, queueing.mmc_metrics,
    streams=("request_flow", "member_lifecycle"), units=("FlowPeriod", "RequestSpell"),
    shape="structure", min_n=30, cadence="hourly", scope=("category", "group_ref"),
    name="M/M/c queue metrics",
    one_liner="Utilisation, the chance of waiting, and the expected wait for a given team size.",
    assumes=(
        "Poisson arrivals, exponential service, c identical servers.",
        "No priority ordering, no abandonment, unlimited queue capacity.",
        "Utilisation below 1, or no finite wait exists.",
    ),
    wrong_when=(
        "Resolvers specialise by category, so they are not interchangeable, which is the normal "
        "case in a committee.",
        "Requests are worked in priority order.",
        "Residents give up and re-file, which is abandonment and makes the model optimistic.",
        "The service rate is estimated from closed spells only, which is optimistic and is "
        "always raised as a WARN with the censoring-aware mean offered instead.",
    ),
    interval=(
        "Propagated from the intervals on the estimated arrival and service rates by seeded "
        "bootstrap, so it is uncertainty about the parameters, not about a single request."
    ),
    refs=("Gross, Shortle, Thompson and Harris, Fundamentals of Queueing Theory, 5th ed., ch. 2 and 3",),
    known=(
        "Worked examples from Gross and Harris ch. 2 with published Lq, Wq and P(wait); plus two "
        "exact identities: M/M/1 is the c=1 case to floating-point tolerance, and L = lambda * W "
        "must hold for the model's own outputs."
    ),
    min_n_expr="30 closed spells for the service rate, and utilisation below 1",
    implemented=True,
)

_s(
    "queueing.erlang_c_staffing", RELIABILITY, queueing.erlang_c_staffing,
    streams=("request_flow", "member_lifecycle"),
    units=("FlowPeriod", "RequestSpell", "RosterSnapshot"), shape="structure", min_n=30,
    cadence="hourly", scope=("category", "group_ref"),
    name="Erlang-C staffing",
    one_liner=(
        "How many active volunteers it takes to close the promised share of requests inside the "
        "promised time."
    ),
    assumes=(
        "Erlang-C, so M/M/c with no abandonment and infinite patience. Real people abandon, "
        "which makes this conservative in one direction and optimistic in another.",
        "The availability convention is declared: rwa_society counts a committee member as an "
        "0.2 FTE server, and the number changes by a factor of five if that is ignored.",
    ),
    wrong_when=(
        "Volunteers are not interchangeable, so a plumbing request cannot be taken by the "
        "electrical volunteer and the pooled number understates the requirement.",
        "Demand is strongly seasonal, in which case staff to the peak period rather than the "
        "average.",
        "The service time was estimated from closed requests only.",
    ),
    interval=(
        "The sensitivity curve is the honest output: 4 servers gives 91%, 3 gives 74%. An "
        "integer server count with a confidence interval would be theatre."
    ),
    refs=(
        "Erlang (1917)",
        "Gans, Koole and Mandelbaum (2003) M&SOM 5:79",
        "Standard ACD staffing tables",
    ),
    known=(
        "Published Erlang-C staffing tables: the standard worked case of 20 Erlangs of offered "
        "load at an 80% within 20 seconds target requires 24 agents, and the solver must "
        "reproduce the published agent counts across a grid of loads and service levels. Plus "
        "the exact identity that Erlang-C P(wait) equals the M/M/c P(wait) from mmc_metrics for "
        "the same parameters."
    ),
    min_n_expr="30 closed spells for the service time and 8 periods for the arrival rate",
    implemented=True,
)

_s(
    "queueing.mg1_wait", RELIABILITY, queueing.mg1_wait,
    streams=_REQ, units=("RequestSpell", "FlowPeriod"), shape="scalar", min_n=30,
    cadence="hourly", scope=("category", "group_ref"),
    name="Pollaczek-Khinchine wait",
    one_liner="The expected wait when one person works the queue and service times vary a lot.",
    assumes=(
        "One server, Poisson arrivals, any service distribution with a finite variance, "
        "first-come first-served.",
    ),
    wrong_when=(
        "Service times are heavy-tailed enough that the variance is not stable, which happens "
        "when one request has been open for two years.",
        "More than one person actually works the queue, in which case this is the wrong model "
        "and the check blocks.",
    ),
    interval="Propagated parameter uncertainty by seeded bootstrap.",
    refs=("Pollaczek (1930)", "Khinchine (1932)", "Gross and Harris, ch. 5"),
    known=(
        "The P-K formula is closed form, so the test is exact against hand computation, plus the "
        "identity that at a coefficient of variation of 1 the M/G/1 wait equals M/M/1 to "
        "floating-point tolerance."
    ),
    min_n_expr="30 closed spells, because the service-time variance needs more data than the mean",
    implemented=True,
)

_s(
    "queueing.backlog_projection", RELIABILITY, queueing.backlog_projection,
    streams=_REQ, units=("FlowPeriod", "Forecast"), shape="series", min_n=8, cadence="weekly",
    scope=("category", "group_ref"), soft=("forecast.request_volume",),
    name="Backlog projection",
    one_liner="Where the open-request pile is heading at the current arrival rate and capacity.",
    assumes=(
        "The arrival forecast it is given passed its own MASE gate.",
        "Capacity stays as declared over the horizon.",
    ),
    wrong_when=(
        "The forecast it consumes lost to seasonal-naive, in which case the projection inherits "
        "that failure and says so rather than drawing a confident line.",
        "A staffing change is planned inside the horizon and was not entered.",
    ),
    interval=(
        "A predictive interval inherited from the arrival forecast and widened by the "
        "uncertainty in the service rate. It widens fast, which is honest."
    ),
    refs=("Little (1961) Operations Research 9:383", "Hyndman and Athanasopoulos, FPP3, ch. 5"),
    known=(
        "Composition, not a new estimator: the projection must reproduce the input forecast "
        "exactly when capacity is set to zero, and must reproduce Little's Law in steady state."
    ),
    min_n_expr="8 periods, plus whatever the arrival forecast requires",
    implemented=True,
)

_s(
    "fairness.workload_gini", RELIABILITY, fairness.workload_gini,
    streams=_REQ, units=_SPELL, shape="structure", min_n=50, cadence="nightly",
    scope=("category", "group_ref"),
    name="Workload concentration",
    one_liner="How unevenly the work is spread across the people doing it.",
    assumes=("The unit of work is comparable across people.",),
    wrong_when=(
        "One resolver takes only the hard cases, so equal counts are not equal work.",
        "Part-time availability is not accounted for, so the person available one evening a week "
        "looks like a shirker.",
        "Resolvers with zero assignments were included or excluded without the choice being "
        "declared. It moves the coefficient enormously and it is in params_hash for that reason.",
    ),
    interval=(
        "A bias-corrected bootstrap interval over resolvers. Gini is biased downward in small "
        "samples and the correction matters at ten people."
    ),
    refs=("Gini (1912)", "Efron and Tibshirani (1993), An Introduction to the Bootstrap"),
    known=(
        "Three exact closed forms, no reference implementation needed: Gini of a perfectly equal "
        "vector is 0; of (0, ..., 0, 1) it is (n-1)/n; of the discrete uniform 1..n it is "
        "(n-1)/(3n). Lorenz curve against a published income distribution example."
    ),
    min_n_expr="10 resolvers and 50 assigned requests",
    implemented=True,
)

_s(
    "fairness.balanced_assignment", RELIABILITY, fairness.balanced_assignment,
    streams=("request_flow", "member_lifecycle"), units=("RequestSpell", "RosterSnapshot"),
    shape="table", min_n=1, cadence="on_demand", scope=("category", "group_ref"),
    name="Balanced assignment suggestion",
    one_liner="A suggested allocation of the open requests that evens out load and respects skill.",
    assumes=(
        "The cost matrix reflects real preferences and real capacity. It is a recommendation, "
        "and a committee overriding it is not an error.",
    ),
    wrong_when=(
        "The cost function encodes only load and ignores expertise, which will hand the sewage "
        "treatment problem to whoever is least busy.",
        "Declared capacity is below the number of open requests, in which case no complete "
        "assignment exists and the partial one plus the shortfall is returned.",
    ),
    interval=(
        "None, and the absence is the point: this is an optimisation result, not an estimate, "
        "and giving it an interval would be a category error. The min_n of 1 has the same "
        "explanation, since there is no inference here."
    ),
    refs=("Kuhn (1955) Naval Research Logistics Quarterly 2:83", "Munkres (1957) JSIAM 5:32"),
    known=(
        "Exhaustive enumeration as the oracle on seeded random matrices, which is exact rather "
        "than a second implementation, a 3x3 instance where the greedy choice costs 34 and the "
        "optimum 33, and the invariant that adding a constant to any row leaves the optimal "
        "assignment unchanged."
    ),
    min_n_expr="1 open request and 2 resolvers; there is no statistical floor because there is no inference",
    implemented=True,
)


# ===========================================================================
# Pack 2: Bayesian Ranking and Experimentation
# ===========================================================================

_s(
    "bayes.fit_beta_prior", BAYES_RANKING, bayes.fit_beta_prior,
    streams=("request_flow",), units=("RateObservation",), shape="structure", min_n=5,
    cadence="nightly", scope=("category", "trade"),
    name="Empirical Beta prior",
    one_liner="What a typical success rate looks like across groups, learned from the groups themselves.",
    assumes=(
        "Group rates are exchangeable draws from a common Beta distribution.",
        "Trials within a group are Bernoulli with that group's rate.",
    ),
    wrong_when=(
        "The groups genuinely differ in kind. Vendors from different trades are not "
        "exchangeable: pool within trade, not across.",
        "One group supplies most of the trials and therefore most of the prior.",
        "The rate is not stable over the window, so a vendor who improved is shrunk toward "
        "their own past.",
    ),
    interval=(
        "A profile-likelihood interval on the prior mean. It is uncertainty about the "
        "POPULATION of groups, not about any one group."
    ),
    refs=(
        "Robbins (1956) on empirical Bayes",
        "Efron and Morris (1975) JASA 70:311",
        "Robinson, Introduction to Empirical Bayes (2017), ch. 3",
    ),
    known=(
        "Robinson's baseball batting-average example fits Beta(alpha about 78.7, beta about "
        "224.9), a published pair reproduced across the empirical Bayes literature; our fit must "
        "match within 1%. Plus recovery: data simulated from a known Beta at a fixed seed must "
        "return alpha and beta within a tolerance derived from the Fisher information."
    ),
    min_n_expr="5 groups and at least 50 total trials",
)

_s(
    "bayes.beta_binomial_shrink", BAYES_RANKING, bayes.beta_binomial_shrink,
    streams=("request_flow",), units=("RateObservation",), shape="table", min_n=5,
    cadence="nightly", scope=("category", "trade"), soft=("bayes.fit_beta_prior",),
    name="Beta-Binomial shrinkage",
    one_liner="Each group's success rate pulled toward the typical rate in proportion to how little we know.",
    assumes=(
        "The Beta prior fits the population of groups.",
        "Trials are exchangeable within a group.",
    ),
    wrong_when=(
        "The group is genuinely exceptional, in which case shrinkage understates it and only "
        "more data fixes that.",
        "The outcome is not binary, for example partial resolutions counted as successes.",
    ),
    interval=(
        "A 95% CREDIBLE interval: a Bayesian statement about this group's rate given the model, "
        "not a confidence interval. The two are read differently and interval_kind says which "
        "this is."
    ),
    refs=("Gelman et al., Bayesian Data Analysis, 3rd ed., ch. 5", "Efron and Morris (1975) JASA 70:311"),
    known=(
        "Exact and closed form: the posterior of Beta(a,b) with x successes in n trials is "
        "Beta(a+x, b+n-x), asserted against scipy.stats.beta to 1e-12. Then Efron and Morris's "
        "eighteen baseball players, where the empirical Bayes estimates reduce total squared "
        "error by a published factor of about 3.5. Then the pathology test, which is a hard "
        "shipping requirement: a fixture with a 3-of-3 group and a 47-of-52 group must rank "
        "47-of-52 first by posterior lower bound."
    ),
    min_n_expr="1 trial per group for a row, 5 groups for the prior",
)

_s(
    "bayes.gamma_poisson_shrink", BAYES_RANKING, bayes.gamma_poisson_shrink,
    streams=("request_flow",), units=("CountObservation",), shape="table", min_n=5,
    cadence="nightly", scope=("category", "assignee_ref"),
    name="Gamma-Poisson shrinkage",
    one_liner="The same shrinkage for rates per unit of exposure rather than per trial.",
    assumes=(
        "Group event counts are Poisson with a rate drawn from a common Gamma.",
        "Exposure is measured, not assumed equal.",
    ),
    wrong_when=(
        "Exposure is wrong or missing, which silently compares a resolver active for two weeks "
        "against one active for a year.",
        "Counts are overdispersed beyond what the Gamma mixture absorbs.",
    ),
    interval="A 95% credible interval on the group's rate per unit exposure.",
    refs=("Gelman et al., Bayesian Data Analysis, 3rd ed., ch. 5", "Robbins (1956)"),
    known=(
        "Exact conjugate identity: the posterior is Gamma(alpha + sum(y), beta + sum(exposure)), "
        "asserted against scipy.stats.gamma to 1e-12, plus recovery of a known Gamma from seeded "
        "simulation."
    ),
    min_n_expr="5 groups",
)

_s(
    "bayes.rank_by_posterior_lower_bound", BAYES_RANKING, bayes.rank_by_posterior_lower_bound,
    streams=("request_flow",), units=("Posterior",), shape="table", min_n=5, cadence="nightly",
    scope=("category", "trade"), soft=("bayes.beta_binomial_shrink", "bayes.gamma_poisson_shrink"),
    name="Ranking by posterior lower bound",
    one_liner="A leaderboard where not knowing enough about someone costs them a place.",
    assumes=(
        "The posteriors handed in were fitted on comparable groups.",
        "The reader wants a ranking that is robust to small samples rather than the highest "
        "point estimate.",
    ),
    wrong_when=(
        "Someone ranks by the posterior mean instead, which still favours small samples whenever "
        "the prior is weak.",
        "Adjacent ranks have heavily overlapping intervals and are read as an order. A rank-1 "
        "with 34% stability and a rank-2 with 31% are not meaningfully ordered, which is why "
        "rank_stability is returned and the UI renders a tie band.",
    ),
    interval="Per-row credible intervals, plus the seeded probability that each group holds its rank.",
    refs=("Efron and Morris (1975) JASA 70:311", "Gelman et al., Bayesian Data Analysis, 3rd ed."),
    known=(
        "Deterministic given the posteriors, asserted exactly. The behavioural tests are the "
        "point and are required for shipping: 3-of-3 must not outrank 47-of-52, and in the "
        "inverse fixture a 0-of-1 group must not outrank a measured 2-of-10. Rank stability is "
        "asserted by seeded Monte Carlo against the analytic two-group integral."
    ),
    min_n_expr="inherits the prior's 5 groups",
)

_s(
    "bayes.hierarchical_pool", BAYES_RANKING, bayes.hierarchical_pool,
    streams=("request_flow",), units=("RateObservation",), shape="structure", min_n=5,
    cadence="weekly_platform", scope=("vertical", "group_key"),
    name="Hierarchical pooling across tenants",
    one_liner="The prior a new community starts with, learned from every community already here.",
    assumes=(
        "Tenants are exchangeable within a vertical. They are not exchangeable across verticals, "
        "and the service refuses to pool a housing society with a sports club.",
        "Each tenant's contribution per batch is bounded to one differentially private "
        "sufficient statistic per group_key, enforced by construction rather than trusted.",
        "The pool refreshes on a fixed cadence, never live, so no single tenant's update is "
        "isolable by differencing across releases.",
    ),
    wrong_when=(
        "One large tenant dominates before noise is applied, which the 25% concentration check "
        "blocks.",
        "The vertical is heterogeneous, so the pooled prior describes nobody.",
        "A tenant's per-quarter privacy budget is exhausted, which excludes its contribution "
        "rather than silently weakening the guarantee.",
    ),
    interval=(
        "Credible intervals from the posterior over the NOISED sufficient statistics. The "
        "pooling factor says how much of each unit's estimate came from its own data rather "
        "than from the pool."
    ),
    refs=(
        "Gelman and Hill (2006), ch. 12",
        "Rubin (1981) Journal of Educational Statistics 6:377",
        "Dwork and Roth (2014), The Algorithmic Foundations of Differential Privacy",
    ),
    known=(
        "The eight schools dataset: published posterior estimates for the group effects and for "
        "tau in Rubin (1981) and BDA ch. 5, matched within Monte Carlo error at a fixed seed. "
        "Plus a privacy gate: perturbing one held-out tenant's contribution by a bounded amount "
        "must change the published pooled statistic by no more than the declared epsilon allows."
    ),
    min_n_expr="5 units per level; for cross-tenant pooling, 10 tenants with none above 25% of observations",
)

_s(
    "experiments.beta_ab_test", BAYES_RANKING, experiments.beta_ab_test,
    streams=("participation",), units=("ParticipationEvent",), shape="structure", min_n=100,
    cadence="hourly", scope=("campaign_ref", "channel"),
    name="Bayesian A/B test",
    one_liner="The probability one nudge really is better than the other, and by how much.",
    assumes=(
        "Random assignment, verified against the exposure log rather than asserted.",
        "Independent members, a stable conversion definition, one metric declared in advance.",
    ),
    wrong_when=(
        "The arms were assigned by channel or by time of day, so channel is confounded.",
        "Members received both arms.",
        "The metric was chosen after seeing the data.",
    ),
    interval=(
        "Credible intervals from the Beta posteriors. P(B beats A) is a posterior probability, "
        "not a p-value, and it must not be read as one."
    ),
    refs=(
        "Miller, Formulas for Bayesian A/B testing",
        "Kohavi, Tang and Xu (2020), Trustworthy Online Controlled Experiments",
    ),
    known=(
        "P(B>A) for two Beta posteriors has an exact closed form (Miller's finite sum over the "
        "integer parameters), asserted to 1e-10 against high-resolution numerical integration of "
        "the same quantity. Two independent computations of one integral, so an error in either "
        "is caught."
    ),
    min_n_expr="100 exposures per arm and 10 conversions per arm",
)

_s(
    "experiments.expected_loss", BAYES_RANKING, experiments.expected_loss,
    streams=("participation",), units=("ParticipationEvent",), shape="structure", min_n=100,
    cadence="hourly", scope=("campaign_ref", "channel"), soft=("experiments.beta_ab_test",),
    name="Expected loss",
    one_liner="How much you would lose, in the metric's own units, by picking each arm now.",
    assumes=(
        "The posteriors are the ones from the declared test.",
        "The committee's threshold of caring is set in the metric's units, not as a significance "
        "level.",
    ),
    wrong_when=(
        "The threshold is set after seeing the loss.",
        "The metric is not the one the decision actually turns on.",
    ),
    interval="Credible, from the same posteriors. The loss is an expectation over them.",
    refs=("Stucchio (2015) on expected loss", "Berger (1985), Statistical Decision Theory"),
    known=(
        "The expected-loss integral for Beta posteriors has a closed form, asserted against "
        "numerical integration to 1e-10, plus the identity that the loss is exactly zero when "
        "the posteriors are identical."
    ),
    min_n_expr="inherits the A/B test's floor",
)

_s(
    "experiments.sequential_stopping_rule", BAYES_RANKING, experiments.sequential_stopping_rule,
    streams=("participation",), units=("ParticipationEvent",), shape="structure", min_n=0,
    cadence="hourly", scope=("campaign_ref",),
    name="Always-valid stopping rule",
    one_liner="Whether the experiment can be stopped now, safely, having been watched every day.",
    assumes=(
        "The e-value or mixture SPRT construction, which stays valid under continuous monitoring.",
        "Observations arrive in time order.",
    ),
    wrong_when=(
        "The metric definition changed mid-flight.",
        "The arms changed mid-flight, which resets the process.",
        "A fixed-horizon test is being monitored sequentially, which the blocking check catches.",
    ),
    interval=(
        "The confidence sequence covers the true effect at ALL times simultaneously with "
        "probability 1 - alpha, which is a stronger and different guarantee from a fixed-sample "
        "interval. It is correspondingly wider, and that width is the price of being allowed to "
        "look."
    ),
    refs=(
        "Ville (1939)",
        "Howard, Ramdas, McAuliffe and Sekhon (2021) Annals of Statistics 49:1055",
        "Johari, Koomen, Pekelis and Walsh (2022) Management Science",
    ),
    known=(
        "A theorem: under the null, P(sup_t E_t >= 1/alpha) <= alpha by Ville's inequality. Many "
        "seeded null experiments monitored continuously must keep the empirical false-positive "
        "rate at or below alpha. The negative control is required: a fixed-horizon z-test "
        "monitored the same way must exceed alpha substantially on the identical fixture."
    ),
    min_n_expr="none by construction; that is the point of an always-valid method",
)

_s(
    "bandits.thompson_sampling_policy", BAYES_RANKING, bandits.thompson_sampling_policy,
    streams=("participation",), units=("ParticipationEvent", "Posterior"), shape="structure",
    min_n=0, cadence="on_dispatch", scope=("campaign_ref", "channel"),
    name="Thompson sampling allocation",
    one_liner="How to split the next batch of nudges between arms while still learning.",
    assumes=(
        "Stationary arm rewards.",
        "Independent exposures.",
        "The reward is observed promptly relative to the decision cadence.",
        "A traffic floor keeps every arm at 5%, so an arm that got unlucky early can recover.",
    ),
    wrong_when=(
        "The reward is seasonal: a channel that works during festivals will dominate permanently "
        "after one festival.",
        "Rewards arrive with a long delay, so the bandit acts on incomplete feedback.",
        "The arm set changed, which invalidates the accumulated posteriors.",
    ),
    interval=(
        "Per-arm credible intervals. The allocation itself is a decision, not an estimate, and "
        "carries no interval."
    ),
    refs=(
        "Thompson (1933) Biometrika 25:285",
        "Russo, Van Roy, Kazerouni, Osband and Wen (2018), A Tutorial on Thompson Sampling",
        "Lai and Robbins (1985) Advances in Applied Mathematics 6:4",
    ),
    known=(
        "Honest and partial: there is no published table of Thompson-sampling outputs to assert "
        "against. Asserted instead: exact seed reproducibility, which is the property a committee "
        "actually depends on; cumulative regret growing as O(log T) and staying within a constant "
        "multiple of the Lai-Robbins lower bound, which is a theorem; and beating uniform "
        "allocation on a seeded fixture without starving an arm below the floor."
    ),
    min_n_expr="none to run; 30 exposures per arm before the pack acts on the allocation",
)

_s(
    "bandits.freeze_and_report", BAYES_RANKING, bandits.freeze_and_report,
    streams=("participation",), units=("Posterior",), shape="structure", min_n=0,
    cadence="on_demand", scope=("campaign_ref",), soft=("bandits.thompson_sampling_policy",),
    name="Frozen policy record",
    one_liner="Why the system chose to send Tuesday evening reminders, reproducible months later.",
    assumes=(
        "The stored state and seed are the ones that produced the allocation.",
        "Nothing recomputes: this is a record, not an estimate.",
    ),
    wrong_when=(
        "The arm set or the reward definition changed after the freeze, which makes the record "
        "accurate and the comparison meaningless.",
    ),
    interval="The per-arm credible intervals as they stood at the freeze, not as they stand now.",
    refs=("Russo et al. (2018), A Tutorial on Thompson Sampling",),
    known=(
        "Exact: replaying the frozen state with the stored seed reproduces the identical "
        "allocation, asserted bit for bit. This is also the test that would fail first if "
        "someone added module-level state to app/stats/, so it doubles as a purity regression."
    ),
)

_s(
    "pairwise.bradley_terry", BAYES_RANKING, pairwise.bradley_terry,
    streams=("request_flow",), units=("PairwiseResult",), shape="table", min_n=30,
    cadence="nightly", scope=("category", "sport", "ladder"),
    name="Bradley-Terry abilities",
    one_liner="A single strength score per item, fitted from who beat whom.",
    assumes=(
        "A single latent ability per item.",
        "Comparison outcomes independent given the abilities.",
        "Abilities stable over the window.",
        "Every item lies in one connected component of the comparison graph.",
    ),
    wrong_when=(
        "Preferences are cyclic, in which case a one-dimensional ability model is the wrong "
        "description, exactly as a Condorcet cycle means a linear preference order is.",
        "Abilities changed during the window; pairwise.elo_update tracks change by construction.",
        "The comparison graph is disconnected, where every implementation that does not check "
        "silently returns a ranking anyway.",
    ),
    interval=(
        "Profile-likelihood intervals on abilities RELATIVE to the reference item. Only "
        "differences are identified, so the origin of the scale is arbitrary."
    ),
    refs=(
        "Bradley and Terry (1952) Biometrika 39:324",
        "Hunter (2004) Annals of Statistics 32:384",
        "Turner and Firth (2012) JSS 48:9",
    ),
    known=(
        "The BradleyTerry2 package's published worked examples with printed abilities and "
        "standard errors. Exact second ground truth: in a balanced round-robin the fitted "
        "abilities must be a monotone function of win counts, and for a perfectly transitive "
        "result set the ordering must match exactly. Third: the separation fixture must trigger "
        "the blocking check rather than return a large finite number."
    ),
    min_n_expr="5 items, 30 comparisons, and a connected comparison graph",
)

_s(
    "pairwise.elo_update", BAYES_RANKING, pairwise.elo_update,
    streams=("request_flow",), units=("PairwiseResult",), shape="structure", min_n=1,
    cadence="nightly", scope=("sport", "ladder"),
    name="Elo rating trajectory",
    one_liner="Ratings that move after each result, for items whose strength genuinely changes.",
    assumes=(
        "Comparisons arrive in time order.",
        "The K-factor is declared in advance, since it sets how fast a rating forgets.",
    ),
    wrong_when=(
        "A rating from very few comparisons is read as a measurement. One result updates a "
        "rating; ten do not make it reliable.",
        "The K-factor was tuned until a favoured item came out on top.",
    ),
    interval=(
        "None on the trajectory itself. Elo is a filter, not an estimator with sampling error, "
        "and the Bradley-Terry service is where an interval belongs."
    ),
    refs=("Elo (1978), The Rating of Chessplayers", "Glickman (1999) Applied Statistics 48:377"),
    known=(
        "Exact arithmetic: each update is a closed-form expression asserted by hand; total "
        "rating is conserved across an update; and the fixed point of repeated updates against a "
        "constant opponent equals the Bradley-Terry ability difference implied by the observed "
        "win rate, which links the two services and is a real analytic identity."
    ),
)


# ===========================================================================
# Pack 3: Forecasting and Calibrated Risk
# ===========================================================================

_FORECAST_UNITS = ("FlowPeriod", "LedgerPeriod", "ParticipationPeriod")

_s(
    "forecast.seasonal_naive", FORECAST_RISK, forecast.seasonal_naive,
    streams=("ledger",), units=_FORECAST_UNITS, shape="series", min_n=24, cadence="weekly",
    scope=("category", "location_ref"),
    name="Seasonal naive forecast",
    one_liner="Next month will look like the same month last year. The number everything else must beat.",
    assumes=("A stable seasonal period of the declared length.",),
    wrong_when=(
        "The series has a trend, which this ignores entirely. That is the point: it is a "
        "baseline, and a sophisticated model that cannot beat it is decoration.",
        "The last seasonal cycle contained a one-off event.",
    ),
    interval="An 80% prediction interval from the residual quantiles of the same rule.",
    refs=("Hyndman and Athanasopoulos, Forecasting: Principles and Practice, 3rd ed., ch. 5",),
    known=(
        "Exact: yhat[t] = y[t - m]. The MASE of seasonal-naive against itself must equal exactly "
        "1.0, which is the anchor for the entire gate."
    ),
    min_n_expr="2 * season_length periods",
    implemented=True,
)

_s(
    "forecast.stl_decompose", FORECAST_RISK, forecast.stl_decompose,
    streams=("ledger",), units=_FORECAST_UNITS, shape="structure", min_n=24, cadence="weekly",
    scope=("category", "location_ref"),
    name="STL decomposition",
    one_liner="Splitting a series into its trend, its seasonal rhythm and what is left over.",
    assumes=(
        "A single fixed-length seasonal period.",
        "Slowly varying seasonality.",
        "Additivity, unless a log transform was applied and disclosed.",
    ),
    wrong_when=(
        "The community has two overlapping seasonalities, a weekly rhythm and a festival "
        "calendar, which STL with one period cannot separate.",
        "The series has a level shift, which STL smears across the trend rather than isolating; "
        "run changepoint.detect_level_shifts first, and the pack does.",
    ),
    interval=(
        "None on the components. A decomposition is a partition, not an estimate, and the "
        "remainder is what is left rather than an error term with a distribution."
    ),
    refs=("Cleveland, Cleveland, McRae and Terpenning (1990) Journal of Official Statistics 6:3",),
    known=(
        "Partial, and stated as such: there is no published table of STL component values. The "
        "ground truth is three-part, and none of the three is a published external number: the "
        "exact reconstruction identity, recovery of known components from a synthetic build, and "
        "agreement with the statsmodels reference implementation on the co2 series."
    ),
    min_n_expr="2 * season_length periods and at least 24 observations",
    implemented=True,
)

_s(
    "forecast.holt_winters", FORECAST_RISK, forecast.holt_winters,
    streams=("ledger",), units=_FORECAST_UNITS, shape="series", min_n=24, cadence="weekly",
    scope=("category", "location_ref"),
    soft=("forecast.seasonal_naive", "forecast.rolling_origin_backtest"),
    name="Holt-Winters exponential smoothing",
    one_liner="A forecast with level, trend and season, served only if it beats the naive baseline.",
    assumes=(
        "The exponential smoothing state space form.",
        "Additive errors unless the multiplicative form was selected.",
        "A stable seasonal period.",
        "It beat seasonal-naive on MASE under rolling-origin cross-validation on this tenant's "
        "own history. That is a blocking check, not a note.",
    ),
    wrong_when=(
        "The level shifted; fit on the segment after the changepoint instead.",
        "A one-off event dominates, since a single festival collection is smoothed into the "
        "trend and inflates the next four periods.",
        "The series is a count with many zeros, where a Poisson model is the right tool.",
    ),
    interval=(
        "An 80% prediction interval for a FUTURE OBSERVATION, not for the mean. It is wider than "
        "a confidence interval on purpose and it widens with the horizon."
    ),
    refs=(
        "Holt (1957)",
        "Winters (1960) Management Science 6:324",
        "Hyndman and Athanasopoulos, FPP3, ch. 8",
    ),
    known=(
        "FPP3 section 8.3's worked Holt-Winters example on Australian domestic tourism, whose "
        "fitted smoothing parameters and point forecasts are published. Second: on the M3 monthly "
        "series, published benchmark MASE values for ETS give a range our implementation must "
        "land inside."
    ),
    min_n_expr="2 * season_length periods, minimum 24",
    implemented=True,
)

_s(
    "forecast.sarima", FORECAST_RISK, forecast.sarima,
    streams=("ledger",), units=_FORECAST_UNITS, shape="series", min_n=36, cadence="weekly",
    scope=("category", "location_ref"),
    soft=("forecast.seasonal_naive", "forecast.rolling_origin_backtest"),
    name="Seasonal ARIMA",
    one_liner="A forecast fitted to the series' own autocorrelation, served only if it beats naive.",
    assumes=(
        "Linear and stationary after differencing.",
        "Gaussian innovations, for the interval only.",
        "It passed the MASE gate on this tenant's history.",
    ),
    wrong_when=(
        "Automatic order selection was run on a short series, where AICc will happily pick a "
        "six-parameter model for forty observations.",
        "The series has structural breaks.",
        "The intervals are read as complete: they ignore parameter uncertainty and are known to "
        "be slightly too narrow, which the caveat states.",
    ),
    interval=(
        "As Holt-Winters, a prediction interval for a future observation, and additionally known "
        "to be slightly too narrow because parameter uncertainty is excluded."
    ),
    refs=(
        "Box, Jenkins, Reinsel and Ljung, Time Series Analysis, 5th ed.",
        "Hyndman and Khandakar (2008) JSS 27:3",
    ),
    known=(
        "The Box-Jenkins airline model on AirPassengers: ARIMA(0,1,1)(0,1,1)[12] on the log "
        "scale, published estimates theta = -0.40 and Theta = -0.56, tolerance 0.02 on each. The "
        "single most reproduced fit in the time-series literature."
    ),
    min_n_expr="3 * season_length periods and at least 36; stricter than the contract default because SARIMA has more parameters",
    implemented=True,
)

_s(
    "forecast.rolling_origin_backtest", FORECAST_RISK, forecast.rolling_origin_backtest,
    streams=("ledger",), units=_FORECAST_UNITS, shape="structure", min_n=24, cadence="weekly",
    scope=("category", "location_ref"), soft=("forecast.seasonal_naive",),
    name="Rolling-origin backtest",
    one_liner="Whether a forecaster actually beat the naive baseline on this community's own history.",
    assumes=(
        "Time order is respected: no fold's training set contains an observation after its "
        "origin, which is asserted rather than trusted.",
        "The baseline is seasonal-naive at the same season length.",
        "Hyperparameter selection happens INSIDE each fold, not outside.",
    ),
    wrong_when=(
        "MASE is compared across series with different scales and averaged carelessly.",
        "The model was tuned on the same folds it is being evaluated on.",
        "Fewer than five folds are available, where the comparison is a coin flip.",
    ),
    interval=(
        "A bootstrap interval on MASE over folds, showing how stable the advantage over naive "
        "is. A MASE of 0.95 with an interval of 0.6 to 1.4 has not beaten naive."
    ),
    refs=(
        "Hyndman and Koehler (2006) International Journal of Forecasting 22:679",
        "Tashman (2000) International Journal of Forecasting 16:437",
    ),
    known=(
        "Two exact anchors: the MASE of seasonal-naive against itself is exactly 1.0 by "
        "construction, which pins the scaling denominator; and MASE on a hand-computed five-point "
        "example matches the arithmetic in Hyndman and Koehler. Interval coverage is checked by "
        "seeded simulation from a known process, where nominal 80% must be attained within "
        "binomial tolerance."
    ),
    min_n_expr="initial_train + min_folds * step periods, so at least 5 folds",
    implemented=True,
)

_s(
    "forecast.dues_collection", FORECAST_RISK, forecast.dues_collection,
    streams=("ledger",), units=("LedgerPeriod",), shape="series", min_n=24, cadence="weekly",
    scope=("category",), soft=("forecast.holt_winters", "forecast.rolling_origin_backtest"),
    name="Dues collection forecast",
    one_liner="How much is likely to come in over the next few billing cycles.",
    assumes=(
        "A hard monthly billing cycle, so the season length is the billing period.",
        "Expected entries are receivables, not actuals, and are disclosed separately (rule L2).",
        "It passed the MASE gate.",
    ),
    wrong_when=(
        "The billing amount or cycle changed inside the fitting window.",
        "A festival contribution drive is treated as ordinary seasonality.",
        "The last period is incomplete because the treasurer has not finished reconciling, which "
        "is why the series is truncated at complete_through.",
    ),
    interval="An 80% and a 95% prediction interval for the collected amount in each future period.",
    refs=("Hyndman and Athanasopoulos, FPP3, ch. 8",),
    known="Inherits its parent forecaster's ground truth; the addition is the billing-cycle fixture.",
    min_n_expr="2 * season_length periods",
    implemented=True,
)

_s(
    "forecast.request_volume", FORECAST_RISK, forecast.request_volume,
    streams=("request_flow",), units=("FlowPeriod",), shape="series", min_n=24, cadence="weekly",
    scope=("category", "location_ref"),
    soft=("forecast.holt_winters", "forecast.rolling_origin_backtest"),
    name="Request volume forecast",
    one_liner="How many requests to expect next month, so staffing can be planned rather than reacted to.",
    assumes=(
        "A count series with the vertical's declared seasonal structure, monsoon included.",
        "It passed the MASE gate.",
    ),
    wrong_when=(
        "A category was introduced or retired inside the window.",
        "The count is small enough that a Gaussian interval crosses zero, where a Poisson model "
        "is the right tool.",
    ),
    interval="A prediction interval for the count in each future period, floored at zero.",
    refs=("Hyndman and Athanasopoulos, FPP3, ch. 8",),
    known="Inherits its parent forecaster's ground truth; the addition is the monsoon-season fixture.",
    min_n_expr="2 * season_length periods",
    implemented=True,
)

_s(
    "forecast.attendance", FORECAST_RISK, forecast.attendance,
    streams=("participation", "member_lifecycle"),
    units=("ParticipationPeriod", "RosterSnapshot"), shape="series", min_n=24, cadence="weekly",
    scope=("group_ref", "event_kind"),
    soft=("forecast.holt_winters", "forecast.rolling_origin_backtest"),
    name="Attendance forecast",
    one_liner="How many people are likely to turn up, and never more than exist.",
    assumes=(
        "Attendance is bounded above by the roster, which is a blocking check rather than a "
        "hope: a 340-member society cannot have 400 attendees.",
        "It passed the MASE gate.",
    ),
    wrong_when=(
        "The roster grew or shrank sharply, so the bound moved.",
        "One exceptional event, an annual general meeting or a festival, dominates the history.",
    ),
    interval=(
        "A prediction interval on the headcount, truncated at the roster size. Communities "
        "consistently over-forecast turnout, so the bound is enforced rather than suggested."
    ),
    refs=("Hyndman and Athanasopoulos, FPP3, ch. 8",),
    known=(
        "Inherits its parent forecaster's ground truth. The additional assertion is the bound "
        "check, tested against a fixture that would otherwise forecast past the roster size."
    ),
    min_n_expr="2 * season_length periods",
    implemented=True,
)

_s(
    "montecarlo.runway_shortfall", FORECAST_RISK, montecarlo.runway_shortfall,
    streams=("ledger",), units=("LedgerPeriod", "Forecast"), shape="structure", min_n=12,
    cadence="weekly", scope=("fund", "category"),
    soft=("forecast.dues_collection", "forecast.rolling_origin_backtest"),
    name="Runway shortfall simulation",
    one_liner="The chance the fund runs below its floor within the horizon, and roughly when.",
    assumes=(
        "The forecast predictive distributions are correct, and both passed the MASE gate.",
        "Inflow and outflow shocks are drawn JOINTLY with the estimated correlation. If "
        "collections fall in the same month maintenance spend rises, independent sampling "
        "understates the shortfall badly.",
        "Committed outflows are treated as certain and disclosed separately from forecast ones.",
    ),
    wrong_when=(
        "A single lumpy expense, a sewage plant overhaul, is in the horizon and was not entered "
        "as an expected outflow.",
        "The correlation was estimated from twelve noisy points.",
        "A committee levies an emergency assessment mid-horizon, which is exactly what a "
        "committee would do.",
    ),
    interval=(
        "p_shortfall is a probability under the model; the interval on the first shortfall period "
        "is a predictive interval over simulated paths and widens fast."
    ),
    refs=(
        "Kroese, Taimre and Botev, Handbook of Monte Carlo Methods",
        "Standard first-passage formulation",
    ),
    known=(
        "Strong and analytic: for a Gaussian random walk with known drift and volatility the "
        "probability of hitting a floor within a horizon has a closed-form first-passage solution "
        "(the inverse Gaussian). The simulator is driven with that process at a fixed seed and "
        "must match the closed form within Monte Carlo error at 20,000 draws."
    ),
    min_n_expr="12 LedgerPeriod observations for the inflow-outflow correlation, plus the forecasts' own floors",
)

_s(
    "risk.late_payment_risk", FORECAST_RISK, risk.late_payment_risk,
    streams=("ledger", "participation", "member_lifecycle"),
    units=("DueSpell", "EngagementFeatures", "MemberSpell"), shape="table", min_n=300,
    cadence="monthly", scope=("block", "unit_type"),
    soft=("calibration.brier_decomposition", "calibration.reliability_diagram", "drift.label_shift"),
    name="Late payment risk",
    one_liner="How likely each member is to pay late in the next month, as a calibrated probability.",
    assumes=(
        "A fixed prediction horizon, identical for every row.",
        "Features are known BEFORE the due date; temporal leakage is a blocking check.",
        "A due unpaid at window.end within the horizon is right-censored, not labelled paid on "
        "time.",
        "Calibration transfers from the held-out fold to the present.",
    ),
    wrong_when=(
        "The reminder policy changed. Reminders are a treatment, and the model will learn that "
        "people who got reminders pay late and invert the causal direction.",
        "A new billing cycle started.",
        "The score is read as a statement about a person rather than about a rate over similar "
        "rows.",
    ),
    interval=(
        "A 90% conformal interval on the individual probability. It is wider than most tools show "
        "and that width is the honest one."
    ),
    refs=(
        "Platt (1999)",
        "Zadrozny and Elkan (2002) KDD",
        "Gneiting and Raftery (2007) JASA 102:359 on proper scoring rules",
    ),
    known=(
        "There is no external published ground truth for this model, and inventing a benchmark "
        "would be the dishonesty this catalog exists to prevent. Every component is externally "
        "grounded separately. The model itself is GATED, not validated: positive Brier skill "
        "against climatology and ECE under 0.05 on held-out data, plus coefficient recovery from "
        "a known logistic generator, which is a construction and is labelled as one."
    ),
    min_n_expr="300 due spells with at least 40 late outcomes, and 10 outcomes per feature",
)

_s(
    "risk.member_disengagement_risk", FORECAST_RISK, risk.member_disengagement_risk,
    streams=("member_lifecycle", "participation"), units=("MemberSpell", "EngagementFeatures"),
    shape="table", min_n=300, cadence="monthly", scope=("cohort", "block", "year"),
    soft=("survival.churn_curve", "calibration.brier_decomposition", "calibration.reliability_diagram"),
    name="Disengagement risk",
    one_liner="How likely each member is to drift away within the horizon, as a calibrated probability.",
    assumes=(
        "A fixed horizon, identical for every row.",
        "No leakage: every feature precedes the horizon it predicts.",
        "The aggregate predicted lapse rate agrees with survival.churn_curve at the same horizon, "
        "within its Greenwood band. Two of our own services disagreeing is a bug.",
    ),
    wrong_when=(
        "A structural exit, graduation for instance, is being predicted as disengagement.",
        "Engagement is a continuum and the horizon is short, so the model is really predicting "
        "recency.",
        "The score is exported or attached to a name outside the roles the manifest permits.",
    ),
    interval="A 90% conformal interval on the individual probability.",
    refs=(
        "Platt (1999)",
        "Gneiting and Raftery (2007) JASA 102:359",
        "Zadrozny and Elkan (2002) KDD",
    ),
    known=(
        "As late payment risk: gated rather than validated, plus the cross-service consistency "
        "check against survival.churn_curve, which is an internal invariant rather than external "
        "truth and is labelled so."
    ),
    min_n_expr="300 member spells with at least 40 lapse outcomes",
)

_s(
    "calibration.isotonic_calibrate", FORECAST_RISK, calibration.isotonic_calibrate,
    streams=(), units=("ScoreArray",), shape="structure", min_n=200, cadence="monthly",
    name="Isotonic calibration",
    one_liner="Bending a model's scores until a claimed 70% really does happen 70% of the time.",
    assumes=(
        "The mapping is fitted out of fold. Fitting it on the training data produces optimistic "
        "calibration, and the check exists so a future caller cannot quietly skip it.",
        "The true relationship between score and probability is monotone.",
    ),
    wrong_when=(
        "There are fewer than 200 observations or 30 positives, where this non-parametric fit "
        "overfits badly and produces a calibration map that is itself miscalibrated out of "
        "sample. The pack switches to Platt scaling automatically and discloses the switch.",
        "The score distribution shifted between fitting and use.",
    ),
    interval=(
        "None. The mapping is fitted, and its uncertainty is reported by "
        "calibration.brier_decomposition rather than pretended here."
    ),
    refs=(
        "Zadrozny and Elkan (2002) KDD",
        "Ayer, Brunk, Ewing, Reid and Silverman (1955) Annals of Mathematical Statistics 26:641",
    ),
    known=(
        "Exact: pool-adjacent-violators has a unique, hand-computable solution. For input "
        "[1, 3, 2, 4] with equal weights the answer is [1, 2.5, 2.5, 4]. Several such vectors "
        "checked exactly, plus the invariants that the output is non-decreasing and that the sum "
        "of fitted values equals the sum of inputs."
    ),
    min_n_expr="200 observations with at least 30 positives",
    implemented=True,
)

_s(
    "calibration.platt_calibrate", FORECAST_RISK, calibration.platt_calibrate,
    streams=(), units=("ScoreArray",), shape="structure", min_n=50, cadence="monthly",
    name="Platt scaling",
    one_liner="The small-sample calibration map: a logistic curve fitted to scores and outcomes.",
    assumes=(
        "A sigmoid relationship between score and probability.",
        "Platt's prior correction to the target labels, which prevents overfitting at small n.",
        "Fitted out of fold.",
    ),
    wrong_when=(
        "The miscalibration is not sigmoid-shaped, where isotonic is the better map given enough "
        "data.",
        "There are fewer than ten positives.",
    ),
    interval="None on the mapping; the Brier decomposition carries the uncertainty.",
    refs=("Platt (1999) Advances in Large Margin Classifiers", "Niculescu-Mizil and Caruana (2005) ICML"),
    known=(
        "Agreement with sklearn.linear_model.LogisticRegression on the same design to 1e-6, plus "
        "the exact property that a perfectly calibrated input maps to approximately the identity."
    ),
    min_n_expr="50 observations with at least 10 positives",
    implemented=True,
)

_s(
    "calibration.brier_decomposition", FORECAST_RISK, calibration.brier_decomposition,
    streams=(), units=("ProbabilityArray",), shape="structure", min_n=100, cadence="monthly",
    name="Brier score and its decomposition",
    one_liner="Whether a probability is worth more than saying everyone is average. The gate metric.",
    assumes=(
        "The labels are the outcome the probability referred to, over the SAME horizon. Half of "
        "all calibration failures in practice are a horizon mismatch rather than a modelling "
        "failure.",
        "The binning is declared, since the decomposition is exact only given a binning.",
    ),
    wrong_when=(
        "The base rate shifted between the calibration set and now, which drift monitoring "
        "exists to catch.",
        "Bins are equal-width on a skewed score distribution, so one bin holds 80% of the data.",
    ),
    interval=(
        "A seeded bootstrap interval on the Brier score. The decomposition components are exact "
        "given the binning."
    ),
    refs=(
        "Brier (1950) Monthly Weather Review 78:1",
        "Murphy (1973) Journal of Applied Meteorology 12:595",
    ),
    known=(
        "Exact and analytic: the Murphy decomposition is an identity, Brier = reliability - "
        "resolution + uncertainty, holding to 1e-12 on arbitrary seeded inputs; uncertainty "
        "equals base_rate * (1 - base_rate) exactly; and a perfectly calibrated constant "
        "forecaster has reliability exactly 0. Three exact identities, no reference "
        "implementation involved."
    ),
    min_n_expr="100 observations, 20 positives, and at least 5 observations per bin",
    implemented=True,
)

_s(
    "calibration.reliability_diagram", FORECAST_RISK, calibration.reliability_diagram,
    streams=(), units=("ProbabilityArray",), shape="table", min_n=100, cadence="monthly",
    soft=("calibration.brier_decomposition",),
    name="Reliability diagram",
    one_liner="For everything we called 70% likely, how often did it actually happen.",
    assumes=(
        "Each bin holds enough observations for its rate to mean anything; sparse bins are "
        "merged and the merge is disclosed.",
        "Every row carries its own n and interval, per the Evidence contract's table rule.",
    ),
    wrong_when=(
        "A bin holds fewer members than the tenant's k, in which case it is merged rather than "
        "shown.",
        "The expected calibration error is above the pack threshold, which blocks a served risk "
        "score entirely.",
    ),
    interval="A Wilson interval per bin on the observed rate. Bins are not equally precise and this shows it.",
    refs=(
        "Murphy and Winkler (1977) Journal of the Royal Statistical Society C 26:41",
        "Naeini, Cooper and Hauskrecht (2015) AAAI on expected calibration error",
    ),
    known=(
        "A perfectly calibrated synthetic generator (p uniform, y Bernoulli(p), seeded) must give "
        "an ECE converging to 0 at rate O(1/sqrt(n)), asserted within a tolerance derived from "
        "that rate at n = 10,000. A deliberately miscalibrated generator reporting p/2 must give "
        "an ECE close to the analytically computable 0.25."
    ),
    min_n_expr="100 observations and 20 positives",
    implemented=True,
)

_s(
    "conformal.split_conformal_interval", FORECAST_RISK, conformal.split_conformal_interval,
    streams=(), units=("ResidualArray",), shape="scalar", min_n=100, cadence="weekly",
    name="Split conformal interval",
    one_liner="A prediction interval that is right nine times out of ten whatever the model is.",
    assumes=(
        "Exchangeability of the calibration set and the new point. Not independence, not "
        "normality, not a correct model. Exchangeability, and nothing else.",
    ),
    wrong_when=(
        "The process changed during the calibration window.",
        "The calibration set was filtered by outcome, which is the censoring trap and is what "
        "conformal.survival_eta_bound exists to handle instead.",
    ),
    interval=(
        "MARGINAL coverage of at least 90%: across many predictions, at least 90% of true values "
        "fall inside. It does NOT promise 90% for this particular category; that is what "
        "conformal.mondrian_eta provides, at a cost in width."
    ),
    refs=(
        "Vovk, Gammerman and Shafer (2005), Algorithmic Learning in a Random World",
        "Lei, G'Sell, Rinaldo, Tibshirani and Wasserman (2018) JASA 113:1094",
    ),
    known=(
        "A theorem, the strongest form of ground truth available: split conformal guarantees "
        "1 - alpha <= coverage <= 1 - alpha + 1/(n+1). The test draws from a deliberately "
        "non-Gaussian, heteroskedastic process at a fixed seed and asserts empirical coverage "
        "over 10,000 held-out points falls inside BOTH bounds, which catches an over-conservative "
        "implementation that a coverage-only test would pass."
    ),
    min_n_expr="ceil(1/alpha) - 1 for the guarantee, but 100 for usefulness; the two thresholds differ and the card says so",
    implemented=True,
)

_s(
    "conformal.survival_eta_bound", FORECAST_RISK, conformal.survival_eta_bound,
    streams=_REQ, units=_SPELL, shape="structure", min_n=200, cadence="on_write",
    scope=("category", "priority", "location_ref"),
    name="Censoring-aware ETA bound",
    one_liner="When a resident can expect their complaint to be resolved, correct nine times out of ten.",
    assumes=(
        "Censoring is independent of the resolution time GIVEN the covariates.",
        "The censoring model is well calibrated, since the weights depend on it.",
        "Exchangeability of requests within the calibration window.",
    ),
    wrong_when=(
        "An admin bulk-closes stale tickets, breaking the censoring model.",
        "The category was newly introduced and has no history.",
        "A step change in staffing occurred inside the calibration window.",
        "Someone uses plain split conformal on the resolved subset instead, which is calibrated "
        "on the fast requests and fails in the direction that makes the ETA look good.",
    ),
    interval=(
        "A distribution-free lower predictive bound with at least 90% marginal coverage. "
        "Deliberately conservative: it will more often be too wide than too narrow, and a "
        "resident is entitled to know which direction the promise errs in."
    ),
    refs=(
        "Candes, Lei and Ren (2023) JRSS-B, Conformalized survival analysis",
        "Vovk, Gammerman and Shafer (2005)",
    ),
    known=(
        "The coverage theorem under censoring: simulate from a known joint distribution of event "
        "and censoring times at a fixed seed and assert empirical coverage of the lower bound is "
        "at least 1 - alpha within binomial tolerance. The second test matters more: naive split "
        "conformal on the resolved subset must UNDER-cover on the same fixture, so the fixture "
        "proves the correction is doing work rather than merely not breaking."
    ),
    min_n_expr="200 spells with at least 100 observed events",
    implemented=True,
)

_s(
    "conformal.mondrian_eta", FORECAST_RISK, conformal.mondrian_eta,
    streams=_REQ, units=_SPELL, shape="structure", min_n=100, cadence="on_write",
    scope=("category", "priority", "location_ref"), soft=("conformal.survival_eta_bound",),
    name="Class-conditional ETA",
    one_liner="An ETA whose promise holds for this kind of complaint, not just on average.",
    assumes=(
        "Exchangeability within each class of the declared taxonomy.",
        "At least 100 calibration points per class, or the class falls back to the marginal "
        "interval with the fallback disclosed per row.",
    ),
    wrong_when=(
        "The taxonomy is too fine, so every class falls back and the service is marginal "
        "conformal with extra steps.",
        "A class's difficulty changed inside the calibration window.",
    ),
    interval=(
        "Coverage WITHIN each class, which is what a resident actually cares about, at the cost "
        "of a wider interval than the marginal version."
    ),
    refs=(
        "Vovk, Lindsay, Nouretdinov and Gammerman (2003) on Mondrian conformal prediction",
        "Candes, Lei and Ren (2023) JRSS-B",
    ),
    known=(
        "The class-conditional coverage theorem, asserted per class on a seeded simulation, plus "
        "the negative control that marginal conformal FAILS per-class coverage on a fixture with "
        "heterogeneous class difficulty. The negative control is again the point."
    ),
    min_n_expr="100 calibration points per class",
    implemented=True,
)

_s(
    "drift.psi", FORECAST_RISK, drift.psi,
    streams=(), units=("FeatureArray",), shape="table", min_n=200, cadence="nightly",
    name="Population stability index",
    one_liner="Whether the people being scored today look like the people the model was fitted on.",
    assumes=(
        "The SAME binning applied to both windows, derived from the reference quantiles and not "
        "recomputed on the current data. Recomputing the bins is the standard implementation bug "
        "and makes PSI approximately zero always.",
        "The reference distribution is supplied by the caller. It is an artifact of a previous "
        "fit, not stream data, and app/stats/ does not fetch it.",
    ),
    wrong_when=(
        "The feature is categorical with rare levels.",
        "The sample sizes differ by an order of magnitude between windows.",
        "The reference is stale, which makes everything look drifted.",
    ),
    interval=(
        "None. PSI is a descriptive divergence, not an estimate. The conventional 0.1 and 0.25 "
        "thresholds come from credit scoring and are not derived from any distribution; a "
        "threshold presented as if it were a p-value is a small lie."
    ),
    refs=("Siddiqi (2006), Credit Risk Scorecards",),
    known=(
        "Exact and hand-computable: PSI of a distribution against itself is 0 exactly; between "
        "two specified discrete distributions it equals sum((a_i - b_i) * ln(a_i / b_i)), "
        "asserted to 1e-12 on several small cases; and PSI is symmetric, which is also asserted."
    ),
    min_n_expr="200 in each window and 20 per bin",
)

_s(
    "drift.ks_test", FORECAST_RISK, drift.ks_test,
    streams=(), units=("FeatureArray",), shape="table", min_n=200, cadence="nightly",
    name="Two-sample Kolmogorov-Smirnov drift",
    one_liner="Whether a continuous feature's distribution has genuinely moved.",
    assumes=(
        "Continuous features; ties degrade the statistic.",
        "A Holm correction across features, because testing thirty features at 0.05 guarantees a "
        "false alarm.",
    ),
    wrong_when=(
        "The feature is discrete or heavily rounded.",
        "The sample is large enough that a trivially small shift is significant, which is why the "
        "statistic is reported alongside the p-value.",
    ),
    interval="None on the statistic. A p-value is not an interval.",
    refs=("Kolmogorov (1933)", "Smirnov (1948) Annals of Mathematical Statistics 19:279"),
    known=(
        "The exact KS statistic for two specified empirical distributions is hand-computable as "
        "the maximum absolute difference of the empirical CDFs, asserted exactly; the asymptotic "
        "p-value against the Kolmogorov distribution's published critical values, where D at "
        "n = 100 and alpha = 0.05 is 0.1358."
    ),
    min_n_expr="200 in each window",
)

_s(
    "drift.label_shift", FORECAST_RISK, drift.label_shift,
    streams=(), units=("ProbabilityArray",), shape="structure", min_n=100, cadence="nightly",
    name="Label shift",
    one_liner="Whether the thing being predicted has become more or less common since the model was fitted.",
    assumes=(
        "The label definition is unchanged between windows.",
        "Both windows are complete, so a partial current window is not read as a collapse.",
    ),
    wrong_when=(
        "The outcome definition changed, for example a redefinition of what counts as late.",
        "The current window is short, so the interval is wide and the shift is not detectable.",
    ),
    interval=(
        "A Wilson interval on each rate and a Newcombe hybrid-score interval on the difference. "
        "Cheap, and it catches the most consequential drift: a risk model fitted when 12% of dues "
        "were late is meaningless once 30% are."
    ),
    refs=("Wilson (1927) JASA 22:209", "Newcombe (1998) Statistics in Medicine 17:873"),
    known=(
        "The Wilson interval has a closed form, checked exactly; the difference interval is "
        "checked against Newcombe's published worked examples."
    ),
    min_n_expr="100 labelled outcomes in each window",
)


# ===========================================================================
# Pack 4: Governance, Segmentation and Text
# ===========================================================================

_BALLOT = ("Ballot", "DecisionOption", "DecisionSpec")
_DEC = ("decision",)

_s(
    "voting.pairwise_matrix", GOVERNANCE, voting.pairwise_matrix,
    streams=_DEC, units=_BALLOT, shape="structure", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",),
    name="Pairwise preference matrix",
    one_liner="For every pair of options, how many ballots preferred one to the other.",
    assumes=(
        "Ballots are rankings, with ties expressed as tiers.",
        "Unranked options are handled by the declared policy, which materially changes the "
        "matrix and is in params_hash.",
    ),
    wrong_when=(
        "Invalid ballots are silently repaired instead of excluded and counted.",
        "The unranked policy is changed after the count.",
    ),
    interval=(
        "None, because this is an exact count of the ballots cast, not an estimate of anything. "
        "Uncertainty about the ELECTORATE is voting.turnout_representativeness and the two must "
        "not be conflated."
    ),
    refs=("Condorcet (1785)", "Tideman (2006), Collective Decisions and Voting"),
    known=(
        "The Tennessee state-capital example (Memphis 42%, Nashville 26%, Chattanooga 15%, "
        "Knoxville 17%), whose pairwise matrix is published and asserted cell by cell."
    ),
    min_n_expr="1 ballot; it is a tabulation, and the floor that matters is the quorum rule",
)

_s(
    "voting.condorcet_winner", GOVERNANCE, voting.condorcet_winner,
    streams=_DEC, units=_BALLOT, shape="structure", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",), soft=("voting.pairwise_matrix",),
    name="Condorcet winner and cycle disclosure",
    one_liner="Whether one option beats every other head to head, and if not, which options cycle.",
    assumes=(
        "Ballots are rankings.",
        "Unranked options are handled by the declared policy.",
    ),
    wrong_when=(
        "A cycle exists and a tool reports a winner anyway. That is the failure this service "
        "exists to prevent: when there is no Condorcet winner the answer is None, with the cycle "
        "enumerated and the Smith set named, and the UI must render the cycle in words above any "
        "result produced by a completion rule.",
        "An even electorate produces exact pairwise ties, which break naive implementations.",
    ),
    interval="None. Exact combinatorics on the ballots cast.",
    refs=("Condorcet (1785)", "Smith (1973) Econometrica 41:1027 for the Smith set"),
    known=(
        "Two textbook cases, both required by docs/RULES.md section 7. Tennessee yields Nashville "
        "as the Condorcet winner. The deliberate cycle, three voters with A>B>C, B>C>A and "
        "C>A>B, must yield winner=None, a cycle of all three and a Smith set of all three. The "
        "second is the one that matters and it is a hard requirement for shipping the pack."
    ),
    min_n_expr="1 ballot",
)

_s(
    "voting.schulze", GOVERNANCE, voting.schulze,
    streams=_DEC, units=_BALLOT, shape="structure", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",), soft=("voting.pairwise_matrix", "voting.condorcet_winner"),
    name="Schulze method",
    one_liner="A complete ranking that agrees with the head-to-head winner whenever one exists.",
    assumes=(
        "The declared rule was Schulze BEFORE ballots were cast (spine rule D1).",
        "Ties in the beatpath relation are broken by the declared, seeded rule, disclosed rather "
        "than silent.",
    ),
    wrong_when=(
        "A committee sees the Schulze result and then argues for Borda instead. The platform will "
        "compute Borda and show it, but labels the declared rule's result as binding.",
        "A cycle exists and the Schulze winner is presented as a Condorcet winner. It is the "
        "RESOLUTION of a cycle, and the distinction is the entire point.",
    ),
    interval="None.",
    refs=("Schulze (2011) Social Choice and Welfare 36:267",),
    known=(
        "Schulze's own paper contains a fully worked 45-voter, 5-candidate example with a "
        "published strongest-path matrix and the final ranking E > A > C > B > D. Asserted "
        "against the path matrix, not only the winner, because a wrong implementation frequently "
        "gets the winner right by luck."
    ),
    min_n_expr="1 ballot",
)

_s(
    "voting.borda", GOVERNANCE, voting.borda,
    streams=_DEC, units=_BALLOT, shape="table", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",),
    name="Borda count",
    one_liner="A positional score per option, shown alongside the declared rule for sensitivity.",
    assumes=(
        "The treatment of unranked options is declared and is in params_hash, since Borda is "
        "acutely sensitive to it.",
    ),
    wrong_when=(
        "It is presented as the result when another rule was declared. It is shown for "
        "sensitivity: under every rule we computed, option B wins is a much stronger mandate "
        "than a bare winner.",
        "Ballots are heavily truncated, which Borda punishes.",
    ),
    interval="None. An exact tabulation.",
    refs=("Borda (1781)", "Saari (1995), Basic Geometry of Voting"),
    known=(
        "The Tennessee example, which has published Borda and approval outcomes differing from "
        "the Condorcet winner and is therefore the ideal fixture for the sensitivity display."
    ),
    min_n_expr="1 ballot",
)

_s(
    "voting.approval", GOVERNANCE, voting.approval,
    streams=_DEC, units=_BALLOT, shape="table", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",),
    name="Approval count",
    one_liner="How many voters approved each option.",
    assumes=("Ballots express genuine approval rather than strategic bundling.",),
    wrong_when=(
        "Voters approve indiscriminately, which flattens the count.",
        "It is presented as the result when another rule was declared.",
    ),
    interval="None. An exact tabulation.",
    refs=("Brams and Fishburn (1978) American Political Science Review 72:831",),
    known="The Tennessee example's published approval outcome.",
    min_n_expr="1 ballot",
)

_s(
    "voting.score", GOVERNANCE, voting.score,
    streams=_DEC, units=_BALLOT, shape="table", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",),
    name="Score count",
    one_liner="The total and mean score each option received.",
    assumes=(
        "The scale is identical on every ballot, which the scale-consistency check verifies.",
        "Scores are treated as ordinal for the headline and only summed because the rule says to.",
    ),
    wrong_when=(
        "Voters use the scale differently, so one enthusiast outweighs three moderates.",
        "It is presented as the result when another rule was declared.",
    ),
    interval="None. An exact tabulation.",
    refs=("Balinski and Laraki (2010), Majority Judgment",),
    known="Exact arithmetic on a fixture, plus the Tennessee example under a score ballot.",
    min_n_expr="1 ballot",
)

_s(
    "voting.stv", GOVERNANCE, voting.stv,
    streams=_DEC, units=_BALLOT, shape="structure", min_n=1, cadence="on_decision_close",
    scope=("decision_ref",),
    name="Single transferable vote",
    one_liner="A multi-seat count, round by round, because in STV the count is the accountability.",
    assumes=(
        "The transfer method and quota were declared in advance.",
        "Ties are broken by the declared seeded rule, so a contested election can be recounted "
        "identically.",
    ),
    wrong_when=(
        "The transfer method is changed after the fact.",
        "Ballots are truncated heavily, so many exhaust and the last seat is decided by a small "
        "remnant, which the exhausted-ballot share exposes.",
    ),
    interval=(
        "None. STV is non-monotonic, so an interval would be meaningless even in principle."
    ),
    refs=(
        "Tideman (1995) Journal of Economic Perspectives 9:27",
        "ERS97 rules for the Gregory transfer",
        "Meek (1969) Computer Journal 12:23",
    ),
    known=(
        "A published STV count with a documented round-by-round result, asserted round by round "
        "rather than on the final seats, since a wrong transfer rule often lands on the right "
        "seats."
    ),
    min_n_expr="seats + 1 options and at least seats valid ballots",
)

_s(
    "voting.turnout_representativeness", GOVERNANCE, voting.turnout_representativeness,
    streams=("decision", "member_lifecycle"), units=("Ballot", "DecisionSpec", "RosterSnapshot"),
    shape="structure", min_n=30, cadence="on_decision_close", scope=("decision_ref", "block", "year"),
    name="Turnout and representativeness",
    one_liner="Who voted, who did not, and whether the result can be read as the community's view.",
    assumes=(
        "The eligible frame was frozen at opened_at and is accurate, so a later move-in cannot "
        "change a past turnout figure.",
    ),
    wrong_when=(
        "Someone reads 68% of votes favoured the proposal as 68% of the community favours the "
        "proposal at 12% turnout. That inference needs raking weights and a design effect, and "
        "even then it is weak. This is the single most common misuse of a community poll, so "
        "below 30% turnout the generalisation is blocked while the tabulation is still shown.",
        "A per-stratum row falls below the tenant's k, where it is suppressed with no override.",
    ),
    interval=(
        "A Wilson interval on the turnout proportion. Per-stratum rows carry their own, and the "
        "chi-square against the eligible population has none, because a p-value is not an "
        "interval."
    ),
    refs=("Kish (1965), Survey Sampling", "Wilson (1927) JASA 22:209"),
    known=(
        "Wilson intervals have a closed form asserted exactly against published worked values "
        "(Wilson's tabulated cases and Newcombe's 1998 comparison paper); the chi-square "
        "goodness-of-fit against known expected counts is hand-computable and asserted exactly."
    ),
    min_n_expr="30 ballots for the aggregate, and the tenant's k per stratum row",
)

_s(
    "budgeting.method_of_equal_shares", GOVERNANCE, budgeting.method_of_equal_shares,
    streams=_DEC, units=_BALLOT, shape="structure", min_n=20, cadence="on_decision_close",
    scope=("decision_ref",),
    name="Method of Equal Shares",
    one_liner="Funding projects so that every voter's share of the budget counts for something.",
    assumes=(
        "Each voter has an equal share of the budget.",
        "Approvals express genuine support rather than strategic bundling.",
        "The completion method for leftover budget is declared and disclosed.",
    ),
    wrong_when=(
        "Options have wildly unequal costs and voters approve indiscriminately.",
        "The same physical project is split into several options to game the rule, which the "
        "fairness report will show as one stratum capturing a disproportionate share.",
        "Fewer than twenty ballots, where the proportionality guarantee is vacuous because one "
        "voter's budget share funds nothing.",
    ),
    interval=(
        "None. It is an allocation rule, not an estimate. The guarantee it offers is extended "
        "justified representation, which is verified computationally on the actual result."
    ),
    refs=(
        "Peters and Skowron (2020) EC'20",
        "Peters, Pierczynski and Skowron (2021) NeurIPS",
        "The equalshares.net reference instances",
    ),
    known=(
        "The worked instances published with the Method of Equal Shares papers, whose funded sets "
        "are given explicitly. Plus a property test on seeded random instances: EJR must hold for "
        "MES and must be VIOLATED by greedy_knapsack on the constructed counterexample from the "
        "literature. The negative control proves the property checker works."
    ),
    min_n_expr="20 ballots and 3 options",
)

_s(
    "budgeting.greedy_knapsack", GOVERNANCE, budgeting.greedy_knapsack,
    streams=_DEC, units=_BALLOT, shape="structure", min_n=20, cadence="on_decision_close",
    scope=("decision_ref",), soft=("budgeting.method_of_equal_shares",),
    name="Greedy utilitarian allocation",
    one_liner="The allocation that maximises total approvals per rupee, shown as the trade-off.",
    assumes=("Total approval is the objective, which is a choice and not the only defensible one.",),
    wrong_when=(
        "It is shipped INSTEAD of the Method of Equal Shares rather than alongside it. A "
        "committee should see the trade-off between total satisfaction and proportional fairness "
        "explicitly.",
        "A minority's preferences are systematically unfunded, which this rule permits and the "
        "fairness report exposes.",
    ),
    interval="None. An allocation rule.",
    refs=("Dantzig (1957) Operations Research 5:266", "Peters and Skowron (2020) EC'20"),
    known=(
        "Exact dynamic-programming optimum on small instances, and the known one-half "
        "approximation bound of the greedy rule against that optimum."
    ),
    min_n_expr="20 ballots and 3 options",
)

_s(
    "budgeting.fairness_report", GOVERNANCE, budgeting.fairness_report,
    streams=("decision", "member_lifecycle"), units=("Ballot", "DecisionOption", "RosterSnapshot"),
    shape="table", min_n=5, cadence="on_decision_close", scope=("decision_ref", "block", "year"),
    soft=("budgeting.method_of_equal_shares",),
    name="Budget fairness by stratum",
    one_liner="Whether Block C, who are 11% of the society, got any of their preferences funded.",
    assumes=(
        "The strata are the ones the vertical declared, and each published row clears the "
        "tenant's k with no override.",
    ),
    wrong_when=(
        "Small strata are dropped rather than pooled into other, which hides exactly the group "
        "the report exists to protect.",
        "Utilisation is read as entitlement rather than as a description of what happened.",
    ),
    interval=(
        "A seeded bias-corrected bootstrap interval on utilisation. This is the output that makes "
        "participatory budgeting trustworthy rather than a majority tool with extra steps."
    ),
    refs=(
        "Peters, Pierczynski and Skowron (2021) NeurIPS",
        "Efron and Tibshirani (1993), An Introduction to the Bootstrap",
    ),
    known=(
        "The utilisation identity is exact arithmetic on the allocation. The interesting "
        "assertion is a property test that follows from the MES guarantee: no stratum with more "
        "than a proportional share of voters may receive less than its proportional share of "
        "budget by more than the cost of the cheapest unfunded project they approved."
    ),
    min_n_expr="the tenant's k per stratum row, strictly enforced",
)

_s(
    "sortition.stratified_panel", GOVERNANCE, sortition.stratified_panel,
    streams=("member_lifecycle",), units=("RosterSnapshot",), shape="structure", min_n=3,
    cadence="on_demand", scope=("panel_ref",),
    name="Stratified sortition",
    one_liner="Drawing a panel by lottery that still meets the quotas, with everyone's odds visible.",
    assumes=(
        "The volunteer pool is the sampling frame. Sortition makes the PANEL representative of "
        "the POOL, not of the community, and if the pool is skewed the panel inherits the skew. "
        "This is the most misunderstood property of citizens' assemblies.",
        "Quota lower bounds are satisfiable from the pool, which is a blocking check.",
    ),
    wrong_when=(
        "The pool self-selected heavily, which sortition cannot fix and must therefore disclose.",
        "Quotas are so tight only one panel is feasible, which makes the lottery ceremonial.",
        "The minimum selection probability across the pool is near zero, since the fairness of "
        "sortition is precisely that everyone had a real chance.",
    ),
    interval=(
        "Monte Carlo intervals on the per-person selection probability, from the seeded lottery "
        "distribution. The panel itself has none: it is a draw, not an estimate."
    ),
    refs=("Flanigan, Golz, Gupta, Hennig and Procaccia (2021) Nature 596:548",),
    known=(
        "Exact: on a seeded run all quotas are satisfied and the result is reproducible bit for "
        "bit. Analytic: where an equal-probability selection is feasible, the maximin objective "
        "must attain exactly panel_size / pool_size for every member, a provable optimum asserted "
        "within Monte Carlo tolerance over many seeded draws."
    ),
    min_n_expr="a pool at least 3x the panel size, with every quota lower bound satisfiable",
)

_s(
    "survey.likert_distribution", GOVERNANCE, survey.likert_distribution,
    streams=("signal",), units=("OrdinalResponse",), shape="structure", min_n=20,
    cadence="on_survey_close", scope=("item_id", "block", "department", "year"),
    name="Likert distribution",
    one_liner="The full shape of the answers to a rating question, with no mean anywhere.",
    assumes=(
        "The levels are ordered but NOT equally spaced. The gap between poor and fair is not the "
        "gap between good and excellent, which is why the mean is meaningless and the median plus "
        "the full distribution is not.",
        "All pooled responses share one scale, which is blocking: a 1 to 5 and a 1 to 7 item "
        "pooled together happens constantly in real survey data.",
    ),
    wrong_when=(
        "Two groups are compared by mean difference.",
        "A change from 3.8 to 4.0 is reported as an improvement. The returned structure has no "
        "field a mean could live in, so this cannot be done through this service at all.",
        "More than 60% sit in the top or bottom box, where the item cannot discriminate and "
        "comparisons are driven by the bound.",
    ),
    interval=(
        "Bootstrap intervals on each proportion. Cliff's delta is a probability-of-superiority "
        "effect size: 0.3 means a randomly chosen member of group A rates higher than a randomly "
        "chosen member of group B about 65% of the time."
    ),
    refs=(
        "Jamieson (2004) Medical Education 38:1217 on Likert misuse",
        "Cliff (1993) Psychological Bulletin 114:494",
    ),
    known=(
        "Cliff's delta has an exact closed form as a count of dominance pairs, hand-computable on "
        "small vectors and asserted exactly. Its identity with the Mann-Whitney U statistic, "
        "delta = 2U/(mn) - 1, is asserted against a reference U computation."
    ),
    min_n_expr="20 responses per item, and the tenant's k per group row",
)

_s(
    "survey.ordinal_logistic", GOVERNANCE, survey.ordinal_logistic,
    streams=("signal",), units=("OrdinalResponse",), shape="table", min_n=100,
    cadence="on_survey_close", scope=("item_id",),
    name="Ordinal logistic regression",
    one_liner="Which characteristics move satisfaction up the scale, and by what odds.",
    assumes=(
        "Proportional odds: the effect of a covariate is the same at every cutpoint of the "
        "scale, which the Brant test measures rather than assumes.",
        "Independent responses.",
        "The ordinal levels are correctly ordered.",
    ),
    wrong_when=(
        "A covariate moves people out of very dissatisfied but does nothing at the top of the "
        "scale, which is a proportional-odds violation and is common with satisfaction data. The "
        "row is then suppressed and replaced by the per-cutpoint effects, which are longer to "
        "read and correct.",
        "Responses are clustered by household and treated as independent, which understates the "
        "standard errors.",
    ),
    interval=(
        "A profile-likelihood interval on the proportional odds ratio. Multiplicative, with 1.0 "
        "as no effect."
    ),
    refs=(
        "McCullagh (1980) JRSS-B 42:109",
        "Brant (1990) Biometrics 46:1171",
        "Venables and Ripley, MASS, 4th ed., section 7.3",
    ),
    known=(
        "The MASS::polr housing-satisfaction example, the canonical published proportional-odds "
        "fit, with published coefficients for Infl, Type and Cont and published cutpoints, "
        "tolerance 1e-3. The Brant test is asserted on the same dataset against its published "
        "verdict."
    ),
    min_n_expr="10 responses per covariate per sparse response level, in practice 100 for 3 covariates",
)

_s(
    "survey.raking_weights", GOVERNANCE, survey.raking_weights,
    streams=("signal", "member_lifecycle"), units=("OrdinalResponse", "RosterSnapshot"),
    shape="table", min_n=50, cadence="on_survey_close", scope=("survey_ref",),
    name="Raking weights",
    one_liner="Re-weighting respondents so the sample's composition matches the community's.",
    assumes=(
        "The population margins are correct.",
        "Non-response is ignorable WITHIN the raking cells. That is the assumption that actually "
        "carries the inference and it is untestable from the sample alone.",
    ),
    wrong_when=(
        "The people who did not respond differ from those who did in a way not captured by the "
        "raking variables. Raking fixes composition, never motivation.",
        "A cell has zero respondents, which cannot be raked; the service names the cell rather "
        "than silently dropping the margin.",
        "A weight reaches 40, which means one person is speaking for forty and the estimate is "
        "that person's opinion.",
    ),
    interval=(
        "The weights themselves have none. Every downstream estimate widens its interval by the "
        "design effect, which survey.design_effect reports."
    ),
    refs=(
        "Deming and Stephan (1940) Annals of Mathematical Statistics 11:427",
        "Kolenikov (2014) Stata Journal 14:22",
    ),
    known=(
        "Iterative proportional fitting converges to the margins exactly, which is a theorem, so "
        "the achieved margins must match the targets to within tol on several seeded random "
        "tables. Second ground truth: agreement with R survey::rake on a published worked "
        "example."
    ),
    min_n_expr="50 respondents and at least 5 in every cell being raked",
)

_s(
    "survey.design_effect", GOVERNANCE, survey.design_effect,
    streams=("signal",), units=("ProbabilityArray",), shape="scalar", min_n=1,
    cadence="on_survey_close", scope=("survey_ref",), soft=("survey.raking_weights",),
    name="Kish design effect",
    one_liner="Turning 340 residents surveyed, weighted into effective sample size 96.",
    assumes=("The weights are the ones actually applied to the estimate being reported.",),
    wrong_when=(
        "It is omitted, which is the usual case, and a weighted estimate is then quoted with its "
        "raw n. The effective sample size is the number that should be in the reader's head.",
    ),
    interval="None. It is an exact function of the weights.",
    refs=("Kish (1965), Survey Sampling",),
    known=(
        "Exact closed form, hand-computable, asserted to 1e-12. Exactly 1 for uniform weights, "
        "and equal to the published Kish worked example value for his tabulated case."
    ),
)

_s(
    "segmentation.rfm_features", GOVERNANCE, segmentation.rfm_features,
    streams=("participation", "ledger"), units=("ParticipationEvent", "LedgerEntry"),
    shape="table", min_n=1, cadence="weekly", scope=("group_ref",),
    name="Engagement features",
    one_liner="Recency, frequency, breadth and contribution per member, as one table.",
    assumes=(
        "The window bounds every feature, so a feature is never computed from data outside it.",
        "It is a feature builder, not an estimator, and returns Evidence only because everything "
        "crossing the boundary does.",
    ),
    wrong_when=(
        "A member with no participation is given recency zero or None instead of their tenure, "
        "which quietly makes the never-engaged look freshly engaged.",
        "Contribution is summed across currencies.",
    ),
    interval="None. A deterministic transform.",
    refs=("Hughes (1994), Strategic Database Marketing", "Fader, Hardie and Lee (2005) Journal of Marketing Research 42:415"),
    known=(
        "Exact arithmetic on a fixture, including the boundary cases: a member with no "
        "participation gets recency_days equal to their tenure, not None and not zero."
    ),
)

_s(
    "segmentation.gmm_select_k", GOVERNANCE, segmentation.gmm_select_k,
    streams=("participation",), units=("EngagementFeatures",), shape="structure", min_n=50,
    cadence="weekly", scope=("group_ref",), soft=("segmentation.rfm_features",),
    name="Gaussian mixture segmentation",
    one_liner="Whether members fall into distinct engagement groups, and how many.",
    assumes=(
        "Clusters are roughly elliptical in the scaled feature space.",
        "Robust scaling is mandatory, since volunteer hours and login counts differ by orders of "
        "magnitude and an unscaled fit clusters on the largest-variance feature alone.",
    ),
    wrong_when=(
        "The true structure is a continuum, which engagement usually is, so the clusters are cuts "
        "through a gradient and will move between months. The seeded stability score is what "
        "tells you that happened, and it is shown next to the segments always.",
        "BIC and silhouette disagree on k, which is itself the finding and is reported rather "
        "than resolved by picking one.",
        "A cluster falls below the tenant's k, where it is merged rather than labelled.",
    ),
    interval=(
        "None on the labels. The bootstrap adjusted Rand index across resamples is the honest "
        "uncertainty measure: a clustering that does not survive resampling is a drawing, not a "
        "segmentation."
    ),
    refs=(
        "Schwarz (1978) Annals of Statistics 6:461",
        "Rousseeuw (1987) Journal of Computational and Applied Mathematics 20:53",
        "Hennig (2007) Computational Statistics and Data Analysis 52:258",
    ),
    known=(
        "Synthetic: data drawn from a 3-component Gaussian mixture with a specified separation "
        "must minimise BIC at k = 3, seeded and repeated. Published: silhouette on iris is well "
        "documented to peak at k = 2 rather than the 3 true species, and our implementation must "
        "reproduce that, which is useful precisely because it is the counter-intuitive published "
        "answer."
    ),
    min_n_expr="50 members",
)

_s(
    "segmentation.stable_labels", GOVERNANCE, segmentation.stable_labels,
    streams=("participation",), units=("EngagementFeatures",), shape="structure", min_n=50,
    cadence="weekly", scope=("group_ref",), soft=("segmentation.gmm_select_k",),
    name="Stable segment labels",
    one_liner="Making sure Segment 3 means the same thing in September as it did in August.",
    assumes=(
        "The two label assignments describe the same population and the same features.",
        "Matching is on centroids, by the Hungarian algorithm, not on label overlap.",
    ),
    wrong_when=(
        "The segments genuinely changed, in which case pretending they are the same ones is worse "
        "than renumbering, and the drift check blocks.",
        "The feature scaling changed between runs, which moves every centroid.",
    ),
    interval="None. It is a matching procedure, not an estimator.",
    refs=("Kuhn (1955) Naval Research Logistics Quarterly 2:83", "Hennig (2007)"),
    known=(
        "Exact: a fixture whose labels are a known permutation of the reference must map back to "
        "the identity, and a fixture whose centroids genuinely moved must trigger the drift "
        "check. The negative control is again the point."
    ),
)

_s(
    "network.louvain_communities", GOVERNANCE, network.louvain_communities,
    streams=("participation",), units=("InteractionEdge",), shape="structure", min_n=30,
    cadence="weekly", scope=("group_ref",),
    name="Community detection",
    one_liner="Which clusters of people actually interact with each other.",
    assumes=(
        "The interaction graph reflects real relationships. It does not: it reflects co-presence "
        "at events, which is a proxy and sometimes a poor one.",
        "The co-attendance normalisation constant is declared and enters params_hash, because a "
        "different normalisation gives a different graph.",
    ),
    wrong_when=(
        "One large event dominates the edge set.",
        "The resolution parameter was tuned until the number of communities looked plausible.",
        "The observed partition is no better than a configuration-model null, which blocks: "
        "Louvain partitions a random graph without complaint and reporting that as community "
        "structure is fiction.",
    ),
    interval=(
        "None on the partition. The seeded stability across restarts and the null-model "
        "comparison are the uncertainty statements."
    ),
    refs=(
        "Blondel, Guillaume, Lambiotte and Lefebvre (2008) JSTAT P10008",
        "Fortunato and Barthelemy (2007) PNAS 104:36 on the resolution limit",
    ),
    known=(
        "Zachary's karate club: Louvain finds 4 communities with modularity about 0.42 and the "
        "split separates the two known factions around nodes 0 and 33, all three published and "
        "asserted. Second: modularity has a closed form, asserted exactly for a hand-computed "
        "partition on a small graph."
    ),
    min_n_expr="30 nodes and 60 edges",
)

_s(
    "network.betweenness_centrality", GOVERNANCE, network.betweenness_centrality,
    streams=("participation",), units=("InteractionEdge",), shape="table", min_n=30,
    cadence="weekly", scope=("group_ref",),
    name="Betweenness centrality",
    one_liner="Who sits on the paths between otherwise separate parts of the community.",
    assumes=(
        "The edge set is the declared projection with its declared normalisation.",
        "Reported people clear the tenant's k in any grouping shown.",
    ),
    wrong_when=(
        "The result is used to name informal power brokers in a community with active political "
        "friction. rwa_society disables this service for exactly that reason, which is a "
        "statement about that community and is readable in its manifest.",
        "One large gathering dominates the graph, which makes everyone a connector.",
    ),
    interval="None on the centralities. They are exact given the graph, and the graph is the assumption.",
    refs=("Freeman (1977) Sociometry 40:35", "Brandes (2001) Journal of Mathematical Sociology 25:163"),
    known=(
        "Exact closed forms on two graphs where betweenness is analytically known: on a path "
        "graph of n nodes the betweenness of node i is i(n-1-i), and on a star the centre has "
        "normalised betweenness exactly 1 and every leaf exactly 0. Plus the published "
        "karate-club values, where nodes 0 and 33 are the documented highest."
    ),
    min_n_expr="30 nodes and 60 edges",
)

_s(
    "network.isolation_report", GOVERNANCE, network.isolation_report,
    streams=("participation", "member_lifecycle"), units=("InteractionEdge", "RosterSnapshot"),
    shape="structure", min_n=30, cadence="weekly", scope=("block", "year", "cohort"),
    name="Isolation by stratum",
    one_liner="Which parts of the community are disconnected from the rest, as shares, never as names.",
    assumes=(
        "Isolation in this graph means no recorded interaction, which is not the same as being "
        "socially isolated in life.",
        "Every stratum row clears the tenant's k.",
    ),
    wrong_when=(
        "Someone wants the list of individuals. A list of socially isolated neighbours is the "
        "most sensitive output this platform could produce, and this service is shaped so the "
        "list cannot be constructed: it returns shares by stratum and nothing else.",
        "Participation is recorded on only one channel, so people active on WhatsApp look "
        "isolated.",
    ),
    interval="A Wilson interval on the isolated share, per stratum row.",
    refs=("Wilson (1927) JASA 22:209", "Wasserman and Faust (1994), Social Network Analysis"),
    known="The Wilson interval closed form, exact; isolated-node counting is exact graph arithmetic on a fixture.",
    min_n_expr="30 nodes, and the tenant's k per stratum row",
)

_s(
    "text.tfidf_similarity", GOVERNANCE, text.tfidf_similarity,
    streams=("signal",), units=("TextDoc",), shape="table", min_n=2, cadence="weekly",
    scope=("category",),
    name="TF-IDF similarity",
    one_liner="Which pieces of text use the same distinctive words.",
    assumes=(
        "The sublinear scaling and smoothing conventions are declared, since they change the "
        "numbers.",
        "Tokens arrive precomputed; this service does not tokenise differently from the corpus.",
    ),
    wrong_when=(
        "The corpus is tiny, so inverse document frequency is dominated by one document.",
        "Documents are in mixed languages.",
    ),
    interval="None. Cosine similarity on a fixed vocabulary is exact.",
    refs=(
        "Salton and Buckley (1988) Information Processing and Management 24:513",
        "Manning, Raghavan and Schutze (2008), Introduction to Information Retrieval, ch. 6",
    ),
    known=(
        "Exact hand computation on a three-document toy corpus with the smoothing convention "
        "stated, plus agreement with sklearn's TfidfVectorizer under matching parameters as a "
        "second oracle."
    ),
    min_n_expr="2 documents",
)

_s(
    "text.near_duplicate_candidates", GOVERNANCE, text.near_duplicate_candidates,
    streams=("signal",), units=("TextDoc",), shape="table", min_n=1, cadence="on_submission",
    scope=("category", "location_ref"),
    name="Near-duplicate detection",
    one_liner="Telling someone that three neighbours already reported this, while they are still typing.",
    assumes=(
        "Lexical or embedding similarity approximates semantic duplication. It does not always: "
        "no water in B-402 and no water in C-101 are lexically near-identical and are different "
        "problems, which is why location is a hard filter before similarity, not a ranking "
        "feature.",
        "Embeddings arrive precomputed; this module never calls a model.",
    ),
    wrong_when=(
        "Texts are shorter than five tokens, where Jaccard is dominated by one word.",
        "A recurring seasonal complaint is flagged as a duplicate of last year's.",
        "Fewer than 64 MinHash permutations are used, where the estimate is too noisy to "
        "threshold.",
    ),
    interval=(
        "None on cosine, which is exact. The MinHash estimate has a standard error of "
        "sqrt(J(1-J)/k), about 0.04 at 128 permutations for J = 0.7."
    ),
    refs=(
        "Broder (1997) on MinHash",
        "Leskovec, Rajaraman and Ullman, Mining of Massive Datasets, ch. 3",
    ),
    known=(
        "Analytic and unusually clean: exact Jaccard is computable by definition on token sets "
        "and asserted exactly; the MinHash estimator is unbiased with variance J(1-J)/k, so the "
        "test asserts the estimate falls within three standard errors AND that the empirical "
        "variance across seeds matches the analytic variance."
    ),
    min_n_expr="1 candidate document; this runs at submission time on whatever exists",
)

_s(
    "text.nmf_topics", GOVERNANCE, text.nmf_topics,
    streams=("signal",), units=("TextDoc",), shape="structure", min_n=200, cadence="monthly",
    scope=("category",),
    name="NMF topics",
    one_liner="The recurring themes in what people are writing, as term lists.",
    assumes=("Documents are mixtures of a small number of additive term distributions.",),
    wrong_when=(
        "The corpus is dominated by one category, so the model splits it into near-duplicates of "
        "itself.",
        "The vocabulary is small and topics collapse.",
        "The number of topics was chosen to look tidy. When auto, the selection curve is returned "
        "so the choice is visible.",
        "Fewer than 200 documents, where topics are single documents with a label.",
    ),
    interval=(
        "None. NPMI coherence and seeded restart stability are the quality statements and both "
        "are always shown; an incoherent topic list destroys trust in everything next to it."
    ),
    refs=(
        "Lee and Seung (1999) Nature 401:788",
        "Boutsidis and Gallopoulos (2008) Pattern Recognition 41:1350",
        "Bouma (2009) on NPMI coherence",
    ),
    known=(
        "Partial, and stated plainly: there is no published topic-model fixture with "
        "known-correct topics for this domain, and asserting against one would be inventing a "
        "ground truth. What is asserted: on a synthetic corpus generated from three specified "
        "topic-word distributions at a fixed seed, NMF must recover them up to permutation with "
        "cosine similarity above 0.9. The coherence and stability metrics have exact known "
        "answers and are tested separately."
    ),
    min_n_expr="200 documents and 30 per topic",
)

_s(
    "privacy.k_anonymity_suppress", GOVERNANCE, privacy.k_anonymity_suppress,
    streams=(), units=("TableEvidence",), shape="table", min_n=0, cadence="on_demand",
    name="k-anonymity suppression",
    one_liner="Hiding any row that describes too few people, and any row that would give it away.",
    assumes=(
        "k is set correctly for the community's size and the sensitivity of the attribute.",
        "Complementary suppression is on. Suppressing one cell in a table whose total is "
        "published lets that cell be recovered by subtraction, so additional cells are suppressed "
        "until no suppressed value is uniquely determined.",
    ),
    wrong_when=(
        "An attacker has background knowledge, which k-anonymity does not protect against.",
        "Several tables are published over time and their differences reveal an individual, which "
        "is why params_hash and the suppression record are stored per run.",
        "Complementary suppression is impossible without suppressing the whole table, in which "
        "case the whole table is suppressed.",
    ),
    interval="Unchanged from the input envelope. This is a filter, not an estimator.",
    refs=(
        "Sweeney (2002) International Journal of Uncertainty, Fuzziness and Knowledge-Based Systems 10:557",
        "Cox (1980) JASA 75:377 on complementary suppression",
    ),
    known=(
        "Exact rule verification: every published cell has count at least k, and a constructed "
        "table where naive suppression leaks a cell by subtraction must trigger secondary "
        "suppression. The leak fixture is the important test and is a documented example from the "
        "statistical disclosure control literature."
    ),
    min_n_expr="not applicable; it is a filter, and the last thing every Pack 4 service calls",
)

_s(
    "privacy.laplace_noise", GOVERNANCE, privacy.laplace_noise,
    streams=(), units=("TableEvidence",), shape="scalar", min_n=0, cadence="on_demand",
    name="Laplace mechanism",
    one_liner="Adding calibrated noise so one household cannot be read out of a published figure.",
    assumes=(
        "The declared sensitivity bounds the effect of one member on the statistic. A wrong "
        "sensitivity means no privacy guarantee at all, and it is the most common failure, which "
        "is why an undeclared sensitivity is blocking.",
        "Epsilon composes across every query on the same data, and the consumed epsilon is "
        "returned so the caller can maintain a budget.",
    ),
    wrong_when=(
        "The same statistic is queried repeatedly.",
        "Noise is added to a figure that is also published exactly elsewhere.",
    ),
    interval=(
        "The interval reflects ADDED NOISE, not sampling uncertainty. A DP figure at small n has "
        "both, and the caveat says the displayed interval is noise only."
    ),
    refs=(
        "Dwork, McSherry, Nissim and Smith (2006) TCC",
        "Dwork and Roth (2014), The Algorithmic Foundations of Differential Privacy",
    ),
    known=(
        "The Laplace mechanism with scale sensitivity/epsilon satisfies epsilon-DP, a theorem. "
        "Tests: the empirical noise distribution over seeded draws matches Laplace with that "
        "scale by KS test; the mechanism is unbiased so the mean of many draws converges at the "
        "known rate; sequential composition adds epsilons exactly; and the noised output is "
        "reproducible from the seed."
    ),
    min_n_expr="not applicable",
)

_s(
    "audit.benford_digits", GOVERNANCE, audit.benford_digits,
    streams=("ledger",), units=("LedgerEntry",), shape="table", min_n=300, cadence="monthly",
    scope=("category",),
    name="Benford first-digit test",
    one_liner="Whether the leading digits of a set of amounts look like naturally occurring numbers.",
    assumes=(
        "Amounts arise from a process spanning several orders of magnitude.",
        "Amounts are neither bounded nor rounded, both of which are blocking checks.",
        "A deviation is a prompt to look, not evidence of anything. That caveat is permanent and "
        "not removable.",
    ),
    wrong_when=(
        "Almost always in a small community ledger, which is why the two blocking checks come "
        "first and why this service is off by default in every vertical manifest. A series of "
        "identical monthly maintenance dues produces a spectacular false positive, so the service "
        "refuses rather than reports.",
    ),
    interval="Wilson intervals on the observed digit frequencies against the Benford expectation.",
    refs=(
        "Benford (1938) Proceedings of the American Philosophical Society 78:551",
        "Nigrini (2012), Benford's Law",
        "Cho and Gaines (2007) The American Statistician 61:218 on its misuse",
    ),
    known=(
        "The Benford probabilities are a closed form, log10(1 + 1/d), asserted exactly; the "
        "chi-square against known counts is hand-computable and asserted; and a negative control: "
        "a uniform digit distribution must be flagged while a sample drawn from a genuine Benford "
        "process at a fixed seed must not."
    ),
    min_n_expr="300 entries, and only for categories spanning at least two orders of magnitude",
)


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------


def get(service_id: str) -> ServiceSpec:
    """One spec by id. Raises KeyError, which the API turns into a 404."""
    return REGISTRY[service_id]


def method_card(service_id: str) -> MethodCard:
    """What GET /api/methods/{method_id} serves. Public and unauthenticated by design."""
    return REGISTRY[service_id].method_card


def service_ids() -> tuple[str, ...]:
    return tuple(sorted(REGISTRY))


def for_pack(pack_id: str) -> tuple[ServiceSpec, ...]:
    if pack_id not in PACKS:
        raise KeyError(pack_id)
    return tuple(sorted((s for s in REGISTRY.values() if s.pack == pack_id), key=lambda s: s.id))


def packs() -> tuple[PackSpec, ...]:
    return tuple(PACKS.values())


def available_for_streams(streams: frozenset[str]) -> tuple[ServiceSpec, ...]:
    """
    Which services a tenant could run given the streams it supports.

    A service whose required stream is absent is not an error and is not hidden:
    docs/VERTICALS.md rule 1 says the onboarding screen shows it greyed with the
    reason, because a tenant should be able to see what switching a domain on
    would buy them. This function answers the first half of that.
    """
    return tuple(
        sorted(
            (s for s in REGISTRY.values() if s.required_streams <= streams),
            key=lambda s: s.id,
        )
    )


def missing_streams(service_id: str, streams: frozenset[str]) -> frozenset[str]:
    """The reason string for the greyed-out case: which streams are still needed."""
    return REGISTRY[service_id].required_streams - streams


def implemented_ids() -> tuple[str, ...]:
    """
    Services whose mathematics actually exists. The rest are registered, carry a
    complete Method Card, and raise NotImplementedError when called: specified
    and honest about not being built, rather than absent and invisible.
    """
    return tuple(sorted(s.id for s in REGISTRY.values() if s.implemented))


__all__ = [
    "BAYES_RANKING",
    "CADENCES",
    "FORECAST_RISK",
    "GOVERNANCE",
    "PACKS",
    "REGISTRY",
    "RELIABILITY",
    "PackSpec",
    "ServiceSpec",
    "available_for_streams",
    "for_pack",
    "get",
    "implemented_ids",
    "method_card",
    "missing_streams",
    "packs",
    "service_ids",
]
