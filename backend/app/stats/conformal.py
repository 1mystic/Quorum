"""
Distribution-free predictive intervals.

`conformal.survival_eta_bound` is the resident-facing ETA and is the hardest
thing in Pack 3 to get right: split conformal calibrated on resolved requests is
calibrated on the fast ones, so exchangeability fails in the direction that
makes the ETA look good, which is the worst possible direction for the one
number a resident will trust and quote.

**Which bound carries the guarantee, and why.** Under right censoring the data
is informative about short waits and systematically missing about long ones. A
distribution-free UPPER bound on the waiting time is therefore not attainable:
beyond the censoring horizon all anyone can honestly say is "longer than this".
Conformalized survival analysis (Candes, Lei and Ren 2023) gives a valid LOWER
predictive bound, and that is what this module guarantees. The upper and point
figures are computed from a censoring-aware Kaplan-Meier estimate, are reported
alongside, and are labelled as model-based rather than guaranteed. A resident is
entitled to know which half of the promise is underwritten by a theorem.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
import random
from typing import Any, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import mean, percentile

MIN_CALIBRATION = 100
MIN_SPELLS = 200
MIN_EVENTS = 100
MIN_PER_CLASS = 100

# The mathematical floor: with fewer than ceil(1/alpha) - 1 points the conformal
# quantile is +infinity and the interval is the whole line. The guarantee still
# holds there, which is the point worth stating: the guarantee and the
# usefulness have different thresholds.
def theoretical_floor(alpha: float) -> int:
    return int(math.ceil(1.0 / alpha)) - 1


# A tuple of pairs rather than a dict, because a module-level dict is mutable
# state and the purity lint refuses it. It is right to: a caller that mutated
# this would silently change the meaning of every interval kind on the wire.
_INTERVAL_KINDS: tuple[tuple[float, str], ...] = ((0.1, "conformal-90"), (0.05, "conformal-95"))


def _interval_kind(alpha: float) -> str:
    for level, kind in _INTERVAL_KINDS:
        if abs(alpha - level) < 1e-12:
            return kind
    raise ValueError(
        "alpha must be 0.1 or 0.05: the Evidence contract has no interval kind for "
        + repr(alpha) + ", and relabelling one that exists would misdescribe the guarantee"
    )


# ---------------------------------------------------------------------------
# The conformal quantile
# ---------------------------------------------------------------------------


def conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """
    The `ceil((n + 1) * (1 - alpha))`-th smallest score.

    The `+1` is the whole theorem. It is what makes the finite-sample guarantee
    `1 - alpha <= coverage <= 1 - alpha + 1/(n + 1)` hold for any exchangeable
    distribution, and dropping it (taking the plain empirical quantile) produces
    an interval that under-covers by exactly one observation's worth, which is
    invisible at large n and fatal at small n.
    """
    n = len(scores)
    if n == 0:
        return math.inf
    k = int(math.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return math.inf
    return sorted(scores)[k - 1]


def weighted_conformal_quantile(scores: Sequence[float], weights: Sequence[float],
                                alpha: float) -> float:
    """
    The weighted conformal quantile of Tibshirani et al., which is what makes
    the censoring correction work.

    The test point contributes a point mass at +infinity with its own weight, so
    the quantile is the smallest score whose cumulative normalised weight
    reaches `1 - alpha`. With equal weights this reduces exactly to
    `conformal_quantile`, which is asserted in the tests.
    """
    if len(scores) != len(weights):
        raise ValueError("scores and weights differ in length")
    if not scores:
        return math.inf
    total = math.fsum(weights) + max(weights)      # the test point's mass at infinity
    if total <= 0.0:
        return math.inf
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    cumulative = 0.0
    for i in order:
        cumulative += weights[i]
        if cumulative / total >= 1.0 - alpha:
            return scores[i]
    return math.inf


def _ks_two_sample(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov statistic and its asymptotic p-value."""
    if not a or not b:
        return 0.0, 1.0
    combined = sorted(set(list(a) + list(b)))
    sorted_a = sorted(a)
    sorted_b = sorted(b)
    n_a, n_b = len(a), len(b)
    statistic = 0.0
    i = j = 0
    for value in combined:
        while i < n_a and sorted_a[i] <= value:
            i += 1
        while j < n_b and sorted_b[j] <= value:
            j += 1
        statistic = max(statistic, abs(i / n_a - j / n_b))
    effective = math.sqrt(n_a * n_b / (n_a + n_b))
    lam = statistic * effective
    if lam <= 0.0:
        return statistic, 1.0
    p = 2.0 * math.fsum(
        (-1.0) ** (k - 1) * math.exp(-2.0 * k * k * lam * lam) for k in range(1, 101)
    )
    return statistic, max(0.0, min(1.0, p))


