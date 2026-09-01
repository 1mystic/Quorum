"""
A/B tests over the exposure log.

Every service here consumes ParticipationEvent rows with arm_ref and the nudge_*
kinds. Without the exposure log they would measure self-selection.

Three things in this module are worth reading before the code.

**The posterior probability is not a p-value.** `P(B > A)` is computed exactly,
by Miller's finite sum over the integer Beta parameters, and the Method Card says
in those words that it must not be read as a significance level. A committee that
reads 0.94 as "significant at the 6% level" has been misled by the number's
shape, so the caveat is not removable.

**The expected loss is not zero when the two arms are identical.** Two
independent Beta(a, b) posteriors have `E[(theta_B - theta_A)^+] > 0`: it is
`E|theta_B - theta_A| / 2`. What is true, and what this module asserts, is that
the two losses are then exactly equal, and that `loss_a - loss_b` equals the
difference of the posterior means for any pair of posteriors. The catalog said
zero; that was wrong and is corrected there.

**Peeking is made safe rather than forbidden.** A committee will look at a
running experiment every day whatever the documentation says. So
`sequential_stopping_rule` is an always-valid method: a nonnegative
supermartingale under the null, whose crossing probability is bounded by Ville's
inequality at every stopping time simultaneously. The naive alternative, a
fixed-horizon two-proportion z test consulted at every peek, is available under
`method="fixed_horizon_z"` and is refused with a blocking check, because it is
the single most common real statistics bug in this domain and refusing it out
loud is more useful than not offering it.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import betainc, chi2_sf, norm_sf
from app.stats.streams.participation import EXPOSURE_KINDS

# docs/STATS_CATALOG.md: 100 exposures per arm AND 10 conversions per arm. Below
# ten conversions the posterior is dominated by the prior and P(B>A) hovers near
# 0.5 while still looking like a measurement.
MIN_EXPOSURES_PER_ARM = 100
MIN_CONVERSIONS_PER_ARM = 10

# Kohavi, Tang and Xu treat a sample ratio mismatch as a pipeline fault rather
# than a finding, and use a very small alpha because the check runs on every
# render: at 0.05 one honest experiment in twenty would be blocked.
SRM_ALPHA = 0.001
BALANCE_ALPHA = 0.001

ALWAYS_VALID_METHODS = ("evalue", "msprt")
SEQUENTIAL_METHODS = ("evalue", "msprt", "fixed_horizon_z")

# Imported from the stream rather than restated, so a new exposure kind cannot
# be added to the spine and silently ignored here.
CONVERSION_KIND = "nudge_acted"
DELIVERY_KINDS = ("nudge_delivered", "nudge_opened", CONVERSION_KIND)


# ---------------------------------------------------------------------------
# Beta posterior arithmetic. Closed forms, so the tests assert against an
# independent numerical integration of the same integral rather than against a
# stored number.
# ---------------------------------------------------------------------------


def lbeta(a: float, b: float) -> float:
    """log B(a, b). Used everywhere below; the direct form overflows early."""
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def prob_b_beats_a(alpha_a: float, beta_a: float, alpha_b: float, beta_b: float) -> float:
    """
    P(theta_B > theta_A) for independent Beta posteriors, exactly.

    Miller's finite sum, valid when alpha_b is a positive integer, which it is
    whenever the prior parameters are integers and the data are counts:

        P = sum_{i=0}^{alpha_b - 1}
              B(alpha_a + i, beta_a + beta_b)
              / [ (beta_b + i) B(1 + i, beta_b) B(alpha_a, beta_a) ]

    Every term is computed in logs and summed with fsum, so a large conversion
    count does not lose the tail. When alpha_b is not an integer the finite sum
    does not exist and we fall back to quadrature, which is the same quantity by
    a different route.
    """
    for name, value in (
        ("alpha_a", alpha_a), ("beta_a", beta_a), ("alpha_b", alpha_b), ("beta_b", beta_b),
    ):
        if value <= 0:
            raise ValueError("Beta parameter " + name + " must be positive, got " + repr(value))

    if abs(alpha_b - round(alpha_b)) > 1e-12 or alpha_b > 2_000_000:
        return _prob_b_beats_a_quadrature(alpha_a, beta_a, alpha_b, beta_b)

    k = int(round(alpha_b))
    base = lbeta(alpha_a, beta_a)
    terms = []
    for i in range(k):
        log_term = (
            lbeta(alpha_a + i, beta_a + beta_b)
            - math.log(beta_b + i)
            - lbeta(1.0 + i, beta_b)
            - base
        )
        if log_term > -745.0:
            terms.append(math.exp(log_term))
    total = math.fsum(terms)
    return min(1.0, max(0.0, total))


def expected_loss_pair(
    alpha_a: float, beta_a: float, alpha_b: float, beta_b: float
) -> tuple[float, float]:
    """
    (loss of choosing A, loss of choosing B), in the metric's own units.

    loss_A = E[(theta_B - theta_A)^+]
           = m_B P(theta_B' > theta_A) - m_A P(theta_B > theta_A')

    where m_B = alpha_b / (alpha_b + beta_b), theta_B' ~ Beta(alpha_b + 1, beta_b)
    and theta_A' ~ Beta(alpha_a + 1, beta_a). This is Stucchio's closed form and
    it follows from E[theta 1{event}] = E[theta] P(event under the size-biased
    posterior), which for a Beta is again a Beta with alpha + 1.

    The two losses are NOT zero for identical posteriors. They are equal, and
    their difference is always E[theta_B] - E[theta_A].
    """
    mean_b = alpha_b / (alpha_b + beta_b)
    mean_a = alpha_a / (alpha_a + beta_a)
    loss_a = (
        mean_b * prob_b_beats_a(alpha_a, beta_a, alpha_b + 1.0, beta_b)
        - mean_a * prob_b_beats_a(alpha_a + 1.0, beta_a, alpha_b, beta_b)
    )
    loss_b = (
        mean_a * prob_b_beats_a(alpha_b, beta_b, alpha_a + 1.0, beta_a)
        - mean_b * prob_b_beats_a(alpha_b + 1.0, beta_b, alpha_a, beta_a)
    )
    return max(0.0, loss_a), max(0.0, loss_b)


def _gauss_legendre(n: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Nodes and weights on [-1, 1] by Newton iteration on the Legendre polynomial.

    Computed rather than tabulated so there is no typed-in table to mistype, and
    recomputed per call rather than cached, because a module-level cache is
    mutable module-level state and the purity lint would reject it. n is small.
    """
    nodes = []
    weights = []
    for i in range(1, n + 1):
        x = math.cos(math.pi * (i - 0.25) / (n + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, 0.0
            for j in range(1, n + 1):
                p0, p1 = ((2 * j - 1) * x * p0 - (j - 1) * p1) / j, p0
            dp = n * (x * p0 - p1) / (x * x - 1.0)
            dx = -p0 / dp
            x += dx
            if abs(dx) < 1e-15:
                break
        p0, p1 = 1.0, 0.0
        for j in range(1, n + 1):
            p0, p1 = ((2 * j - 1) * x * p0 - (j - 1) * p1) / j, p0
        dp = n * (x * p0 - p1) / (x * x - 1.0)
        nodes.append(x)
        weights.append(2.0 / ((1.0 - x * x) * dp * dp))
    return tuple(nodes), tuple(weights)


def _beta_pdf(x: float, a: float, b: float) -> float:
    if x <= 0.0 or x >= 1.0:
        return 0.0
    log_pdf = (a - 1.0) * math.log(x) + (b - 1.0) * math.log1p(-x) - lbeta(a, b)
    return math.exp(log_pdf) if log_pdf > -745.0 else 0.0


def _beta_cdf(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return betainc(a, b, x)


def _support(a: float, b: float, *, sds: float = 12.0) -> tuple[float, float]:
    """The interval outside which a Beta(a, b) carries no numerically useful mass."""
    mean = a / (a + b)
    var = a * b / ((a + b) ** 2 * (a + b + 1.0))
    sd = math.sqrt(var)
    return max(0.0, mean - sds * sd), min(1.0, mean + sds * sd)


def _integrate(f, lo: float, hi: float, *, nodes: int = 96) -> float:
    if hi <= lo:
        return 0.0
    xs, ws = _gauss_legendre(nodes)
    half = 0.5 * (hi - lo)
    mid = 0.5 * (hi + lo)
    return half * math.fsum(w * f(mid + half * x) for x, w in zip(xs, ws))


def _prob_b_beats_a_quadrature(
    alpha_a: float, beta_a: float, alpha_b: float, beta_b: float, *, nodes: int = 96
) -> float:
    lo, hi = _support(alpha_b, beta_b)
    return _integrate(
        lambda x: _beta_pdf(x, alpha_b, beta_b) * _beta_cdf(x, alpha_a, beta_a),
        lo, hi, nodes=nodes,
    )


def _quantile_of(cdf, lo: float, hi: float, q: float, *, iterations: int = 80) -> float:
    """Bisection on a monotone CDF. Deterministic, no seed, no starting guess."""
    a, b = lo, hi
    for _ in range(iterations):
        mid = 0.5 * (a + b)
        if cdf(mid) < q:
            a = mid
        else:
            b = mid
    return 0.5 * (a + b)


def relative_lift_quantiles(
    alpha_a: float, beta_a: float, alpha_b: float, beta_b: float, qs: Sequence[float]
) -> list[float]:
    """
    Quantiles of theta_B / theta_A - 1 under the two posteriors.

    P(theta_B / theta_A <= r) = integral pdf_A(x) F_B(r x) dx, evaluated by
    Gauss-Legendre over the numerically relevant support of A and inverted by
    bisection. No Monte Carlo, so no seed and no simulation error.
    """
    lo_a, hi_a = _support(alpha_a, beta_a)

    def cdf(r: float) -> float:
        if r <= 0.0:
            return 0.0
        return _integrate(
            lambda x: _beta_pdf(x, alpha_a, beta_a) * _beta_cdf(min(1.0, r * x), alpha_b, beta_b),
            lo_a, hi_a,
        )

    upper = 1.0
    while cdf(upper) < max(qs) and upper < 1e6:
        upper *= 2.0
    return [_quantile_of(cdf, 0.0, upper, q) - 1.0 for q in qs]


def difference_quantiles(
    alpha_a: float, beta_a: float, alpha_b: float, beta_b: float, qs: Sequence[float]
) -> list[float]:
    """Quantiles of theta_B - theta_A, by the same quadrature route."""
    lo_a, hi_a = _support(alpha_a, beta_a)

    def cdf(d: float) -> float:
        return _integrate(
            lambda x: _beta_pdf(x, alpha_a, beta_a) * _beta_cdf(x + d, alpha_b, beta_b),
            lo_a, hi_a,
        )

    return [_quantile_of(cdf, -1.0, 1.0, q) for q in qs]


# ---------------------------------------------------------------------------
# Reducing the exposure log to arm counts. This is arithmetic over atoms, not a
# fetch: the caller hands us rows and we count them, once per member.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArmSummary:
    """
    One arm of an experiment, deduplicated to one trial per member.

    A member nudged four times is one exposure, not four. Counting deliveries
    instead of members inflates n by the retry policy, which is the most common
    way an exposure log lies.
    """

    arm_ref: str
    exposures: int
    conversions: int
    members: frozenset[str] = frozenset()
    first_exposure: datetime | None = None
    last_exposure: datetime | None = None
    strata: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    early_exposures: int = 0
    early_conversions: int = 0
    delivered: int | None = None

    def __post_init__(self) -> None:
        if self.conversions > self.exposures:
            raise ValueError(
                "arm " + self.arm_ref + " has " + str(self.conversions) + " conversions from "
                + str(self.exposures) + " exposures; a member who acted was exposed, so an "
                "exposure log that says otherwise is incomplete rather than surprising"
            )


def _looks_like_events(arm: Any) -> bool:
    try:
        first = next(iter(arm))
    except (TypeError, StopIteration):
        return False
    return hasattr(first, "kind") or hasattr(first, "member_ref")


def summarise_arm(arm: Any, *, label: str = "arm") -> ArmSummary:
    """
    Accept the three shapes a caller honestly has, and refuse anything else.

    1. An `ArmSummary`, or any object carrying `exposures` and `conversions`.
    2. `(conversions, exposures)`, the shape a hand-written fixture has.
    3. An iterable of `ParticipationEvent` exposure rows, which is what the
       spine actually produces.
    """
    if isinstance(arm, ArmSummary):
        return arm
    if hasattr(arm, "exposures") and hasattr(arm, "conversions"):
        return ArmSummary(
            arm_ref=str(getattr(arm, "arm_ref", label)),
            exposures=int(arm.exposures),
            conversions=int(arm.conversions),
            members=frozenset(getattr(arm, "members", ()) or ()),
            first_exposure=getattr(arm, "first_exposure", None),
            last_exposure=getattr(arm, "last_exposure", None),
            strata=dict(getattr(arm, "strata", {}) or {}),
            early_exposures=int(getattr(arm, "early_exposures", 0) or 0),
            early_conversions=int(getattr(arm, "early_conversions", 0) or 0),
            delivered=getattr(arm, "delivered", None),
        )
    if isinstance(arm, (tuple, list)) and len(arm) == 2 and all(
        isinstance(v, (int, float)) for v in arm
    ):
        conversions, exposures = int(arm[0]), int(arm[1])
        return ArmSummary(arm_ref=label, exposures=exposures, conversions=conversions)
    if _looks_like_events(arm):
        return _summarise_events(arm, label=label)
    raise ValueError(
        "experiments.* takes an ArmSummary, a (conversions, exposures) pair or an iterable of "
        "exposure-log ParticipationEvent rows for " + label + "; got " + type(arm).__name__
    )


def _summarise_events(events, *, label: str) -> ArmSummary:
    seen: dict[str, datetime | None] = {}
    converted: set[str] = set()
    delivered: set[str] = set()
    strata: dict[str, dict[str, int]] = {}
    strata_seen: set[str] = set()
    arm_refs: set[str] = set()

    rows = []
    for event in events:
        kind = getattr(event, "kind", None)
        if kind not in EXPOSURE_KINDS:
            continue
        arm_ref = getattr(event, "arm_ref", None)
        if not arm_ref:
            raise ValueError(
                "exposure-log row of kind " + str(kind) + " carries no arm_ref, so it cannot be "
                "attributed to an arm; the stream atom forbids this and so does the service"
            )
        arm_refs.add(str(arm_ref))
        rows.append(event)

    if len(arm_refs) > 1:
        raise ValueError(
            "the rows passed as " + label + " mix arms " + ", ".join(sorted(arm_refs))
            + "; each argument is one arm, split them before calling"
        )

    for event in rows:
        member = str(getattr(event, "member_ref", ""))
        at = getattr(event, "at", None)
        if member not in seen:
            seen[member] = at
        else:
            known = seen[member]
            if at is not None and (known is None or at < known):
                seen[member] = at
        if getattr(event, "kind", None) == CONVERSION_KIND:
            converted.add(member)
        if getattr(event, "kind", None) in DELIVERY_KINDS:
            delivered.add(member)
        if member not in strata_seen:
            strata_seen.add(member)
            for key, value in (getattr(event, "strata", None) or {}).items():
                strata.setdefault(str(key), {})
                strata[str(key)][str(value)] = strata[str(key)].get(str(value), 0) + 1
            channel = getattr(event, "channel", None)
            if channel:
                strata.setdefault("channel", {})
                strata["channel"][str(channel)] = strata["channel"].get(str(channel), 0) + 1

    times = [t for t in seen.values() if t is not None]
    first = min(times) if times else None
    last = max(times) if times else None

    early_exposures = 0
    early_conversions = 0
    if first is not None and last is not None and last > first:
        cutoff = first + (last - first) / 4
        for member, at in seen.items():
            if at is not None and at <= cutoff:
                early_exposures += 1
                if member in converted:
                    early_conversions += 1

    return ArmSummary(
        arm_ref=(sorted(arm_refs)[0] if arm_refs else label),
        exposures=len(seen),
        conversions=len(converted),
        members=frozenset(seen),
        first_exposure=first,
        last_exposure=last,
        strata={k: dict(v) for k, v in strata.items()},
        early_exposures=early_exposures,
        early_conversions=early_conversions,
        delivered=len(delivered) if delivered else None,
    )


def _contingency_chi_square(table: Sequence[Sequence[float]]) -> tuple[float, int, float]:
    """Pearson chi-square on an r x c table. Returns (statistic, df, p)."""
    rows = len(table)
    cols = len(table[0]) if rows else 0
    total = math.fsum(math.fsum(row) for row in table)
    if total <= 0 or rows < 2 or cols < 2:
        return 0.0, 0, 1.0
    row_sums = [math.fsum(row) for row in table]
    col_sums = [math.fsum(table[r][c] for r in range(rows)) for c in range(cols)]
    stat = 0.0
    for r in range(rows):
        for c in range(cols):
            expected = row_sums[r] * col_sums[c] / total
            if expected > 0:
                stat += (table[r][c] - expected) ** 2 / expected
    df = (rows - 1) * (cols - 1)
    return stat, df, chi2_sf(stat, df)


def two_proportion_p(s1: int, n1: int, s2: int, n2: int) -> tuple[float, float]:
    """Pooled two-proportion z test. Returns (z, two-sided p)."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0
    p1, p2 = s1 / n1, s2 / n2
    pooled = (s1 + s2) / (n1 + n2)
    var = pooled * (1.0 - pooled) * (1.0 / n1 + 1.0 / n2)
    if var <= 0:
        return 0.0, 1.0
    z = (p2 - p1) / math.sqrt(var)
    return z, 2.0 * norm_sf(abs(z))


def _as_of_for(arms: Sequence[ArmSummary], as_of: datetime | None) -> datetime:
    if as_of is not None:
        return as_of
    times = [a.last_exposure for a in arms if a.last_exposure is not None]
    if times:
        return max(times)
    raise ValueError(
        "experiments.* cannot read a clock (spine rule S6). Pass as_of, or pass exposure rows "
        "carrying timestamps so the latest exposure can serve as it"
    )


def _balance_check(arm_a: ArmSummary, arm_b: ArmSummary) -> Check:
    features = sorted(set(arm_a.strata) & set(arm_b.strata))
    if not features:
        return Check(
            id="randomisation-balance",
            label="The arms are balanced on the covariates the exposure log carries",
            status="SKIPPED",
            detail=(
                "The exposure rows carry no strata, so balance cannot be measured. This "
                "comparison is being trusted as randomised on the caller's word rather than on "
                "evidence."
            ),
        )
    worst_p = 1.0
    worst_stat = 0.0
    worst_feature = ""
    for feature in features:
        values = sorted(set(arm_a.strata[feature]) | set(arm_b.strata[feature]))
        table = [
            [float(arm_a.strata[feature].get(v, 0)) for v in values],
            [float(arm_b.strata[feature].get(v, 0)) for v in values],
        ]
        stat, df, p = _contingency_chi_square(table)
        if df and p < worst_p:
            worst_p, worst_stat, worst_feature = p, stat, feature
    adjusted = min(1.0, worst_p * max(1, len(features)))
    failed = adjusted < BALANCE_ALPHA
    return Check(
        id="randomisation-balance",
        label="The arms are balanced on the covariates the exposure log carries",
        status="FAIL" if failed else "PASS",
        statistic=worst_stat,
        p_value=adjusted,
        blocking=failed,
        detail=(
            "The arms differ on " + worst_feature + " (chi-square " + "{:.2f}".format(worst_stat)
            + ", Bonferroni p = " + "{:.2g}".format(adjusted) + " over " + str(len(features))
            + " covariates). Assignment was therefore not random with respect to "
            + worst_feature + ", and the difference between the arms is confounded with it. No "
            "comparison is reported: this is an observational contrast, and a broken "
            "randomisation produces an answer that is confident and wrong."
        ) if failed else "",
    )


def _srm_check(arm_a: ArmSummary, arm_b: ArmSummary, split: tuple[float, float]) -> Check:
    n_a, n_b = arm_a.exposures, arm_b.exposures
    total = n_a + n_b
    expected_a = total * split[0]
    expected_b = total * split[1]
    stat = 0.0
    if expected_a > 0:
        stat += (n_a - expected_a) ** 2 / expected_a
    if expected_b > 0:
        stat += (n_b - expected_b) ** 2 / expected_b
    p = chi2_sf(stat, 1)
    failed = p < SRM_ALPHA
    return Check(
        id="sample-ratio-mismatch",
        label="Exposures per arm match the intended split",
        status="FAIL" if failed else "PASS",
        statistic=stat,
        p_value=p,
        blocking=failed,
        detail=(
            "The intended split was " + "{:.0%}".format(split[0]) + " / "
            + "{:.0%}".format(split[1]) + " but " + str(n_a) + " and " + str(n_b)
            + " exposures were recorded (chi-square " + "{:.2f}".format(stat) + ", p = "
            + "{:.2g}".format(p) + "). A sample ratio mismatch is a fault in the delivery "
            "pipeline, not a finding about the arms: members are missing from one side and the "
            "ones missing are not a random sample. Nothing is reported until it is explained."
        ) if failed else "",
    )


def _novelty_check(arm_a: ArmSummary, arm_b: ArmSummary) -> Check:
    if not arm_a.early_exposures or not arm_b.early_exposures:
        return Check(
            id="novelty-window",
            label="The effect is not concentrated in the first days of exposure",
            status="SKIPPED",
            detail="Exposure timestamps are not available, so the effect cannot be split by time.",
        )
    late_a = arm_a.exposures - arm_a.early_exposures
    late_b = arm_b.exposures - arm_b.early_exposures
    if late_a < 10 or late_b < 10:
        return Check(
            id="novelty-window",
            label="The effect is not concentrated in the first days of exposure",
            status="SKIPPED",
            detail="Too few exposures outside the first quarter of the window to compare against.",
        )
    early_effect = (
        arm_b.early_conversions / arm_b.early_exposures
        - arm_a.early_conversions / arm_a.early_exposures
    )
    late_effect = (
        (arm_b.conversions - arm_b.early_conversions) / late_b
        - (arm_a.conversions - arm_a.early_conversions) / late_a
    )
    gap = early_effect - late_effect
    concentrated = abs(early_effect) > 1e-12 and abs(gap) > 0.5 * abs(early_effect)
    return Check(
        id="novelty-window",
        label="The effect is not concentrated in the first days of exposure",
        status="WARN" if concentrated else "PASS",
        statistic=gap,
        detail=(
            "The measured difference is " + "{:+.1%}".format(early_effect) + " in the first "
            "quarter of the exposure window and " + "{:+.1%}".format(late_effect) + " after it. "
            "A novelty effect fades, and an average over the whole window will overstate what "
            "this nudge will do next month."
        ) if concentrated else "",
    )


def _contamination_check(arm_a: ArmSummary, arm_b: ArmSummary) -> Check:
    if not arm_a.members or not arm_b.members:
        return Check(
            id="no-contamination",
            label="No member appears in both arms",
            status="SKIPPED",
            detail="Member references are not available, so overlap cannot be measured.",
        )
    overlap = arm_a.members & arm_b.members
    return Check(
        id="no-contamination",
        label="No member appears in both arms",
        status="FAIL" if overlap else "PASS",
        statistic=float(len(overlap)),
        blocking=bool(overlap),
        detail=(
            str(len(overlap)) + " members were exposed to both arms. Their outcome cannot be "
            "attributed to either, so the contrast is between two overlapping groups rather "
            "than between two treatments. No comparison is reported."
        ) if overlap else "",
    )


def _peeking_check(stopping_rule: Any) -> Check:
    if stopping_rule is None:
        return Check(
            id="no-peeking",
            label="The declared stopping rule has fired",
            status="WARN",
            detail=(
                "No stopping rule was supplied with this comparison, so it is an interim look at "
                "a running experiment. Read it as such: the experiment is still running, and the "
                "arm ahead today is ahead partly by chance. experiments.sequential_stopping_rule "
                "answers whether it can be stopped safely."
            ),
        )
    fired = stopping_rule
    if isinstance(stopping_rule, Evidence):
        value = stopping_rule.value or {}
        fired = bool(value.get("stop")) if isinstance(value, Mapping) else False
    fired = bool(fired)
    return Check(
        id="no-peeking",
        label="The declared stopping rule has fired",
        status="PASS" if fired else "WARN",
        detail="" if fired else (
            "The declared stopping rule has not fired. This experiment is still running and this "
            "is an interim look, not a verdict."
        ),
    )


def _interval_kind_for(credible: float) -> str:
    if abs(credible - 0.95) < 1e-9:
        return "credible-95"
    if abs(credible - 0.89) < 1e-9:
        return "credible-89"
    raise ValueError(
        "docs/EVIDENCE_CONTRACT.md names credible-95 and credible-89 only; a "
        + repr(credible) + " interval has no declared kind and would render as one of those two"
    )


# ---------------------------------------------------------------------------
# The services
# ---------------------------------------------------------------------------


def beta_ab_test(
    arm_a,
    arm_b,
    *,
    prior=(1.0, 1.0),
    credible=0.95,
    split=(0.5, 0.5),
    as_of=None,
    stopping_rule=None,
) -> Evidence:
    """experiments.beta_ab_test. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "experiments.beta_ab_test"
    summary_a = summarise_arm(arm_a, label="arm_a")
    summary_b = summarise_arm(arm_b, label="arm_b")
    phash = params_hash(method, 1, {
        "prior": list(prior), "credible": credible, "split": list(split),
        "arm_a": summary_a.arm_ref, "arm_b": summary_b.arm_ref,
    })
    when = _as_of_for((summary_a, summary_b), as_of)
    kind = _interval_kind_for(credible)
    n = summary_a.exposures + summary_b.exposures

    if math.fsum(split) <= 0:
        raise ValueError("the declared split must be positive, got " + repr(split))
    normalised = (split[0] / math.fsum(split), split[1] / math.fsum(split))

    floors_met = (
        summary_a.exposures >= MIN_EXPOSURES_PER_ARM
        and summary_b.exposures >= MIN_EXPOSURES_PER_ARM
        and summary_a.conversions >= MIN_CONVERSIONS_PER_ARM
        and summary_b.conversions >= MIN_CONVERSIONS_PER_ARM
    )
    if not floors_met:
        return insufficient(
            method, n=n, as_of=when, params_hash=phash, unit="probability",
            empty_value={
                "p_b_beats_a": None, "lift": None, "lift_lo": None, "lift_hi": None,
                "posterior_a": None, "posterior_b": None,
                "n_a": summary_a.exposures, "n_b": summary_b.exposures,
            },
            caveats=(
                "Needs " + str(MIN_EXPOSURES_PER_ARM) + " exposures and "
                + str(MIN_CONVERSIONS_PER_ARM) + " conversions per arm; arm "
                + summary_a.arm_ref + " has " + str(summary_a.exposures) + " and "
                + str(summary_a.conversions) + ", arm " + summary_b.arm_ref + " has "
                + str(summary_b.exposures) + " and " + str(summary_b.conversions) + ".",
                "Below ten conversions the posterior is the prior wearing the data's coat: "
                "P(B beats A) would sit near 0.5 and look like a measurement of the nudge.",
            ),
        )

    alpha_a = prior[0] + summary_a.conversions
    beta_a = prior[1] + summary_a.exposures - summary_a.conversions
    alpha_b = prior[0] + summary_b.conversions
    beta_b = prior[1] + summary_b.exposures - summary_b.conversions

    p_b_beats_a = prob_b_beats_a(alpha_a, beta_a, alpha_b, beta_b)
    tail = (1.0 - credible) / 2.0
    lift_lo, lift, lift_hi = relative_lift_quantiles(
        alpha_a, beta_a, alpha_b, beta_b, (tail, 0.5, 1.0 - tail)
    )
    diff_lo, diff, diff_hi = difference_quantiles(
        alpha_a, beta_a, alpha_b, beta_b, (tail, 0.5, 1.0 - tail)
    )

    checks = (
        _balance_check(summary_a, summary_b),
        _srm_check(summary_a, summary_b, normalised),
        _contamination_check(summary_a, summary_b),
        _novelty_check(summary_a, summary_b),
        _peeking_check(stopping_rule),
    )
    blocked = any(c.status == "FAIL" and c.blocking for c in checks)

    value = {
        "p_b_beats_a": None if blocked else p_b_beats_a,
        "lift": None if blocked else lift,
        "lift_lo": None if blocked else lift_lo,
        "lift_hi": None if blocked else lift_hi,
        "absolute_difference": None if blocked else diff,
        "difference_lo": None if blocked else diff_lo,
        "difference_hi": None if blocked else diff_hi,
        "posterior_a": {
            "arm_ref": summary_a.arm_ref, "alpha": alpha_a, "beta": beta_a,
            "mean": alpha_a / (alpha_a + beta_a),
            "conversions": summary_a.conversions, "exposures": summary_a.exposures,
        },
        "posterior_b": {
            "arm_ref": summary_b.arm_ref, "alpha": alpha_b, "beta": beta_b,
            "mean": alpha_b / (alpha_b + beta_b),
            "conversions": summary_b.conversions, "exposures": summary_b.exposures,
        },
        "n_a": summary_a.exposures,
        "n_b": summary_b.exposures,
    }

    caveats = [
        "P(B beats A) = " + "{:.3f}".format(p_b_beats_a) + " is a POSTERIOR PROBABILITY, not a "
        "p-value and not a significance level. It is the probability, given these exposures and "
        "this prior, that arm " + summary_b.arm_ref + " really does convert better than arm "
        + summary_a.arm_ref + ".",
        "The interval is a " + "{:.0%}".format(credible) + " credible interval on the RELATIVE "
        "lift, from the posteriors themselves rather than from a normal approximation.",
    ]
    if blocked:
        caveats.insert(0, (
            "No comparison is reported: " + "; ".join(
                c.detail for c in checks if c.status == "FAIL" and c.blocking
            )
        ))

    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=when,
        interval=None if blocked else (lift_lo, lift_hi),
        interval_kind=kind,
        assumptions=(
            "Assignment to arms was random, at the declared "
            + "{:.0%}".format(normalised[0]) + " / " + "{:.0%}".format(normalised[1]) + " split.",
            "One trial per member: repeated nudges to the same member are one exposure.",
            "The conversion definition and the metric were fixed before the data were seen.",
        ),
        checks=checks,
        caveats=tuple(caveats),
        unit="probability",
        params_hash=phash,
    )


def expected_loss(arm_a, arm_b, *, prior=(1.0, 1.0), threshold=None, as_of=None) -> Evidence:
    """experiments.expected_loss. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "experiments.expected_loss"
    summary_a = summarise_arm(arm_a, label="arm_a")
    summary_b = summarise_arm(arm_b, label="arm_b")
    phash = params_hash(method, 1, {
        "prior": list(prior), "threshold": threshold,
        "arm_a": summary_a.arm_ref, "arm_b": summary_b.arm_ref,
    })
    when = _as_of_for((summary_a, summary_b), as_of)
    n = summary_a.exposures + summary_b.exposures

    floors_met = (
        summary_a.exposures >= MIN_EXPOSURES_PER_ARM
        and summary_b.exposures >= MIN_EXPOSURES_PER_ARM
        and summary_a.conversions >= MIN_CONVERSIONS_PER_ARM
        and summary_b.conversions >= MIN_CONVERSIONS_PER_ARM
    )
    if not floors_met:
        return insufficient(
            method, n=n, as_of=when, params_hash=phash, unit="conversion rate",
            empty_value={"loss_a": None, "loss_b": None, "recommend": None},
            caveats=(
                "Inherits the A/B test's floor: " + str(MIN_EXPOSURES_PER_ARM) + " exposures and "
                + str(MIN_CONVERSIONS_PER_ARM) + " conversions per arm.",
            ),
        )

    alpha_a = prior[0] + summary_a.conversions
    beta_a = prior[1] + summary_a.exposures - summary_a.conversions
    alpha_b = prior[0] + summary_b.conversions
    beta_b = prior[1] + summary_b.exposures - summary_b.conversions

    loss_a, loss_b = expected_loss_pair(alpha_a, beta_a, alpha_b, beta_b)
    recommend = summary_a.arm_ref if loss_a <= loss_b else summary_b.arm_ref
    smallest = min(loss_a, loss_b)

    if threshold is None:
        threshold_check = Check(
            id="threshold-of-caring",
            label="The remaining expected loss is below the committee's threshold of caring",
            status="SKIPPED",
            statistic=smallest,
            detail=(
                "No threshold was declared, so this envelope says how much is at stake and "
                "nothing about whether that is enough to stop. The threshold belongs to the "
                "committee and is set in the metric's units, before the loss is seen."
            ),
        )
    else:
        below = smallest <= threshold
        threshold_check = Check(
            id="threshold-of-caring",
            label="The remaining expected loss is below the committee's threshold of caring",
            status="PASS" if below else "WARN",
            statistic=smallest,
            detail="" if below else (
                "Choosing " + recommend + " now risks losing "
                + "{:.4f}".format(smallest) + " in conversion rate, against a declared threshold "
                "of " + "{:.4f}".format(threshold) + ". The experiment has not yet bought enough "
                "certainty to be worth stopping."
            ),
        )

    identity = Check(
        id="loss-difference-identity",
        label="loss(A) - loss(B) equals the difference of the posterior means",
        status="PASS",
        statistic=(loss_a - loss_b),
        detail="",
    )
    expected_gap = (alpha_b / (alpha_b + beta_b)) - (alpha_a / (alpha_a + beta_a))
    if abs((loss_a - loss_b) - expected_gap) > 1e-9:
        identity = Check(
            id="loss-difference-identity",
            label="loss(A) - loss(B) equals the difference of the posterior means",
            status="FAIL",
            statistic=(loss_a - loss_b) - expected_gap,
            blocking=True,
            detail=(
                "The two losses do not satisfy loss(A) - loss(B) = E[theta_B] - E[theta_A], "
                "which is an identity rather than an approximation, so the closed form has been "
                "evaluated wrongly and no loss is reported."
            ),
        )

    blocked = identity.status == "FAIL"
    return Evidence(
        value={
            "loss_a": None if blocked else loss_a,
            "loss_b": None if blocked else loss_b,
            "recommend": None if blocked else recommend,
            "smallest_loss": None if blocked else smallest,
            "threshold": threshold,
            "arm_a": summary_a.arm_ref,
            "arm_b": summary_b.arm_ref,
            "n_a": summary_a.exposures,
            "n_b": summary_b.exposures,
        },
        n=n,
        method=method,
        as_of=when,
        interval=None,
        interval_kind="none",
        assumptions=(
            "The posteriors are the ones from the declared test.",
            "The threshold of caring is in the metric's units and was set before the loss was "
            "seen.",
        ),
        checks=(threshold_check, identity),
        caveats=(
            "Expected loss is the average size of the mistake, in conversion-rate points, if you "
            "pick that arm now and it turns out to be the worse one. Choosing " + recommend
            + " risks " + "{:.4f}".format(smallest) + ".",
            "It is NOT zero when the arms are identical. Two identical posteriors leave a real "
            "expected regret, equal on both sides, because either arm might still be the better "
            "one. What is exactly zero at that point is the DIFFERENCE between the two losses.",
        ),
        unit="conversion rate",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# The always-valid sequential test.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Trial:
    """One member's exposure and its outcome, in exposure order."""

    arm: str
    outcome: float
    at: datetime | None = None


def reduce_trials(event_stream_ordered) -> tuple[tuple[Trial, ...], int]:
    """
    The exposure log, or a hand-written fixture, as one ordered trial per member.

    Returns the trials and the count excluded for being exposed to both arms. A
    member in both arms is dropped rather than assigned to one, and the count is
    surfaced as `n_excluded`, because an invisible exclusion is indistinguishable
    from a lost row.
    """
    rows = list(event_stream_ordered)
    if not rows:
        return (), 0
    first = rows[0]

    if isinstance(first, Trial):
        return tuple(rows), 0
    if hasattr(first, "arm") and hasattr(first, "outcome"):
        return tuple(
            Trial(str(r.arm), float(r.outcome), getattr(r, "at", None)) for r in rows
        ), 0
    if isinstance(first, (tuple, list)):
        out = []
        for r in rows:
            at = r[2] if len(r) > 2 else None
            out.append(Trial(str(r[0]), float(r[1]), at))
        return tuple(out), 0

    arm_of: dict[str, str] = {}
    first_at: dict[str, Any] = {}
    acted: set[str] = set()
    conflicted: set[str] = set()
    for event in rows:
        kind = getattr(event, "kind", None)
        if kind not in EXPOSURE_KINDS:
            continue
        member = str(getattr(event, "member_ref", ""))
        arm_ref = getattr(event, "arm_ref", None)
        if not arm_ref:
            raise ValueError(
                "exposure-log row of kind " + str(kind) + " carries no arm_ref"
            )
        arm_ref = str(arm_ref)
        at = getattr(event, "at", None)
        if member in arm_of and arm_of[member] != arm_ref:
            conflicted.add(member)
        known = first_at.get(member)
        if member not in arm_of or (at is not None and (known is None or at < known)):
            arm_of[member] = arm_ref
            first_at[member] = at
        if kind == CONVERSION_KIND:
            acted.add(member)

    members = [m for m in arm_of if m not in conflicted]
    members.sort(key=lambda m: (first_at.get(m) is None, first_at.get(m), m))
    trials = tuple(
        Trial(arm_of[m], 1.0 if m in acted else 0.0, first_at.get(m)) for m in members
    )
    return trials, len(conflicted)


def mixture_rho(sigma_squared: float, target_n: int, alpha: float) -> float:
    """
    The mixture variance that makes the boundary tightest near `target_n`.

    The normal-mixture boundary on the running sum is

        b(t) = sqrt( (V_t + rho) * log( (V_t + rho) / (rho * alpha^2) ) )

    with V_t = t * sigma^2. Its ratio to the fixed-sample boundary z * sigma *
    sqrt(t) is a function of u = V_t / rho alone, minimised where

        u = 2 log(1/alpha) + log(1 + u),

    a fixed point that converges in a handful of iterations. Setting
    rho = target_n * sigma^2 / u* therefore puts the tightest point of the
    always-valid boundary at the sample size the experiment is designed for.
    """
    c = 2.0 * math.log(1.0 / alpha)
    u = c
    for _ in range(200):
        nxt = c + math.log1p(u)
        if abs(nxt - u) < 1e-14:
            u = nxt
            break
        u = nxt
    return max(1e-12, target_n * sigma_squared / u)


def mixture_boundary(v: float, rho: float, alpha: float) -> float:
    """The two-sided crossing boundary on the running sum, from Ville's inequality."""
    total = v + rho
    inner = total / (rho * alpha * alpha)
    if inner <= 1.0:
        return float("inf")
    return math.sqrt(total * math.log(inner))


def _mixture_e_value(s: float, v: float, rho: float) -> float:
    """
    Robbins' normal mixture: E_t = sqrt(rho / (V_t + rho)) exp(S_t^2 / (2(V_t + rho))).

    A nonnegative supermartingale with E_0 = 1 under the null whenever the
    increments are conditionally mean zero and sub-Gaussian with variance proxy
    sigma^2, since it is the N(0, 1/rho) mixture of exp(lambda S_t - lambda^2
    V_t / 2). Ville then bounds P(sup_t E_t >= 1/alpha) by alpha, at every
    stopping time simultaneously, which is what makes daily looks safe.
    """
    total = v + rho
    return math.sqrt(rho / total) * math.exp(min(700.0, s * s / (2.0 * total)))


def run_eprocess(
    trials: Sequence[Trial],
    *,
    arms: tuple[str, str],
    alpha: float = 0.05,
    split: tuple[float, float] = (0.5, 0.5),
    target_n: int = 500,
    variance: str = "hoeffding",
) -> dict:
    """
    Stream the trials through the e-process and report where, if ever, it crossed.

    The increment is the Horvitz-Thompson contrast

        psi_i = y_i * ( 1{arm_i = B} / pi_B  -  1{arm_i = A} / pi_A ),

    which has expectation p_B - p_A under the declared randomisation, and hence
    exactly zero under the null. It is bounded in [-1/pi_A, 1/pi_B], so by
    Hoeffding's lemma it is sub-Gaussian with variance proxy
    ((1/pi_A + 1/pi_B) / 2)^2. That proxy is conservative, which is the direction
    that keeps the guarantee honest and the price is power.

    `variance="empirical"` swaps the worst-case proxy for the running sample
    variance of psi. That is the Johari, Koomen, Pekelis and Walsh mSPRT: tighter,
    and valid asymptotically rather than at every finite n. It is offered because
    a method nobody can afford to run is not a safeguard, and its weaker
    guarantee is stated in the envelope.

    Exposed as a public function because the false-positive-rate experiment in
    the tests must run it thousands of times, and running it through the full
    Evidence path would be measuring the check assembly rather than the
    mathematics.
    """
    if variance not in ("hoeffding", "empirical"):
        raise ValueError("variance must be 'hoeffding' or 'empirical', got " + repr(variance))
    pi_a, pi_b = split[0] / math.fsum(split), split[1] / math.fsum(split)
    if pi_a <= 0 or pi_b <= 0:
        raise ValueError("both assignment probabilities must be positive, got " + repr(split))
    proxy = ((1.0 / pi_a + 1.0 / pi_b) / 2.0) ** 2
    rho = mixture_rho(proxy, target_n, alpha)

    s = 0.0
    sum_sq = 0.0
    t = 0
    max_e = 0.0
    crossed_at = None
    e_value = 1.0
    v = 0.0
    for trial in trials:
        if trial.arm == arms[1]:
            psi = trial.outcome / pi_b
        elif trial.arm == arms[0]:
            psi = -trial.outcome / pi_a
        else:
            continue
        t += 1
        s += psi
        sum_sq += psi * psi
        if variance == "hoeffding":
            v = t * proxy
        else:
            # The running second moment about zero, which under the null is the
            # variance. Floored so the first few observations cannot make the
            # boundary vanish.
            v = max(sum_sq, t * 1e-9)
        e_value = _mixture_e_value(s, v, rho)
        if e_value > max_e:
            max_e = e_value
        if crossed_at is None and e_value >= 1.0 / alpha:
            crossed_at = t

    boundary = mixture_boundary(v, rho, alpha) if t else float("inf")
    delta = s / t if t else 0.0
    half_width = boundary / t if t else float("inf")
    return {
        "e_value": e_value,
        "max_e_value": max_e,
        "crossed_at": crossed_at,
        "n": t,
        "sum": s,
        "v": v,
        "rho": rho,
        "sigma_squared": proxy,
        "effect": delta,
        "ci_lo": delta - half_width,
        "ci_hi": delta + half_width,
        "threshold": 1.0 / alpha,
    }


def naive_z_crossing(
    trials: Sequence[Trial],
    *,
    arms: tuple[str, str],
    alpha: float = 0.05,
    peek_every: int = 25,
    min_per_arm: int = 30,
) -> int | None:
    """
    The bug, implemented on purpose: stop the first time a fixed-horizon two
    proportion z test reads p < alpha.

    This is not a service and nothing returns it as Evidence. It exists so the
    test suite can measure what peeking actually costs on the identical fixture
    the always-valid method is measured on. A guarantee nobody has measured the
    alternative to is a claim, not a result.
    """
    s_a = n_a = s_b = n_b = 0
    for index, trial in enumerate(trials, start=1):
        if trial.arm == arms[0]:
            n_a += 1
            s_a += int(trial.outcome > 0)
        elif trial.arm == arms[1]:
            n_b += 1
            s_b += int(trial.outcome > 0)
        else:
            continue
        if index % peek_every:
            continue
        if n_a < min_per_arm or n_b < min_per_arm:
            continue
        _, p = two_proportion_p(s_a, n_a, s_b, n_b)
        if p < alpha:
            return index
    return None


def sequential_stopping_rule(
    event_stream_ordered,
    *,
    alpha=0.05,
    method="evalue",
    split=(0.5, 0.5),
    target_n=500,
    arms=None,
    as_of=None,
) -> Evidence:
    """experiments.sequential_stopping_rule. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method_id = "experiments.sequential_stopping_rule"
    if method not in SEQUENTIAL_METHODS:
        raise ValueError(
            "experiments.sequential_stopping_rule knows " + ", ".join(SEQUENTIAL_METHODS)
            + "; got " + repr(method)
        )
    trials, excluded = reduce_trials(event_stream_ordered)
    phash = params_hash(method_id, 1, {
        "alpha": alpha, "method": method, "split": list(split), "target_n": target_n,
        "arms": list(arms) if arms else None,
    })

    seen_arms = []
    for trial in trials:
        if trial.arm not in seen_arms:
            seen_arms.append(trial.arm)
    if arms is None:
        arms_pair = tuple(sorted(seen_arms))
    else:
        arms_pair = tuple(arms)
    if len(arms_pair) != 2:
        raise ValueError(
            "experiments.sequential_stopping_rule compares exactly two arms; this stream has "
            + str(len(seen_arms)) + " (" + ", ".join(sorted(seen_arms)) + "). Name the two to "
            "compare, or use bandits.thompson_sampling_policy for more than two"
        )

    times = [t.at for t in trials if t.at is not None]
    when = as_of if as_of is not None else (max(times) if times else None)
    if when is None:
        raise ValueError(
            "experiments.sequential_stopping_rule cannot read a clock (spine rule S6). Pass "
            "as_of, or pass trials carrying timestamps"
        )

    n_a = sum(1 for t in trials if t.arm == arms_pair[0])
    n_b = sum(1 for t in trials if t.arm == arms_pair[1])
    n = n_a + n_b

    exposure_complete = Check(
        id="exposure-log-complete",
        label="Every trial has an exposure and both arms are represented",
        status="PASS" if (n_a and n_b) else "FAIL",
        statistic=float(n),
        blocking=not (n_a and n_b),
        detail=(
            "One arm has no exposures at all (" + arms_pair[0] + ": " + str(n_a) + ", "
            + arms_pair[1] + ": " + str(n_b) + "). There is nothing to compare, so nothing is "
            "reported."
        ) if not (n_a and n_b) else "",
    )

    if method == "fixed_horizon_z":
        crossed = naive_z_crossing(trials, arms=arms_pair, alpha=alpha)
        validity = Check(
            id="optional-stopping-valid",
            label="The method in use stays valid when the experiment is watched repeatedly",
            status="FAIL",
            blocking=True,
            detail=(
                "A fixed-horizon two-proportion z test was requested for a stream that is being "
                "monitored sequentially. Its 5% error rate is the error rate of ONE look at a "
                "pre-declared sample size. Consulted at every peek it fires far more often than "
                "that under no effect at all, so no stopping decision is reported. Use "
                "method='evalue', which is valid at every stopping time simultaneously."
            ),
        )
        return Evidence(
            value={
                "stop": None, "at_n": None, "e_value": None, "threshold": None,
                "decision": "not interpretable",
                "would_have_stopped_at": crossed,
                "arm_a": arms_pair[0], "arm_b": arms_pair[1], "n_a": n_a, "n_b": n_b,
            },
            n=n,
            method=method_id,
            as_of=when,
            interval=None,
            interval_kind="none",
            assumptions=("A fixed horizon declared in advance, which a monitored stream does not "
                         "have.",),
            checks=(validity, exposure_complete),
            caveats=(
                "This envelope reports no stopping decision on purpose. The naive rule would "
                "have stopped at n = " + str(crossed) + "." if crossed is not None else
                "This envelope reports no stopping decision on purpose.",
            ),
            n_excluded=excluded,
            exclusion_reason=(
                "members exposed to both arms, whose outcome belongs to neither"
            ) if excluded else "",
            unit="e-value",
            params_hash=phash,
        )

    variance = "hoeffding" if method == "evalue" else "empirical"
    result = run_eprocess(
        trials, arms=arms_pair, alpha=alpha, split=split, target_n=target_n, variance=variance,
    )

    stop = result["crossed_at"] is not None
    direction = arms_pair[1] if result["effect"] > 0 else arms_pair[0]
    if stop:
        decision = "stop: " + direction + " is ahead by more than chance explains"
    else:
        decision = "keep running: the evidence has not crossed the boundary"

    validity = Check(
        id="optional-stopping-valid",
        label="The method in use stays valid when the experiment is watched repeatedly",
        status="PASS" if method == "evalue" else "WARN",
        statistic=result["max_e_value"],
        detail="" if method == "evalue" else (
            "The mSPRT substitutes the observed variance for a worst-case bound. That makes the "
            "boundary tighter and the guarantee asymptotic rather than exact at every finite n. "
            "Early in an experiment, prefer method='evalue', whose bound is a theorem at every "
            "sample size."
        ),
    )

    maturation = Check(
        id="outcome-maturation",
        label="The most recently exposed members have had time to respond",
        status="SKIPPED",
        detail=(
            "Exposure times are not available, so it cannot be checked whether the last members "
            "exposed have had time to act."
        ),
    )
    if times and len(times) > 20:
        ordered = sorted(times)
        span = (ordered[-1] - ordered[0]).total_seconds()
        # The last tenth of the WINDOW, not the last tenth of the rows: the
        # question is how many members were nudged too recently to have replied,
        # and a quantile of the rows answers that with 10% by construction.
        recent_cut = ordered[0] + (ordered[-1] - ordered[0]) * 0.9
        recent_share = sum(1 for t in times if t >= recent_cut) / len(times)
        immature = span > 0 and recent_share > 0.25
        maturation = Check(
            id="outcome-maturation",
            label="The most recently exposed members have had time to respond",
            status="WARN" if immature else "PASS",
            statistic=recent_share,
            detail=(
                "{:.0%}".format(recent_share) + " of exposures fall in the last tenth of the "
                "window. Their non-conversions are right censored, not zeroes: those members may "
                "still act, so the measured rates are biased downward for whichever arm was "
                "delivered last."
            ) if immature else "",
        )

    blocked = not (n_a and n_b)
    return Evidence(
        value={
            "stop": None if blocked else stop,
            "at_n": result["crossed_at"],
            "e_value": None if blocked else result["e_value"],
            "max_e_value": None if blocked else result["max_e_value"],
            "threshold": result["threshold"],
            "decision": "not interpretable" if blocked else decision,
            "effect": None if blocked else result["effect"],
            "confidence_sequence": None if blocked else [result["ci_lo"], result["ci_hi"]],
            "arm_a": arms_pair[0],
            "arm_b": arms_pair[1],
            "n_a": n_a,
            "n_b": n_b,
            "method": method,
        },
        n=n,
        method=method_id,
        as_of=when,
        interval=None,
        interval_kind="none",
        assumptions=(
            "Assignment probabilities are the declared "
            + "{:.0%}".format(split[0] / math.fsum(split)) + " / "
            + "{:.0%}".format(split[1] / math.fsum(split)) + " and are independent of the "
            "outcome.",
            "Observations arrive in exposure order.",
            "The metric and the arm set did not change mid-flight; either resets the process.",
        ),
        checks=(validity, exposure_complete, maturation),
        caveats=(
            "The e-value is " + "{:.3g}".format(result["e_value"]) + " against a threshold of "
            + "{:.0f}".format(result["threshold"]) + ". It may be watched as often as you like: "
            "Ville's inequality bounds the chance of it ever crossing, under no real difference, "
            "by " + "{:.0%}".format(alpha) + " over the whole life of the experiment.",
            "The confidence sequence " + "[{:+.4f}, {:+.4f}]".format(result["ci_lo"], result["ci_hi"])
            + " covers the true difference at ALL times at once, which is a stronger claim than a "
            "fixed-sample interval makes and is why it is wider. That width is the price of being "
            "allowed to look.",
        ),
        n_excluded=excluded,
        exclusion_reason=(
            "members exposed to both arms, whose outcome belongs to neither"
        ) if excluded else "",
        unit="e-value",
        params_hash=phash,
    )


__all__ = [
    "ALWAYS_VALID_METHODS",
    "ArmSummary",
    "MIN_CONVERSIONS_PER_ARM",
    "MIN_EXPOSURES_PER_ARM",
    "SEQUENTIAL_METHODS",
    "Trial",
    "beta_ab_test",
    "difference_quantiles",
    "expected_loss",
    "expected_loss_pair",
    "lbeta",
    "mixture_boundary",
    "mixture_rho",
    "naive_z_crossing",
    "prob_b_beats_a",
    "reduce_trials",
    "relative_lift_quantiles",
    "run_eprocess",
    "sequential_stopping_rule",
    "summarise_arm",
]