def _drift_check(residuals: Sequence[float]) -> Check:
    """
    Exchangeability is the only assumption conformal prediction makes, so it is
    the only one worth testing hard. A residual distribution that differs
    between the first and second half of the calibration window is drifting, and
    the coverage guarantee goes with it.
    """
    half = len(residuals) // 2
    if half < 10:
        return Check(
            id="exchangeability-time-drift",
            label="The calibration residuals look the same early and late in the window",
            status="SKIPPED",
            detail="too few calibration points to compare the two halves",
        )
    statistic, p_value = _ks_two_sample(residuals[:half], residuals[half:])
    if p_value < 0.01:
        status = "FAIL"
    elif p_value < 0.05:
        status = "WARN"
    else:
        status = "PASS"
    return Check(
        id="exchangeability-time-drift",
        label="The calibration residuals look the same early and late in the window",
        status=status,
        statistic=statistic,
        p_value=p_value,
        detail="" if status == "PASS" else (
            "the residual distribution shifted inside the calibration window, so "
            "exchangeability is doubtful and the coverage guarantee weakens with it"
        ),
    )


# ---------------------------------------------------------------------------
# Kaplan-Meier, used for the censoring weights and the model-based bounds
# ---------------------------------------------------------------------------


def kaplan_meier(durations: Sequence[float], observed: Sequence[bool]
                 ) -> tuple[list[float], list[float]]:
    """
    Survival curve as (times, S(t)). Used here for two distinct jobs: the
    censoring distribution (which supplies the conformal weights) and the
    event distribution (which supplies the model-based upper bound).
    """
    points = sorted(zip(durations, observed), key=lambda p: (p[0], not p[1]))
    n = len(points)
    times: list[float] = []
    survival: list[float] = []
    current = 1.0
    at_risk = n
    i = 0
    while i < n:
        t = points[i][0]
        deaths = 0
        tied = 0
        while i < n and points[i][0] == t:
            if points[i][1]:
                deaths += 1
            tied += 1
            i += 1
        if deaths and at_risk > 0:
            current *= (1.0 - deaths / at_risk)
            times.append(t)
            survival.append(current)
        at_risk -= tied
    return times, survival


def survival_at(times: Sequence[float], survival: Sequence[float], t: float) -> float:
    value = 1.0
    for time, s in zip(times, survival):
        if time <= t:
            value = s
        else:
            break
    return value


def km_quantile(times: Sequence[float], survival: Sequence[float], q: float) -> float:
    """The smallest t with S(t) <= 1 - q; infinity if the curve never gets there."""
    target = 1.0 - q
    for time, s in zip(times, survival):
        if s <= target:
            return time
    return math.inf


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def split_conformal_interval(calibration_residuals, point_prediction, as_of, *, alpha=0.1
                             ) -> Evidence:
    """conformal.split_conformal_interval. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "conformal.split_conformal_interval"
    kind = _interval_kind(alpha)
    residuals = [abs(float(r)) for r in calibration_residuals]
    n = len(residuals)
    phash = params_hash(method, 1, {"alpha": alpha, "n": n})
    floor = theoretical_floor(alpha)
    if n < MIN_CALIBRATION:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=None, params_hash=phash,
            caveats=(
                "the guarantee holds from " + str(floor) + " calibration points but the "
                "interval is the whole range there; " + str(MIN_CALIBRATION) + " is the "
                "practical floor and this has " + str(n) + ". The guarantee and the usefulness "
                "have different thresholds, which is worth stating plainly",
            ),
        )
    q = conformal_quantile(residuals, alpha)
    point = float(point_prediction)
    signed = [float(r) for r in calibration_residuals]
    checks = [
        _drift_check(signed),
        Check(
            id="calibration-size",
            label="Enough calibration points for the interval to be informative",
            status="PASS",
            statistic=float(n),
        ),
    ]
    if math.isinf(q):
        return insufficient(
            method, n=n, as_of=as_of, empty_value=None, params_hash=phash,
            caveats=("the conformal quantile is unbounded at this alpha and sample size",),
        )
    return Evidence(
        value=point,
        n=n,
        method=method,
        as_of=as_of,
        interval=(point - q, point + q),
        interval_kind=kind,
        assumptions=(
            "Exchangeability of the calibration set and the new point. Not independence, not "
            "normality, not a correct model. Exchangeability, and nothing else.",
        ),
        checks=tuple(checks),
        caveats=(
            "coverage is MARGINAL: across many predictions at least "
            + ("%.0f%%" % (100 * (1 - alpha))) + " of true values fall inside. It does not "
            "promise that rate for any particular category, which is what conformal.mondrian_eta "
            "provides at a cost in width",
            "the guarantee is finite-sample and two-sided: coverage is at least "
            + ("%.2f" % (1 - alpha)) + " and at most "
            + ("%.4f" % (1 - alpha + 1.0 / (n + 1))),
        ),
        params_hash=phash,
    )


def _spell_arrays(spells: Sequence[Any]) -> tuple[list[float], list[bool]]:
    durations = []
    observed = []
    for spell in spells:
        hours = getattr(spell, "duration_hours", None)
        if hours is None:
            continue
        durations.append(float(hours) / 24.0)
        observed.append(bool(getattr(spell, "event_observed", False)))
    return durations, observed


def survival_eta_bound(spells, window, *, covariates, seed, alpha=0.1) -> Evidence:
    """conformal.survival_eta_bound. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "conformal.survival_eta_bound"
    kind = _interval_kind(alpha)
    durations, observed = _spell_arrays(spells)
    n = len(durations)
    events = sum(1 for o in observed if o)
    censored = n - events
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "covariates": list(covariates or ()), "alpha": alpha, "seed": seed,
    })
    as_of = getattr(window, "end", None)
    if n < MIN_SPELLS or events < MIN_EVENTS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash, n_censored=censored,
            caveats=(
                "needs " + str(MIN_SPELLS) + " spells with " + str(MIN_EVENTS)
                + " observed resolutions, has " + str(n) + " with " + str(events)
                + "; the request page shows the category's Kaplan-Meier curve instead",
            ),
        )

    # Split deterministically into a model half and a calibration half.
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    split = n // 2
    train_index = order[:split]
    calibration_index = order[split:]

    # The censoring distribution, estimated by reversing the event indicator.
    # The weights depend on it, which is why its fit is a blocking check.
    censor_times, censor_survival = kaplan_meier(
        [durations[i] for i in train_index], [not observed[i] for i in train_index]
    )
    # A threshold beyond which the data cannot speak: the censoring-aware
    # horizon. Candes, Lei and Ren work with T truncated at c0 for exactly this
    # reason, and c0 must be a level the censoring model still supports.
    c0 = percentile(sorted([durations[i] for i in train_index]), 0.60)
    censoring_support = survival_at(censor_times, censor_survival, c0)

    # The model: the alpha-quantile of the truncated waiting time on the
    # training half, which is the lower bound before conformalisation.
    train_durations = [durations[i] for i in train_index]
    train_observed = [observed[i] for i in train_index]
    event_times, event_survival = kaplan_meier(train_durations, train_observed)
    model_lower = km_quantile(event_times, event_survival, alpha)
    if not math.isfinite(model_lower):
        model_lower = min(train_durations)

    # Weighted conformal scores on the calibration half. Only points whose
    # censoring time reaches c0 are usable, and each is weighted by the inverse
    # probability of that happening, which restores validity.
    scores: list[float] = []
    weights: list[float] = []
    dropped = 0
    for i in calibration_index:
        truncated = min(durations[i], c0)
        if not observed[i] and durations[i] < c0:
            dropped += 1          # censored before c0: the score is not computable
            continue
        probability = max(survival_at(censor_times, censor_survival, truncated), 1e-3)
        scores.append(model_lower - truncated)     # positive when the bound was too high
        weights.append(1.0 / probability)
    usable = len(scores)
    if usable < MIN_CALIBRATION:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash, n_censored=censored,
            caveats=(
                "only " + str(usable) + " calibration points survive the censoring correction "
                "and " + str(MIN_CALIBRATION) + " are needed; no ETA is shown to a resident",
            ),
        )
    q = weighted_conformal_quantile(scores, weights, alpha)
    lower_days = model_lower - q if math.isfinite(q) else 0.0
    lower_days = max(0.0, lower_days)

    # The model-based companions, labelled as such: only the lower bound is
    # underwritten by the coverage theorem.
    full_times, full_survival = kaplan_meier(durations, observed)
    point_days = km_quantile(full_times, full_survival, 0.5)
    upper_days = km_quantile(full_times, full_survival, 1.0 - alpha)
    if not math.isfinite(point_days):
        point_days = max(durations)
    if not math.isfinite(upper_days):
        upper_days = max(durations)

    # The coverage backtest: does the bound hold on this tenant's own history?
    held_out = [i for i in calibration_index if observed[i]]
    covered = sum(1 for i in held_out if durations[i] >= lower_days)
    empirical = covered / len(held_out) if held_out else 0.0
    coverage_floor = 1.0 - alpha - 0.05

    censoring_ok = censoring_support > 0.05
    checks = [
        Check(
            id="censoring-model-fit",
            label="The censoring model still has support at the truncation horizon",
            status="PASS" if censoring_ok else "FAIL",
            statistic=censoring_support,
            blocking=not censoring_ok,
            detail="" if censoring_ok else
            "almost nothing remains uncensored at the truncation horizon, so the inverse "
            "probability weights are unstable and no ETA is shown; the request page shows the "
            "category's Kaplan-Meier curve instead",
        ),
        Check(
            id="censoring-independent-given-covariates",
            label="Censored and observed requests look alike once the weights are applied",
            status="PASS" if dropped < usable else "WARN",
            statistic=float(dropped),
            detail="" if dropped < usable else
            "more calibration points were dropped for early censoring than were kept, so the "
            "weighting is carrying a great deal of the estimate",
        ),
        Check(
            id="coverage-backtest",
            label="The bound actually held on this community's past requests",
            status="PASS" if empirical >= coverage_floor else "FAIL",
            statistic=empirical,
            blocking=empirical < coverage_floor,
            detail="" if empirical >= coverage_floor else
            "the lower bound held for only " + ("%.0f%%" % (100 * empirical)) + " of past "
            "requests against a floor of " + ("%.0f%%" % (100 * coverage_floor)) + "; the "
            "guarantee is theoretical and this checks it held here, so no ETA is shown",
        ),
        _drift_check([durations[i] for i in sorted(calibration_index)]),
    ]
    blocked = any(c.status == "FAIL" and c.blocking for c in checks)
    value = {} if blocked else {
        "lower_days": lower_days,
        "upper_days": upper_days,
        "point_days": point_days,
        "coverage_target": 1.0 - alpha,
        "truncation_horizon_days": c0,
        "calibration_n": usable,
        "empirical_coverage": empirical,
    }
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None if blocked else (lower_days, upper_days),
        interval_kind="none" if blocked else kind,
        assumptions=(
            "Censoring is independent of the resolution time given the covariates.",
            "The censoring model is well calibrated, since the weights depend on it.",
            "Exchangeability of requests within the calibration window.",
        ),
        checks=tuple(checks),
        caveats=(
            "only the LOWER bound carries the distribution-free guarantee. Under right "
            "censoring the data is informative about short waits and systematically missing "
            "about long ones, so no distribution-free upper bound exists; the upper and point "
            "figures come from the censoring-aware Kaplan-Meier estimate and are model-based",
            "the bound is deliberately conservative: it will more often be too wide than too "
            "narrow, and a resident is entitled to know which direction the promise errs in",
            str(censored) + " of " + str(n) + " requests were still open and were censored at "
            "the window boundary, never dropped (spine rule C1)",
        ),
        unit="days",
        n_censored=censored,
        params_hash=phash,
    )


def naive_resolved_only_upper_bound(spells, *, alpha=0.1) -> float:
    """
    The mistake, implemented so it can be measured.

    This is what `WHERE resolved_at IS NOT NULL` produces: the 1 - alpha
    quantile of the RESOLVED subset, which is exactly the fast requests. It is
    not exported as a service and exists only so the test suite can demonstrate
    that it under-covers on the same fixture where the corrected bound does not.
    """
    resolved = [float(s.duration_hours) / 24.0 for s in spells
                if getattr(s, "event_observed", False)]
    if not resolved:
        return 0.0
    return percentile(sorted(resolved), 1.0 - alpha)


def mondrian_eta(spells, window, *, seed, taxonomy="category", alpha=0.1) -> Evidence:
    """conformal.mondrian_eta. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "conformal.mondrian_eta"
    kind = _interval_kind(alpha)
    as_of = getattr(window, "end", None)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "taxonomy": taxonomy, "alpha": alpha, "seed": seed,
    })
    if taxonomy not in ("category", "priority", "location_ref"):
        raise ValueError(
            "taxonomy must be 'category', 'priority' or 'location_ref', got " + repr(taxonomy)
        )
    classes: dict[str, list[Any]] = {}
    n = 0
    censored = 0
    for spell in spells:
        if getattr(spell, "duration_hours", None) is None:
            continue
        n += 1
        if not getattr(spell, "event_observed", False):
            censored += 1
        key = getattr(spell, taxonomy, None) or "unclassified"
        classes.setdefault(str(key), []).append(spell)
    if n < MIN_SPELLS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash, n_censored=censored,
            caveats=("needs " + str(MIN_SPELLS) + " spells, has " + str(n),),
        )

    # The marginal fallback, computed once over everything.
    all_durations, all_observed = _spell_arrays(spells)
    marginal_times, marginal_survival = kaplan_meier(all_durations, all_observed)
    marginal_lower = km_quantile(marginal_times, marginal_survival, alpha)
    if not math.isfinite(marginal_lower):
        marginal_lower = 0.0

    rows = []
    fallbacks = 0
    for key in sorted(classes):
        members = classes[key]
        durations, observed = _spell_arrays(members)
        usable = len(durations)
        if usable < MIN_PER_CLASS:
            fallbacks += 1
            rows.append({
                "class": key,
                "n": usable,
                "lower_days": max(0.0, marginal_lower),
                "coverage_target": 1.0 - alpha,
                "fallback": True,
                "lo": max(0.0, marginal_lower),
                "hi": max(all_durations) if all_durations else 0.0,
            })
            continue
        times, survival = kaplan_meier(durations, observed)
        class_lower = km_quantile(times, survival, alpha)
        if not math.isfinite(class_lower):
            class_lower = min(durations)
        # Class-conditional conformal correction on the class's own points.
        scores = [class_lower - d for d in durations]
        q = conformal_quantile(scores, alpha)
        lower = max(0.0, class_lower - q) if math.isfinite(q) else 0.0
        upper = km_quantile(times, survival, 1.0 - alpha)
        if not math.isfinite(upper):
            upper = max(durations)
        rows.append({
            "class": key,
            "n": usable,
            "lower_days": lower,
            "upper_days": upper,
            "coverage_target": 1.0 - alpha,
            "fallback": False,
            "lo": lower,
            "hi": upper,
        })
    every_class_fell_back = fallbacks == len(rows)
    checks = [
        Check(
            id="classes-populated",
            label="Each class has enough history for a promise of its own",
            status="PASS" if fallbacks == 0 else "WARN",
            statistic=float(fallbacks),
            detail="" if fallbacks == 0 else
            str(fallbacks) + " class(es) fell back to the marginal interval, disclosed per row; "
            "a class below " + str(MIN_PER_CLASS) + " calibration points cannot support a "
            "class-conditional promise",
        ),
        Check(
            id="taxonomy-not-too-fine",
            label="The taxonomy is coarse enough for class-conditional coverage to mean anything",
            status="FAIL" if every_class_fell_back else "PASS",
            statistic=float(len(rows)),
            blocking=every_class_fell_back,
            detail="" if not every_class_fell_back else
            "every class fell back to the marginal interval, so this is marginal conformal with "
            "extra steps; use conformal.survival_eta_bound instead and say so",
        ),
    ]
    return Evidence(
        value=[] if every_class_fell_back else rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none" if every_class_fell_back else kind,
        assumptions=(
            "Exchangeability within each class of the declared taxonomy.",
            "At least " + str(MIN_PER_CLASS) + " calibration points per class, or the class "
            "falls back to the marginal interval with the fallback disclosed per row.",
        ),
        checks=tuple(checks),
        caveats=(
            "coverage holds WITHIN each class, which is what a resident actually cares about, "
            "at the cost of a wider interval than the marginal version",
            "as with the marginal ETA, only the lower bound carries the guarantee",
        ),
        unit="days",
        n_censored=censored,
        params_hash=phash,
    )


__all__ = [
    "conformal_quantile",
    "kaplan_meier",
    "km_quantile",
    "mondrian_eta",
    "naive_resolved_only_upper_bound",
    "split_conformal_interval",
    "survival_at",
    "survival_eta_bound",
    "theoretical_floor",
    "weighted_conformal_quantile",
]
