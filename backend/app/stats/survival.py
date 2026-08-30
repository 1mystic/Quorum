"""
Time-to-event over request_flow and member_lifecycle.

Every competing community dashboard computes average resolution time over closed
tickets only. That number is not slightly wrong, it is biased in a known direction,
and the size of the bias grows with the backlog. This module reports the correct
figure and shows the naive one next to it (survival.naive_vs_km_gap).

Spine rules C1 to C10 in app/stats/streams/request.py are normative here.

**The time scale.** Every estimator here works on age since the request opened,
not on time under observation. A spell that was already 6 days old when the
window opened and resolved 2 days later enters the risk set at day 6 and has its
event at day 8, so `entry = at_risk_from - opened_at` and `exit = entry +
duration`. Rule C3 requires the delayed-entry `(entry, exit]` risk set precisely
so that those 6 days are neither dropped nor counted as if the request were new.

**Suppression.** When a blocking check fails, the returned envelope carries the
shaped-but-empty value, not the number. The UI already refuses to render a value
in the `not_interpretable` state; emptying it here means a mis-wired client
cannot print it either.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import (
    chi2_sf,
    inverse,
    mean,
    norm_ppf,
    solve,
    t_two_sided_p,
    variance,
)

HOURS_PER_DAY = 24.0

MIN_EVENTS_KM = 30
MIN_EVENTS_PER_GROUP = 10
MIN_EVENTS_PER_COVARIATE = 10
MIN_AT_RISK_AT_HORIZON = 10
TAIL_AT_RISK_FLOOR = 5

COMPETING_WARN_SHARE = 0.05
COMPETING_FAIL_SHARE = 0.15
INTERVAL_CENSORING_FAIL_SHARE = 0.20


# ---------------------------------------------------------------------------
# Internal representation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    """One spell reduced to the three numbers an estimator needs, plus its keys."""

    entry: float          # age in days at which it entered the risk set (rule C3)
    exit: float           # age in days at the terminal event or at censoring
    event: bool           # True only for the cause under analysis
    outcome: str | None
    censoring: str
    left_truncated: bool
    ref: str
    keys: Mapping[str, Any]


def _z(alpha: float) -> float:
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1), got " + repr(alpha))
    return norm_ppf(1.0 - alpha / 2.0)


def _spell_keys(spell: Any) -> dict[str, Any]:
    """Everything a stratification, grouping or covariate check may key on."""
    keys: dict[str, Any] = {}
    for name in (
        "category", "subcategory", "priority", "channel", "location_ref",
        "group_ref", "assignee_ref", "outcome", "n_reassignments",
        "reopened_count", "duplicate_count", "left_truncated",
    ):
        if hasattr(spell, name):
            keys[name] = getattr(spell, name)
    covariates = getattr(spell, "covariates", None) or {}
    for name, value in covariates.items():
        keys[name] = value
    strata = getattr(spell, "strata_at_entry", None) or {}
    for name, value in strata.items():
        keys[name] = value
    return keys


def _duration_days(spell: Any, clock: str) -> tuple[float, bool]:
    """
    Returns (duration in days, whether the requested clock was available).

    Rule C8: the wall clock is the default because the resident experiences the
    wall clock. `clock="active"` is honoured only where the reducer filled
    `duration_active_hours`; where it did not, the service falls back to wall
    and says so in a caveat rather than silently reporting a different quantity.
    """
    if clock not in ("wall", "active"):
        raise ValueError("clock must be 'wall' or 'active', got " + repr(clock))
    if clock == "active":
        active = getattr(spell, "duration_active_hours", None)
        if active is None:
            return spell.duration_hours / HOURS_PER_DAY, False
        return active / HOURS_PER_DAY, True
    return spell.duration_hours / HOURS_PER_DAY, True


def _entry_days(spell: Any) -> float:
    at_risk_from = getattr(spell, "at_risk_from", None)
    opened_at = getattr(spell, "opened_at", None) or getattr(spell, "entered_at", None)
    if at_risk_from is None or opened_at is None:
        return 0.0
    return max(0.0, (at_risk_from - opened_at).total_seconds() / 86400.0)


def _request_rows(
    spells: Sequence[Any],
    *,
    clock: str = "wall",
    event_causes: tuple[str, ...] = ("resolved",),
) -> tuple[list[_Row], int, int]:
    """
    RequestSpell[] -> rows. Returns (rows, n_excluded, n_clock_fallbacks).

    Rule C1 in code: nothing is filtered on a terminal timestamp. The only
    exclusion is rule C7, a request merged into another, which is not a
    duplicate observation of the same process but the same request counted
    twice.
    """
    rows: list[_Row] = []
    excluded = 0
    fallbacks = 0
    for spell in spells:
        if getattr(spell, "outcome", None) == "merged":
            excluded += 1
            continue
        days, honoured = _duration_days(spell, clock)
        if not honoured:
            fallbacks += 1
        entry = _entry_days(spell)
        observed = bool(spell.event_observed) and (spell.outcome in event_causes)
        censoring = getattr(spell, "censoring", "none")
        if censoring == "interval":
            # Rule C4: never impute a midpoint. The honest right-censoring
            # reduction is at the lower end of the bracket.
            lo = getattr(spell, "interval_lo_hours", None)
            if lo is not None:
                days = lo / HOURS_PER_DAY
            observed = False
        rows.append(
            _Row(
                entry=entry,
                exit=entry + max(0.0, days),
                event=observed,
                outcome=getattr(spell, "outcome", None),
                censoring=censoring,
                left_truncated=bool(getattr(spell, "left_truncated", False)),
                ref=getattr(spell, "request_ref", ""),
                keys=_spell_keys(spell),
            )
        )
    return rows, excluded, fallbacks


def _member_rows(spells: Sequence[Any]) -> list[_Row]:
    rows: list[_Row] = []
    for spell in spells:
        entry = _entry_days(spell)
        rows.append(
            _Row(
                entry=entry,
                exit=entry + max(0.0, float(spell.duration_days)),
                event=bool(spell.event_observed),
                outcome=getattr(spell, "exit_kind", None),
                censoring="none" if spell.event_observed else "administrative",
                left_truncated=bool(getattr(spell, "left_truncated", False)),
                ref=getattr(spell, "member_ref", ""),
                keys=_spell_keys(spell),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# The estimator
# ---------------------------------------------------------------------------


def _at_risk(rows: Sequence[_Row], t: float) -> int:
    """
    The delayed-entry risk set {i : entry_i < t <= exit_i} (rule C3).

    The one special case is t = 0: a spell that opened and resolved inside the
    same instant must still count, so an untruncated row is at risk there.
    """
    if t <= 0.0:
        return sum(1 for r in rows if r.entry <= 0.0 <= r.exit)
    return sum(1 for r in rows if r.entry < t <= r.exit)


def _km_fit(rows: Sequence[_Row], alpha: float = 0.05) -> dict[str, list[float]]:
    """
    Kaplan-Meier with Greenwood variance and R's default log-transformed band.

    The `at_risk` array is returned inside the curve rather than as a parallel
    per-point n, settling the question docs/EVIDENCE_CONTRACT.md left open: it
    is intrinsic to the curve.
    """
    z = _z(alpha)
    event_times = sorted({r.exit for r in rows if r.event})
    out: dict[str, list[float]] = {
        "t_days": [], "survival": [], "lo": [], "hi": [],
        "at_risk": [], "events": [], "censored": [],
    }
    surv = 1.0
    greenwood = 0.0
    previous = -math.inf
    for t in event_times:
        n_risk = _at_risk(rows, t)
        if n_risk <= 0:
            continue
        d = sum(1 for r in rows if r.event and r.exit == t)
        censored_here = sum(
            1 for r in rows if not r.event and previous < r.exit < t
        ) if previous > -math.inf else sum(1 for r in rows if not r.event and r.exit < t)
        surv *= (1.0 - d / n_risk)
        if n_risk > d:
            greenwood += d / (n_risk * (n_risk - d))
        se_log = math.sqrt(greenwood)
        if surv > 0.0 and math.isfinite(se_log):
            lo = surv * math.exp(-z * se_log)
            hi = min(1.0, surv * math.exp(z * se_log))
        else:
            lo, hi = 0.0, min(1.0, surv)
        out["t_days"].append(t)
        out["survival"].append(surv)
        out["lo"].append(max(0.0, lo))
        out["hi"].append(hi)
        out["at_risk"].append(n_risk)
        out["events"].append(d)
        out["censored"].append(censored_here)
        previous = t
    return out


def _curve_value_at(curve: Mapping[str, Sequence[float]], key: str, t: float) -> float:
    """Right-continuous step lookup: the value in force at time t."""
    value = 1.0
    for i, ti in enumerate(curve["t_days"]):
        if ti <= t:
            value = curve[key][i]
        else:
            break
    return value


def _first_crossing(times: Sequence[float], values: Sequence[float], q: float) -> float | None:
    """The first time a decreasing step curve is at or below q."""
    for t, v in zip(times, values):
        if v <= q:
            return t
    return None


def _last_stable_time(curve: Mapping[str, Sequence[float]]) -> float | None:
    stable = [t for t, n in zip(curve["t_days"], curve["at_risk"]) if n >= TAIL_AT_RISK_FLOOR]
    return stable[-1] if stable else None


# ---------------------------------------------------------------------------
# The checks. Measured, never asserted (Evidence contract, Check docstring).
# ---------------------------------------------------------------------------


def _two_sample_p(values_a: Sequence[float], values_b: Sequence[float]) -> float:
    """Welch's t-test, two-sided. Returns 1.0 when either side is degenerate."""
    if len(values_a) < 3 or len(values_b) < 3:
        return 1.0
    try:
        va, vb = variance(values_a), variance(values_b)
    except ValueError:
        return 1.0
    na, nb = len(values_a), len(values_b)
    se2 = va / na + vb / nb
    if se2 <= 0.0:
        return 1.0
    t = (mean(values_a) - mean(values_b)) / math.sqrt(se2)
    df_num = se2 ** 2
    df_den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    df = df_num / df_den if df_den > 0.0 else float(na + nb - 2)
    return t_two_sided_p(t, max(1.0, df))


def _contingency_p(labels_a: Sequence[Any], labels_b: Sequence[Any]) -> float:
    """Chi-square test of independence on a 2 x k table."""
    levels = sorted({str(v) for v in labels_a} | {str(v) for v in labels_b})
    if len(levels) < 2:
        return 1.0
    rows = [[sum(1 for v in labels_a if str(v) == lv) for lv in levels],
            [sum(1 for v in labels_b if str(v) == lv) for lv in levels]]
    total = sum(sum(r) for r in rows)
    if total == 0:
        return 1.0
    row_sums = [sum(r) for r in rows]
    col_sums = [sum(rows[i][j] for i in range(2)) for j in range(len(levels))]
    stat = 0.0
    for i in range(2):
        for j in range(len(levels)):
            expected = row_sums[i] * col_sums[j] / total
            if expected <= 0.0:
                continue
            stat += (rows[i][j] - expected) ** 2 / expected
    df = len(levels) - 1
    return chi2_sf(stat, df) if df >= 1 else 1.0


def _check_censoring_informative(rows: Sequence[_Row]) -> Check:
    """
    Rule C9. Compares the covariate distribution of censored against observed
    spells, one test per covariate, Bonferroni corrected. An admin bulk-closing
    stale tickets shows up here and nowhere else.
    """
    observed = [r for r in rows if r.event]
    censored = [r for r in rows if not r.event]
    names = sorted({k for r in rows for k in r.keys})
    names = [n for n in names if n not in ("outcome",)]
    if len(observed) < 3 or len(censored) < 3 or not names:
        return Check(
            id="censoring-informative",
            label="Censoring is unrelated to how long a request would have taken",
            status="SKIPPED",
            detail="too few spells on one side of the comparison to test rule C9",
        )
    worst_p = 1.0
    worst_name = ""
    worst_direction = ""
    tested = 0
    for name in names:
        a_raw = [r.keys.get(name) for r in observed if r.keys.get(name) is not None]
        b_raw = [r.keys.get(name) for r in censored if r.keys.get(name) is not None]
        if len(a_raw) < 3 or len(b_raw) < 3:
            continue
        numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in a_raw + b_raw)
        tested += 1
        if numeric:
            p = _two_sample_p([float(v) for v in a_raw], [float(v) for v in b_raw])
            direction = "higher" if mean([float(v) for v in b_raw]) > mean([float(v) for v in a_raw]) else "lower"
        else:
            p = _contingency_p(a_raw, b_raw)
            direction = "differently distributed"
        if p < worst_p:
            worst_p, worst_name, worst_direction = p, name, direction
    if tested == 0:
        return Check(
            id="censoring-informative",
            label="Censoring is unrelated to how long a request would have taken",
            status="SKIPPED",
            detail="no covariate had enough observations on both sides to test rule C9",
        )
    adjusted = min(1.0, worst_p * tested)
    if adjusted < 0.05:
        return Check(
            id="censoring-informative",
            label="Censoring is unrelated to how long a request would have taken",
            status="WARN",
            statistic=adjusted,
            p_value=adjusted,
            detail=(
                "still-open requests differ from resolved ones on '" + worst_name
                + "' (" + worst_direction + " among the censored, Bonferroni adjusted p="
                + format(adjusted, ".4f") + "). Kaplan-Meier assumes they do not, so the curve "
                "is optimistic in the direction of that difference (spine rule C9)."
            ),
        )
    return Check(
        id="censoring-informative",
        label="Censoring is unrelated to how long a request would have taken",
        status="PASS",
        statistic=adjusted,
        p_value=adjusted,
        detail="no covariate separates censored from observed spells after correction",
    )


def _check_competing_risks(rows: Sequence[_Row]) -> Check:
    """Rule C5. escalated and withdrawn are not neutral censoring."""
    terminals = [r for r in rows if r.outcome in ("resolved", "escalated", "withdrawn")]
    if not terminals:
        return Check(
            id="competing-risks-material",
            label="Few requests exit by escalation or withdrawal",
            status="SKIPPED",
            detail="no terminal events in the window",
        )
    competing = sum(1 for r in terminals if r.outcome in ("escalated", "withdrawn"))
    share = competing / len(terminals)
    if share > COMPETING_FAIL_SHARE:
        return Check(
            id="competing-risks-material",
            label="Few requests exit by escalation or withdrawal",
            status="FAIL",
            statistic=share,
            blocking=True,
            detail=(
                format(share * 100.0, ".0f") + "% of terminal events are escalations or "
                "withdrawals. A request that was withdrawn will never resolve, so treating it "
                "as censored overstates resolution. Read survival.competing_risks_cif instead, "
                "which is the correct estimator here (spine rule C5)."
            ),
        )
    if share > COMPETING_WARN_SHARE:
        return Check(
            id="competing-risks-material",
            label="Few requests exit by escalation or withdrawal",
            status="WARN",
            statistic=share,
            detail=(
                format(share * 100.0, ".0f") + "% of terminals are escalations or withdrawals. "
                "This curve answers 'how long if nothing else intervenes'; the cumulative "
                "incidence function answers the question about the real world."
            ),
        )
    return Check(
        id="competing-risks-material",
        label="Few requests exit by escalation or withdrawal",
        status="PASS",
        statistic=share,
    )


def _check_interval_censoring(rows: Sequence[_Row]) -> Check:
    """Rule C4. There is no honest fallback here without a Turnbull estimator."""
    if not rows:
        return Check(
            id="interval-censoring-share", label="Terminal timestamps are exact, not bracketed",
            status="SKIPPED", detail="no spells",
        )
    share = sum(1 for r in rows if r.censoring == "interval") / len(rows)
    if share > INTERVAL_CENSORING_FAIL_SHARE:
        return Check(
            id="interval-censoring-share",
            label="Terminal timestamps are exact, not bracketed",
            status="FAIL",
            statistic=share,
            blocking=True,
            detail=(
                format(share * 100.0, ".0f") + "% of resolution timestamps are only bracketed, "
                "usually a batch import. Rule C4 forbids imputing a midpoint and there is no "
                "honest curve without a Turnbull estimator, so no figure is shown."
            ),
        )
    status = "WARN" if share > 0.0 else "PASS"
    return Check(
        id="interval-censoring-share",
        label="Terminal timestamps are exact, not bracketed",
        status=status,
        statistic=share,
        detail=(
            "bracketed terminals are treated as censored at the earliest possible time, never "
            "imputed to the middle of the bracket (rule C4)"
        ) if share > 0.0 else "",
    )


def _check_left_truncation(rows: Sequence[_Row]) -> Check:
    if not rows:
        return Check(id="left-truncation-share", label="Delayed entry is accounted for",
                     status="SKIPPED", detail="no spells")
    share = sum(1 for r in rows if r.left_truncated) / len(rows)
    return Check(
        id="left-truncation-share",
        label="Delayed entry is accounted for",
        status="PASS",
        statistic=share,
        detail=(
            format(share * 100.0, ".0f") + "% of spells were already open when the window "
            "started and enter the risk set at their age then, not at zero (rule C3). A high "
            "share means the window is short relative to the process."
        ),
    )


def _check_tail_instability(curve: Mapping[str, Sequence[float]]) -> Check:
    times = curve["t_days"]
    if not times:
        return Check(id="tail-instability", label="The tail of the curve rests on enough requests",
                     status="SKIPPED", detail="no event times")
    last_stable = _last_stable_time(curve)
    unstable = sum(1 for n in curve["at_risk"] if n < TAIL_AT_RISK_FLOOR)
    share = unstable / len(times)
    if unstable:
        return Check(
            id="tail-instability",
            label="The tail of the curve rests on enough requests",
            status="WARN",
            statistic=last_stable if last_stable is not None else 0.0,
            detail=(
                "beyond day " + format(last_stable or 0.0, ".1f") + " fewer than "
                + str(TAIL_AT_RISK_FLOOR) + " requests are still at risk, so the curve is "
                "truncated there rather than drawn as if it were estimated."
            ),
        )
    return Check(
        id="tail-instability",
        label="The tail of the curve rests on enough requests",
        status="PASS",
        statistic=share,
    )


def _truncate_at(curve: dict[str, list[float]], t_max: float | None) -> dict[str, list[float]]:
    if t_max is None:
        return {k: [] for k in curve}
    keep = [i for i, t in enumerate(curve["t_days"]) if t <= t_max]
    return {k: [v[i] for i in keep] for k, v in curve.items()}


def _empty_curve() -> dict[str, list[float]]:
    return {"t_days": [], "survival": [], "lo": [], "hi": [], "at_risk": [], "events": [], "censored": []}


def _blocked(checks: Sequence[Check]) -> bool:
    return any(c.status == "FAIL" and c.blocking for c in checks)


def _window_params(window: Any) -> dict[str, Any]:
    return {
        "window_start": getattr(window, "start", None),
        "window_end": getattr(window, "end", None),
        "complete_through": getattr(window, "complete_through", None),
    }


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def _curve_service(
    rows: Sequence[_Row],
    window: Any,
    *,
    method: str,
    unit: str,
    version: int,
    extra_params: Mapping[str, Any],
    n_excluded: int = 0,
    exclusion_reason: str = "",
    extra_caveats: tuple[str, ...] = (),
    min_events: int = MIN_EVENTS_KM,
    alpha: float = 0.05,
) -> Evidence:
    """The shared body of every Kaplan-Meier curve in this module."""
    phash = params_hash(method, version, {**_window_params(window), **extra_params})
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)
    n_events = n - n_censored
    as_of = window.end

    if n_events < min_events:
        return insufficient(
            method,
            n=n,
            as_of=as_of,
            empty_value=_empty_curve(),
            unit=unit,
            n_censored=n_censored,
            params_hash=phash,
            caveats=(
                "needs " + str(min_events) + " observed events, has " + str(n_events)
                + " (" + str(n_censored) + " of " + str(n) + " spells are still open and are "
                "censored, not dropped)",
            ),
        )

    curve = _km_fit(rows, alpha)
    checks = [
        _check_competing_risks(rows),
        _check_interval_censoring(rows),
        _check_censoring_informative(rows),
        _check_left_truncation(rows),
        _check_tail_instability(curve),
    ]
    caveats = list(extra_caveats)
    tail = next(c for c in checks if c.id == "tail-instability")
    if tail.status == "WARN":
        curve = _truncate_at(curve, _last_stable_time(curve))
        caveats.append(tail.detail)
    informative = next(c for c in checks if c.id == "censoring-informative")
    if informative.status == "WARN":
        caveats.append(informative.detail)
    if _blocked(checks):
        blocking = next(c for c in checks if c.status == "FAIL" and c.blocking)
        curve = _empty_curve()
        caveats.append(blocking.detail)

    return Evidence(
        value=curve,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="greenwood-95",
        assumptions=(
            "Open spells are censored at the observation boundary, never dropped (spine rule C1).",
            "Censoring is unrelated to how long a spell would have taken.",
            "Spells are exchangeable within a stratum.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_censored=n_censored,
        n_excluded=n_excluded,
        exclusion_reason=exclusion_reason,
        unit=unit,
        params_hash=phash,
    )


def km_resolution_curve(spells, window, *, stratify_by=None, clock="wall", alpha=0.05) -> Evidence:
    """survival.km_resolution_curve. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    rows, excluded, fallbacks = _request_rows(spells, clock=clock)
    if stratify_by is not None:
        rows = [r for r in rows if r.keys.get(stratify_by) is not None]
    caveats: list[str] = []
    if fallbacks:
        caveats.append(
            str(fallbacks) + " spells have no active-clock duration, so the wall clock was used "
            "for them (rule C8)"
        )
    return _curve_service(
        rows, window,
        method="survival.km_resolution_curve",
        unit="probability unresolved",
        version=1,
        extra_params={"stratify_by": stratify_by, "clock": clock, "alpha": alpha},
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        extra_caveats=tuple(caveats),
        alpha=alpha,
    )


def median_resolution_days(spells, window, *, quantile=0.5, clock="wall", alpha=0.05) -> Evidence:
    """survival.median_resolution_days. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survival.median_resolution_days"
    rows, excluded, _ = _request_rows(spells, clock=clock)
    phash = params_hash(method, 1, {**_window_params(window), "quantile": quantile,
                                    "clock": clock, "alpha": alpha})
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)
    n_events = n - n_censored
    as_of = window.end
    if n_events < MIN_EVENTS_KM:
        return insufficient(
            method, n=n, as_of=as_of, unit="days", n_censored=n_censored, params_hash=phash,
            caveats=("needs " + str(MIN_EVENTS_KM) + " observed events, has " + str(n_events),),
        )
    curve = _km_fit(rows, alpha)
    checks = [
        _check_competing_risks(rows),
        _check_interval_censoring(rows),
        _check_censoring_informative(rows),
    ]
    point = _first_crossing(curve["t_days"], curve["survival"], quantile)
    reached = point is not None
    checks.append(Check(
        id="quantile-reached",
        label="The curve reaches the requested quantile inside the window",
        status="PASS" if reached else "FAIL",
        statistic=curve["survival"][-1] if curve["t_days"] else 1.0,
        blocking=not reached,
        detail="" if reached else (
            "more than " + format((1.0 - quantile) * 100.0, ".0f") + "% of spells are still "
            "unresolved at the end of the window, so the quantile is not reached. That is the "
            "finding: substituting the mean of the closed ones is the defect this product "
            "exists to name."
        ),
    ))
    if not reached:
        return insufficient(
            method, n=n, as_of=as_of, unit="days", n_censored=n_censored, params_hash=phash,
            caveats=(checks[-1].detail,),
        )
    lo = _first_crossing(curve["t_days"], curve["lo"], quantile)
    hi = _first_crossing(curve["t_days"], curve["hi"], quantile)
    caveats: list[str] = []
    interval: tuple[float, float] | None
    if lo is None or hi is None:
        interval = None
        caveats.append(
            "the Brookmeyer-Crowley interval is unbounded on the right: the upper confidence "
            "band never crosses the quantile inside the observed window"
        )
    else:
        interval = (lo, hi)
    informative = next(c for c in checks if c.id == "censoring-informative")
    if informative.status == "WARN":
        caveats.append(informative.detail)
    if _blocked(checks):
        blocking = next(c for c in checks if c.status == "FAIL" and c.blocking)
        return insufficient(
            method, n=n, as_of=as_of, unit="days", n_censored=n_censored, params_hash=phash,
            caveats=(blocking.detail,),
        )
    return Evidence(
        value=point,
        n=n,
        method=method,
        as_of=as_of,
        interval=interval,
        interval_kind="greenwood-95" if interval else "none",
        assumptions=(
            "Open requests are censored at the observation boundary, never dropped (rule C1).",
            "The curve crosses the requested quantile inside the observed window.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_censored=n_censored,
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        unit="days",
        params_hash=phash,
    )


def sla_attainment(spells, window, *, horizon_days, clock="wall", alpha=0.05) -> Evidence:
    """survival.sla_attainment. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survival.sla_attainment"
    rows, excluded, _ = _request_rows(spells, clock=clock)
    phash = params_hash(method, 1, {**_window_params(window), "horizon_days": horizon_days,
                                    "clock": clock, "alpha": alpha})
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)
    n_events = n - n_censored
    as_of = window.end
    at_risk_at_horizon = _at_risk(rows, horizon_days)
    last_seen = max((r.exit for r in rows), default=0.0)
    # The horizon check comes before the at-risk floor: past the last
    # observation the honest sentence is "that is beyond the data", not "not
    # enough data at that point", and the two states read very differently.
    beyond_support = n_events >= MIN_EVENTS_KM and horizon_days > last_seen
    if not beyond_support and (n_events < MIN_EVENTS_KM or at_risk_at_horizon < MIN_AT_RISK_AT_HORIZON):
        return insufficient(
            method, n=n, as_of=as_of, unit="probability resolved", n_censored=n_censored,
            params_hash=phash,
            caveats=(
                "needs " + str(MIN_EVENTS_KM) + " observed events and "
                + str(MIN_AT_RISK_AT_HORIZON) + " requests still at risk at day "
                + format(horizon_days, ".0f") + "; has " + str(n_events) + " events and "
                + str(at_risk_at_horizon) + " at risk",
            ),
        )
    curve = _km_fit(rows, alpha)
    last_observed = last_seen
    checks = [
        _check_competing_risks(rows),
        _check_interval_censoring(rows),
        _check_censoring_informative(rows),
        Check(
            id="horizon-in-support",
            label="The horizon lies inside the observed data",
            status="PASS" if horizon_days <= last_observed else "FAIL",
            statistic=last_observed,
            blocking=horizon_days > last_observed,
            detail="" if horizon_days <= last_observed else (
                "the target horizon of " + format(horizon_days, ".0f") + " days is past the "
                "last observation at " + format(last_observed, ".1f")
                + " days. Extrapolating a Kaplan-Meier curve beyond its data is fabrication, "
                "so no figure is shown."
            ),
        ),
    ]
    surv = _curve_value_at(curve, "survival", horizon_days)
    lo = _curve_value_at(curve, "lo", horizon_days)
    hi = _curve_value_at(curve, "hi", horizon_days)
    value: float | None = 1.0 - surv
    interval: tuple[float, float] | None = (1.0 - hi, 1.0 - lo)
    caveats: list[str] = []
    if _blocked(checks):
        blocking = next(c for c in checks if c.status == "FAIL" and c.blocking)
        value, interval = None, None
        caveats.append(blocking.detail)
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=interval,
        interval_kind="greenwood-95" if interval else "none",
        assumptions=(
            "Open requests are censored at the observation boundary, never dropped (rule C1).",
            "The horizon lies inside the observed data.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_censored=n_censored,
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        unit="probability resolved",
        params_hash=phash,
    )


def first_response_curve(spells, window, *, stratify_by=None, alpha=0.05) -> Evidence:
    """
    survival.first_response_curve. Identical machinery to km_resolution_curve
    with first_response_hours as the duration and "a non-author responded" as the
    event, because acknowledgement and resolution are different promises and
    communities conflate them.
    """
    rows: list[_Row] = []
    excluded = 0
    for spell in spells:
        if getattr(spell, "outcome", None) == "merged":
            excluded += 1
            continue
        entry = _entry_days(spell)
        responded = getattr(spell, "first_response_hours", None)
        if responded is not None:
            days, observed = responded / HOURS_PER_DAY, True
        else:
            # Never answered inside the window: censored at the request's age,
            # exactly as rule C1 requires for an unresolved request.
            days, observed = spell.duration_hours / HOURS_PER_DAY, False
        rows.append(_Row(
            entry=entry, exit=entry + max(0.0, days), event=observed,
            outcome="resolved" if observed else None,
            censoring="none" if observed else "administrative",
            left_truncated=bool(getattr(spell, "left_truncated", False)),
            ref=getattr(spell, "request_ref", ""), keys=_spell_keys(spell),
        ))
    if stratify_by is not None:
        rows = [r for r in rows if r.keys.get(stratify_by) is not None]
    return _curve_service(
        rows, window,
        method="survival.first_response_curve",
        unit="probability unanswered",
        version=1,
        extra_params={"stratify_by": stratify_by, "alpha": alpha},
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        alpha=alpha,
    )


def churn_curve(spells, window, *, stratify_by=None, alpha=0.05) -> Evidence:
    """survival.churn_curve. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    rows = _member_rows(spells)
    if stratify_by is not None:
        rows = [r for r in rows if r.keys.get(stratify_by) is not None]
    return _curve_service(
        rows, window,
        method="survival.churn_curve",
        unit="probability still a member",
        version=1,
        extra_params={"stratify_by": stratify_by, "alpha": alpha},
        alpha=alpha,
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _logrank_statistic(
    groups: Mapping[str, Sequence[_Row]], *, weights: str = "logrank"
) -> tuple[float, int, float]:
    """
    Mantel-Haenszel log-rank (weights="logrank") or Peto-Peto generalized
    Wilcoxon (weights="wilcoxon"), as a chi-square on len(groups) - 1 df.
    """
    keys = list(groups)
    g = len(keys)
    if g < 2:
        return 0.0, 0, 1.0
    all_rows = [r for rows in groups.values() for r in rows]
    event_times = sorted({r.exit for r in all_rows if r.event})
    observed = [0.0] * g
    expected = [0.0] * g
    cov = [[0.0] * g for _ in range(g)]
    for t in event_times:
        n_j = [_at_risk(groups[k], t) for k in keys]
        d_j = [sum(1 for r in groups[k] if r.event and r.exit == t) for k in keys]
        n = sum(n_j)
        d = sum(d_j)
        if n <= 1 or d == 0:
            continue
        w = 1.0 if weights == "logrank" else float(n)
        for i in range(g):
            observed[i] += w * d_j[i]
            expected[i] += w * d * n_j[i] / n
        factor = w * w * d * (n - d) / (n - 1) / (n * n)
        for i in range(g):
            for j in range(g):
                cov[i][j] += factor * (n_j[i] * ((n if i == j else 0.0) - n_j[j]))
    diff = [observed[i] - expected[i] for i in range(g - 1)]
    sub = [[cov[i][j] for j in range(g - 1)] for i in range(g - 1)]
    try:
        solved = solve(sub, diff)
    except ValueError:
        return 0.0, g - 1, 1.0
    stat = math.fsum(d * s for d, s in zip(diff, solved))
    stat = max(0.0, stat)
    return stat, g - 1, chi2_sf(stat, g - 1)


def _group_summary(rows: Sequence[_Row], key: str, alpha: float) -> dict[str, Any]:
    curve = _km_fit(rows, alpha)
    median = _first_crossing(curve["t_days"], curve["survival"], 0.5)
    lo = _first_crossing(curve["t_days"], curve["lo"], 0.5)
    hi = _first_crossing(curve["t_days"], curve["hi"], 0.5)
    return {
        "key": key,
        "n": len(rows),
        "events": sum(1 for r in rows if r.event),
        "censored": sum(1 for r in rows if not r.event),
        "median": median,
        "lo": lo,
        "hi": hi,
    }


def _holm(p_values: Sequence[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for rank, idx in enumerate(order):
        value = min(1.0, (len(p_values) - rank) * p_values[idx])
        running = max(running, value)
        adjusted[idx] = running
    return adjusted


def logrank_compare(spells, window, *, group_by, weights="logrank", clock="wall",
                    alpha=0.05, k_anonymity=5) -> Evidence:
    """survival.logrank_compare. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survival.logrank_compare"
    rows, excluded, _ = _request_rows(spells, clock=clock)
    phash = params_hash(method, 1, {**_window_params(window), "group_by": group_by,
                                    "weights": weights, "alpha": alpha,
                                    "k_anonymity": k_anonymity})
    as_of = window.end
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)

    buckets: dict[str, list[_Row]] = {}
    for r in rows:
        key = str(r.keys.get(group_by, "unknown"))
        buckets.setdefault(key, []).append(r)
    pooled = [k for k, v in buckets.items() if sum(1 for r in v if r.event) < MIN_EVENTS_PER_GROUP]
    groups: dict[str, list[_Row]] = {k: v for k, v in buckets.items() if k not in pooled}
    if pooled:
        other: list[_Row] = []
        for k in pooled:
            other.extend(buckets[k])
        if sum(1 for r in other if r.event) >= MIN_EVENTS_PER_GROUP:
            groups["other"] = other
    if len(groups) < 2:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={"chi_square": None, "df": 0, "p_value": None,
                                                   "groups": [], "pairwise": []},
            n_censored=n_censored, params_hash=phash,
            caveats=(
                "needs at least two groups with " + str(MIN_EVENTS_PER_GROUP)
                + " observed events each; " + str(len(buckets)) + " groups were present and "
                + str(len(groups)) + " cleared the floor",
            ),
        )

    stat, df, p = _logrank_statistic(groups, weights=weights)
    rows_out = [_group_summary(v, k, alpha) for k, v in sorted(groups.items())]

    pairwise: list[dict[str, Any]] = []
    keys = sorted(groups)
    raw: list[float] = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            s, d, pp = _logrank_statistic({keys[i]: groups[keys[i]], keys[j]: groups[keys[j]]},
                                          weights=weights)
            pairwise.append({"a": keys[i], "b": keys[j], "chi_square": s, "p_value": pp,
                             "p_adjusted": None})
            raw.append(pp)
    for entry, adj in zip(pairwise, _holm(raw)):
        entry["p_adjusted"] = adj

    # Crossing detection: the log-rank test has most power against proportional
    # alternatives, so a non-significant p when curves cross is not evidence of
    # no difference.
    crossing = False
    if len(keys) == 2:
        a, b = (_km_fit(groups[k], alpha) for k in keys)
        grid = sorted(set(a["t_days"]) | set(b["t_days"]))
        signs = []
        for t in grid:
            gap = _curve_value_at(a, "survival", t) - _curve_value_at(b, "survival", t)
            if abs(gap) > 1e-9:
                signs.append(1 if gap > 0 else -1)
        crossing = len(set(signs)) > 1

    checks = [
        Check(
            id="group-min-n",
            label="Every reported group clears the events floor",
            status="WARN" if pooled else "PASS",
            statistic=float(len(pooled)),
            detail=(
                "pooled into 'other' for having fewer than " + str(MIN_EVENTS_PER_GROUP)
                + " observed events: " + ", ".join(sorted(pooled))
                + ". Groups below the floor are pooled with the count disclosed, never dropped."
            ) if pooled else "",
        ),
        Check(
            id="proportional-across-groups",
            label="The survival curves do not cross",
            status="WARN" if crossing else "PASS",
            detail=(
                "the curves cross, so the log-rank test is under-powered here and a large "
                "p-value is not evidence of no difference. Read the curves."
            ) if crossing else "",
        ),
        Check(
            id="k-anonymity-cells",
            label="No group row is small enough to identify anyone",
            status="PASS",
            statistic=float(k_anonymity),
            detail=(
                "the spell unit carries no member reference, so the floor is applied to the "
                "number of requests in the group"
            ),
        ),
        _check_competing_risks(rows),
        _check_interval_censoring(rows),
    ]
    suppressed = [r["key"] for r in rows_out if r["n"] < k_anonymity]
    if suppressed:
        checks[2] = Check(
            id="k-anonymity-cells",
            label="No group row is small enough to identify anyone",
            status="FAIL",
            statistic=float(k_anonymity),
            blocking=True,
            detail=(
                "these groups have fewer than " + str(k_anonymity) + " requests and their rows "
                "are suppressed: " + ", ".join(sorted(suppressed))
                + ". The aggregate test is still reported."
            ),
        )
        rows_out = [r for r in rows_out if r["n"] >= k_anonymity]

    value = {
        "chi_square": stat,
        "df": df,
        "p_value": p,
        "weights": weights,
        "groups": rows_out,
        "pairwise": pairwise,
    }
    caveats = tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail)
    if any(c.status == "FAIL" and c.blocking and c.id != "k-anonymity-cells" for c in checks):
        value = {"chi_square": None, "df": df, "p_value": None, "weights": weights,
                 "groups": [], "pairwise": []}
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="none",
        assumptions=(
            "Censoring is independent within every group.",
            "A common event-time scale across groups.",
            "A p-value is not an interval and must not be drawn as one.",
        ),
        checks=tuple(checks),
        caveats=caveats,
        n_censored=n_censored,
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        unit="",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# Cox proportional hazards
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Design:
    names: tuple[str, ...]
    x: tuple[tuple[float, ...], ...]
    entry: tuple[float, ...]
    exit: tuple[float, ...]
    event: tuple[bool, ...]
    dummy: frozenset[str]


def _build_design(rows: Sequence[_Row], covariates: Sequence[str]) -> _Design:
    """
    Numeric covariates enter directly; a categorical one is dummy-encoded with
    its first level (alphabetically) as the reference, so a hazard ratio is
    always relative to something a reader can name.
    """
    names: list[str] = []
    columns: list[list[float]] = []
    dummy: set[str] = set()
    for cov in covariates:
        values = [r.keys.get(cov) for r in rows]
        numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
        if numeric:
            names.append(cov)
            columns.append([float(v) for v in values])
            continue
        levels = sorted({str(v) for v in values})
        if len(levels) < 2:
            continue
        for level in levels[1:]:
            name = cov + "=" + level
            names.append(name)
            dummy.add(name)
            columns.append([1.0 if str(v) == level else 0.0 for v in values])
    x = tuple(tuple(col[i] for col in columns) for i in range(len(rows)))
    return _Design(
        names=tuple(names),
        x=x,
        entry=tuple(r.entry for r in rows),
        exit=tuple(r.exit for r in rows),
        event=tuple(r.event for r in rows),
        dummy=frozenset(dummy),
    )


def _cox_terms(design: _Design, beta: Sequence[float], *, want_hessian: bool = True):
    """
    Efron partial log-likelihood, its gradient and its observed information.

    Risk sets are accumulated by sweeping event times downward, adding subjects
    whose exit is at or after t and removing those whose entry is at or after t.
    That makes one pass O(n p^2) rather than O(events * n * p^2), which is what
    makes a profile-likelihood interval affordable in pure Python.
    """
    p = len(design.names)
    n = len(design.exit)
    order_exit = sorted(range(n), key=lambda i: -design.exit[i])
    order_entry = sorted(range(n), key=lambda i: -design.entry[i])
    eta = [math.fsum(beta[k] * design.x[i][k] for k in range(p)) for i in range(n)]
    max_eta = max(eta) if eta else 0.0
    w = [math.exp(e - max_eta) for e in eta]

    deaths_at: dict[float, list[int]] = {}
    for i in range(n):
        if design.event[i]:
            deaths_at.setdefault(design.exit[i], []).append(i)
    event_times = sorted(deaths_at, reverse=True)
    s0 = 0.0
    s1 = [0.0] * p
    s2 = [[0.0] * p for _ in range(p)]
    ei = 0
    ti = 0
    loglik = 0.0
    grad = [0.0] * p
    hess = [[0.0] * p for _ in range(p)]

    for t in event_times:
        while ei < n and design.exit[order_exit[ei]] >= t:
            i = order_exit[ei]
            wi = w[i]
            xi = design.x[i]
            s0 += wi
            for a in range(p):
                s1[a] += wi * xi[a]
                if want_hessian:
                    for b in range(a, p):
                        s2[a][b] += wi * xi[a] * xi[b]
            ei += 1
        while ti < n and design.entry[order_entry[ti]] >= t:
            i = order_entry[ti]
            wi = w[i]
            xi = design.x[i]
            s0 -= wi
            for a in range(p):
                s1[a] -= wi * xi[a]
                if want_hessian:
                    for b in range(a, p):
                        s2[a][b] -= wi * xi[a] * xi[b]
            ti += 1

        deaths = deaths_at[t]
        m = len(deaths)
        d0 = math.fsum(w[i] for i in deaths)
        d1 = [math.fsum(w[i] * design.x[i][a] for i in deaths) for a in range(p)]
        d2 = [[math.fsum(w[i] * design.x[i][a] * design.x[i][b] for i in deaths)
               for b in range(p)] for a in range(p)] if want_hessian else None
        for a in range(p):
            grad[a] += math.fsum(design.x[i][a] for i in deaths)
        loglik += math.fsum(eta[i] - max_eta for i in deaths)
        for l in range(m):
            frac = l / m
            phi = s0 - frac * d0
            if phi <= 0.0:
                continue
            loglik -= math.log(phi)
            v = [(s1[a] - frac * d1[a]) / phi for a in range(p)]
            for a in range(p):
                grad[a] -= v[a]
            if want_hessian:
                for a in range(p):
                    for b in range(a, p):
                        s2ab = s2[a][b] if b >= a else s2[b][a]
                        term = (s2ab - frac * d2[a][b]) / phi - v[a] * v[b]
                        hess[a][b] -= term
                        if b != a:
                            hess[b][a] -= term
    return loglik, grad, hess


def _cox_fit(design: _Design, *, fixed: Mapping[int, float] | None = None,
             start: Sequence[float] | None = None, penalizer: float = 0.0,
             max_iter: int = 40, tol: float = 1e-9):
    """Newton-Raphson with step halving. `fixed` pins coefficients for a profile fit."""
    p = len(design.names)
    beta = list(start) if start is not None else [0.0] * p
    fixed = dict(fixed or {})
    for k, v in fixed.items():
        beta[k] = v
    free = [k for k in range(p) if k not in fixed]
    loglik, grad, hess = _cox_terms(design, beta)
    if penalizer:
        loglik -= penalizer * math.fsum(b * b for b in beta)
    for _ in range(max_iter):
        if not free:
            break
        g = [grad[k] - 2.0 * penalizer * beta[k] for k in free]
        h = [[-hess[a][b] - (2.0 * penalizer if a == b else 0.0) for b in free] for a in free]
        try:
            step = solve(h, g)
        except ValueError:
            break
        scale = 1.0
        improved = False
        for _ in range(20):
            trial = list(beta)
            for idx, k in enumerate(free):
                trial[k] = beta[k] + scale * step[idx]
            new_ll, new_grad, new_hess = _cox_terms(design, trial)
            if penalizer:
                new_ll -= penalizer * math.fsum(b * b for b in trial)
            if new_ll >= loglik - 1e-12 and all(math.isfinite(b) for b in trial):
                beta, loglik, grad, hess = trial, new_ll, new_grad, new_hess
                improved = True
                break
            scale *= 0.5
        if not improved:
            break
        if max(abs(gi) for gi in g) < tol:
            break
    return beta, loglik, grad, hess


def _profile_bound(design: _Design, index: int, beta_hat: Sequence[float], loglik_max: float,
                   se: float, alpha: float, direction: int, penalizer: float) -> float:
    """
    The profile-likelihood confidence bound: the value of beta_j at which twice
    the drop in the maximized log-likelihood equals the chi-square critical
    value. Started from the Wald bound and refined by a one-dimensional Newton
    step, whose derivative is the profile score, so it converges in a handful of
    refits.
    """
    from app.stats.numeric import chi2_ppf

    critical = chi2_ppf(1.0 - alpha, 1)
    b = beta_hat[index] + direction * norm_ppf(1.0 - alpha / 2.0) * se
    start = list(beta_hat)
    for _ in range(12):
        fit, ll, grad, _ = _cox_fit(design, fixed={index: b}, start=start, penalizer=penalizer,
                                    max_iter=12)
        start = fit
        g = 2.0 * (loglik_max - ll) - critical
        slope = -2.0 * grad[index]
        if abs(g) < 1e-6:
            break
        if abs(slope) < 1e-12:
            b += direction * 0.25 * abs(se)
            continue
        step = -g / slope
        step = max(-4.0 * abs(se), min(4.0 * abs(se), step))
        b += step
    return b


def _schoenfeld_check(design: _Design, beta: Sequence[float], info: Sequence[Sequence[float]],
                      rows: Sequence[_Row], alpha: float) -> tuple[list[Check], Check]:
    """
    Grambsch and Therneau (1994). Schoenfeld residuals are regressed on
    transformed time; a non-zero slope is a hazard ratio that is not constant.

    The transform is g(t) = 1 - KM(t), R's default, which is robust to the
    heavy right tail of a resolution-time distribution.
    """
    p = len(design.names)
    n = len(design.exit)
    km = _km_fit(rows, 0.05)
    event_times = sorted({design.exit[i] for i in range(n) if design.event[i]})
    residuals: list[list[float]] = []
    transformed: list[float] = []
    eta = [math.fsum(beta[k] * design.x[i][k] for k in range(p)) for i in range(n)]
    max_eta = max(eta) if eta else 0.0
    w = [math.exp(e - max_eta) for e in eta]
    for t in event_times:
        at_risk = [i for i in range(n) if design.entry[i] < t <= design.exit[i]]
        if not at_risk:
            continue
        total = math.fsum(w[i] for i in at_risk)
        if total <= 0.0:
            continue
        xbar = [math.fsum(w[i] * design.x[i][a] for i in at_risk) / total for a in range(p)]
        g = 1.0 - _curve_value_at(km, "survival", t)
        for i in at_risk:
            if design.event[i] and design.exit[i] == t:
                residuals.append([design.x[i][a] - xbar[a] for a in range(p)])
                transformed.append(g)
    d = len(residuals)
    if d < 2 * p or d == 0:
        skipped = Check(id="proportional-hazards", label="Hazards stay proportional over time",
                        status="SKIPPED", detail="too few events to test proportionality")
        return [skipped for _ in range(p)], skipped
    gbar = mean(transformed)
    centred = [g - gbar for g in transformed]
    sgg = math.fsum(c * c for c in centred)
    if sgg <= 0.0:
        skipped = Check(id="proportional-hazards", label="Hazards stay proportional over time",
                        status="SKIPPED", detail="the time transform is constant")
        return [skipped for _ in range(p)], skipped
    tvec = [math.fsum(centred[k] * residuals[k][a] for k in range(d)) for a in range(p)]
    # Var(T) = sum (g - gbar)^2 * I / d, with I the observed information.
    var = [[sgg * info[a][b] / d for b in range(p)] for a in range(p)]
    per_covariate: list[Check] = []
    for a in range(p):
        if var[a][a] <= 0.0:
            per_covariate.append(Check(
                id="proportional-hazards", label="Hazards stay proportional over time",
                status="SKIPPED", detail="the information matrix is degenerate for "
                                         + design.names[a]))
            continue
        stat = tvec[a] ** 2 / var[a][a]
        p_value = chi2_sf(stat, 1)
        if p_value < alpha:
            direction = "rises" if tvec[a] > 0 else "falls"
            per_covariate.append(Check(
                id="proportional-hazards",
                label="The effect of " + design.names[a] + " is constant over time",
                status="FAIL",
                statistic=stat,
                p_value=p_value,
                blocking=True,
                detail=(
                    "the effect of " + design.names[a] + " changes over time (Schoenfeld "
                    "correlation with transformed time, p=" + format(p_value, ".4f")
                    + "), and its hazard " + direction + " as requests age. A single hazard "
                    "ratio would be a misleading summary, so this row is suppressed. Run the "
                    "model stratified by " + design.names[a] + ", which is exact under "
                    "non-proportionality."
                ),
            ))
        else:
            per_covariate.append(Check(
                id="proportional-hazards",
                label="The effect of " + design.names[a] + " is constant over time",
                status="PASS", statistic=stat, p_value=p_value,
            ))
    try:
        solved = solve(var, tvec)
        global_stat = math.fsum(t * s for t, s in zip(tvec, solved))
        global_p = chi2_sf(max(0.0, global_stat), p)
    except ValueError:
        global_stat, global_p = 0.0, 1.0
    global_check = Check(
        id="proportional-hazards-global",
        label="Hazards stay proportional over time, across all covariates",
        status="FAIL" if global_p < alpha else "PASS",
        statistic=global_stat,
        p_value=global_p,
        detail=(
            "at least one covariate's effect changes over time; the per-covariate rows say "
            "which, and those rows are suppressed rather than printed as constants."
        ) if global_p < alpha else "",
    )
    return per_covariate, global_check


def cox_hazard_ratios(spells, window, *, covariates, time_varying=(), penalizer=0.0,
                      alpha=0.05, ties="efron", clock="wall") -> Evidence:
    """survival.cox_hazard_ratios. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survival.cox_hazard_ratios"
    if ties != "efron":
        raise ValueError("only the Efron tie correction is implemented; got " + repr(ties))
    rows, excluded, _ = _request_rows(spells, clock=clock)
    phash = params_hash(method, 1, {**_window_params(window), "covariates": tuple(covariates),
                                    "time_varying": tuple(time_varying), "penalizer": penalizer,
                                    "alpha": alpha, "ties": ties, "clock": clock})
    as_of = window.end
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)
    n_events = n - n_censored
    design = _build_design(rows, list(covariates))
    p = len(design.names)
    floor = MIN_EVENTS_PER_COVARIATE * max(1, p)
    if p == 0 or n_events < floor:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], unit="hazard ratio",
            n_censored=n_censored, params_hash=phash,
            caveats=(
                "needs " + str(MIN_EVENTS_PER_COVARIATE) + " observed events per covariate, so "
                + str(floor) + " for " + str(p) + " covariates; has " + str(n_events) + " events",
            ),
        )

    beta, loglik, grad, hess = _cox_fit(design, penalizer=penalizer)
    info = [[-hess[a][b] for b in range(p)] for a in range(p)]
    try:
        cov = inverse(info)
        se = [math.sqrt(max(0.0, cov[a][a])) for a in range(p)]
    except ValueError:
        se = [math.inf] * p

    per_covariate_ph, global_ph = _schoenfeld_check(design, beta, info, rows, alpha)

    epv = n_events / p
    checks: list[Check] = [
        global_ph,
        Check(
            id="events-per-variable",
            label="There are enough events to support this many covariates",
            status="PASS" if epv >= 10 else ("FAIL" if epv < 5 else "WARN"),
            statistic=epv,
            blocking=epv < 5,
            detail=(
                "only " + format(epv, ".1f") + " events per covariate; below five the "
                "coefficients are unstable and their intervals are not trustworthy, so no "
                "figures are shown (Peduzzi et al. 1995)."
            ) if epv < 5 else (
                format(epv, ".1f") + " events per covariate, below the rule of ten"
            ) if epv < 10 else "",
        ),
        _check_censoring_informative(rows),
        _check_competing_risks(rows),
    ]

    # Collinearity by variance inflation on the design.
    vif_max, vif_name = _max_vif(design)
    checks.append(Check(
        id="collinearity",
        label="No covariate is a near-copy of the others",
        status="WARN" if vif_max > 5.0 else "PASS",
        statistic=vif_max,
        detail=("variance inflation factor " + format(vif_max, ".1f") + " on " + vif_name
                + "; its coefficient and the one it duplicates are not separately readable")
        if vif_max > 5.0 else "",
    ))

    table: list[dict[str, Any]] = []
    for a in range(p):
        name = design.names[a]
        column = [design.x[i][a] for i in range(n)]
        supporting = sum(
            1 for i in range(n)
            if design.event[i] and (column[i] != 0.0 if name in design.dummy else True)
        )
        separated = _is_separated(design, a)
        ph = per_covariate_ph[a]
        row: dict[str, Any] = {
            "covariate": name,
            "coef": beta[a],
            "hazard_ratio": math.exp(beta[a]),
            "lo": None,
            "hi": None,
            "se": se[a],
            "p_value": None,
            "n_events_supporting": supporting,
            "n": n,
            "suppressed": False,
            "suppression_reason": "",
        }
        if separated:
            row["suppressed"] = True
            row["coef"] = None
            row["hazard_ratio"] = None
            row["suppression_reason"] = (
                name + " predicts the outcome perfectly, so its coefficient diverges and no "
                "finite hazard ratio exists"
            )
            checks.append(Check(
                id="separation", label="No covariate perfectly predicts the outcome",
                status="FAIL", blocking=True,
                detail=row["suppression_reason"],
            ))
            table.append(row)
            continue
        if ph.status == "FAIL":
            row["suppressed"] = True
            row["coef"] = None
            row["hazard_ratio"] = None
            row["suppression_reason"] = ph.detail
            checks.append(ph)
            table.append(row)
            continue
        checks.append(ph)
        if math.isfinite(se[a]) and se[a] > 0.0:
            wald = beta[a] / se[a]
            row["p_value"] = 2.0 * (1.0 - _phi(abs(wald)))
            lo = _profile_bound(design, a, beta, loglik, se[a], alpha, -1, penalizer)
            hi = _profile_bound(design, a, beta, loglik, se[a], alpha, +1, penalizer)
            row["lo"] = math.exp(min(lo, hi))
            row["hi"] = math.exp(max(lo, hi))
        table.append(row)

    caveats = [c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail]
    if any(c.id == "events-per-variable" and c.status == "FAIL" for c in checks):
        table = []
    return Evidence(
        value=table,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="profile-95",
        assumptions=(
            "Hazards are proportional over time.",
            "The log-hazard is linear in each continuous covariate.",
            "Censoring is independent of the outcome (rule C9).",
            "Ties are handled by the Efron correction.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        n_censored=n_censored,
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        unit="hazard ratio",
        params_hash=phash,
    )


def _phi(z: float) -> float:
    from app.stats.numeric import norm_cdf
    return norm_cdf(z)


def _is_separated(design: _Design, index: int) -> bool:
    """A dummy covariate under which every subject either has the event or none does."""
    name = design.names[index]
    if name not in design.dummy:
        return False
    ones = [i for i in range(len(design.exit)) if design.x[i][index] == 1.0]
    zeros = [i for i in range(len(design.exit)) if design.x[i][index] == 0.0]
    if not ones or not zeros:
        return True
    events_in_ones = sum(1 for i in ones if design.event[i])
    events_in_zeros = sum(1 for i in zeros if design.event[i])
    return events_in_ones == 0 or events_in_zeros == 0


def _max_vif(design: _Design) -> tuple[float, str]:
    p = len(design.names)
    n = len(design.exit)
    if p < 2 or n < p + 2:
        return 1.0, ""
    worst, worst_name = 1.0, ""
    for a in range(p):
        y = [design.x[i][a] for i in range(n)]
        others = [k for k in range(p) if k != a]
        try:
            xtx = [[math.fsum(design.x[i][j] * design.x[i][k] for i in range(n))
                    for k in others] for j in others]
            xty = [math.fsum(design.x[i][j] * y[i] for i in range(n)) for j in others]
            coefs = solve(xtx, xty)
        except (ValueError, ZeroDivisionError):
            continue
        fitted = [math.fsum(c * design.x[i][k] for c, k in zip(coefs, others)) for i in range(n)]
        ybar = mean(y)
        ss_tot = math.fsum((v - ybar) ** 2 for v in y)
        ss_res = math.fsum((v - f) ** 2 for v, f in zip(y, fitted))
        if ss_tot <= 0.0:
            continue
        r2 = max(0.0, min(0.9999, 1.0 - ss_res / ss_tot))
        vif = 1.0 / (1.0 - r2)
        if vif > worst:
            worst, worst_name = vif, design.names[a]
    return worst, worst_name


# ---------------------------------------------------------------------------
# Competing risks
# ---------------------------------------------------------------------------


def competing_risks_cif(spells, window, *, causes=("resolved", "escalated", "withdrawn"),
                        alpha=0.05, clock="wall") -> Evidence:
    """survival.competing_risks_cif. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survival.competing_risks_cif"
    rows, excluded, _ = _request_rows(spells, clock=clock, event_causes=tuple(causes))
    phash = params_hash(method, 1, {**_window_params(window), "causes": tuple(causes),
                                    "alpha": alpha, "clock": clock})
    as_of = window.end
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)
    z = _z(alpha)

    counts = {c: sum(1 for r in rows if r.event and r.outcome == c) for c in causes}
    if not counts or max(counts.values(), default=0) < MIN_EVENTS_KM:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, unit="cumulative probability",
            n_censored=n_censored, params_hash=phash,
            caveats=(
                "needs " + str(MIN_EVENTS_KM) + " events of the reported cause; the largest "
                "cause has " + str(max(counts.values(), default=0)),
            ),
        )

    times = sorted({r.exit for r in rows if r.event})
    overall = 1.0
    cif = {c: 0.0 for c in causes}
    var = {c: 0.0 for c in causes}
    series: dict[str, dict[str, list[float]]] = {
        c: {"t_days": [], "cif": [], "lo": [], "hi": []} for c in causes
    }
    still_open: dict[str, list[float]] = {"t_days": [], "probability": []}
    # Aalen-Johansen: CIF_k(t) = sum_{t_i <= t} S(t_i-) * d_ki / n_i, with S the
    # overall event-free survival. Variance by the standard Marubini-Valsecchi
    # delta-method estimator, accumulated in closed form: expanding the
    # [F(t) - F(t_i)]^2 terms lets every running total be kept incrementally, so
    # the whole curve costs one pass rather than one pass per point.
    acc = {c: {"a": 0.0, "af": 0.0, "aff": 0.0, "b": 0.0, "cc": 0.0, "cf": 0.0} for c in causes}
    for t in times:
        n_risk = _at_risk(rows, t)
        if n_risk <= 0:
            continue
        d_by_cause = {c: sum(1 for r in rows if r.event and r.outcome == c and r.exit == t)
                      for c in causes}
        d_total = sum(d_by_cause.values())
        prev_surv = overall
        for c in causes:
            cif[c] += prev_surv * d_by_cause[c] / n_risk
        overall *= (1.0 - d_total / n_risk)
        for c in causes:
            state = acc[c]
            f_i = cif[c]
            if n_risk > d_total:
                a_i = d_total / (n_risk * (n_risk - d_total))
                state["a"] += a_i
                state["af"] += a_i * f_i
                state["aff"] += a_i * f_i * f_i
            state["b"] += (prev_surv ** 2) * (n_risk - d_by_cause[c]) * d_by_cause[c] / (n_risk ** 3)
            c_i = prev_surv * d_by_cause[c] / (n_risk ** 2)
            state["cc"] += c_i
            state["cf"] += c_i * f_i
            f = cif[c]
            v = (f * f * state["a"] - 2.0 * f * state["af"] + state["aff"]) + state["b"] \
                - 2.0 * (f * state["cc"] - state["cf"])
            var[c] = max(0.0, v)
            se = math.sqrt(var[c])
            series[c]["t_days"].append(t)
            series[c]["cif"].append(cif[c])
            series[c]["lo"].append(max(0.0, cif[c] - z * se))
            series[c]["hi"].append(min(1.0, cif[c] + z * se))
        still_open["t_days"].append(t)
        still_open["probability"].append(overall)

    # cif-sums-to-one is an implementation invariant, not a claim about data.
    worst_gap = 0.0
    for i, t in enumerate(still_open["t_days"]):
        total = still_open["probability"][i] + sum(series[c]["cif"][i] for c in causes)
        worst_gap = max(worst_gap, abs(total - 1.0))
    checks = [
        Check(
            id="cif-sums-to-one",
            label="The cumulative incidences and the still-open probability sum to one",
            status="PASS" if worst_gap < 1e-9 else "FAIL",
            statistic=worst_gap,
            blocking=worst_gap >= 1e-9,
            detail="" if worst_gap < 1e-9 else (
                "the estimated incidences do not sum to one (worst gap "
                + format(worst_gap, ".2e") + "). That is an implementation bug, not a finding, "
                "so no figures are shown."
            ),
        ),
        Check(
            id="cause-min-n",
            label="Every competing cause has enough events to compete",
            status="PASS" if all(v >= 5 for v in counts.values()) else "WARN",
            statistic=float(min(counts.values())),
            detail=(
                "causes with fewer than five events: "
                + ", ".join(c for c, v in sorted(counts.items()) if v < 5)
                + ". Their incidence curves rest on very little."
            ) if any(v < 5 for v in counts.values()) else "",
        ),
        _check_censoring_informative(rows),
    ]
    value: dict[str, Any] = {c: series[c] for c in causes}
    value["still_open"] = still_open
    value["counts"] = dict(counts)
    if _blocked(checks):
        value = {}
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="normal-95",
        assumptions=(
            "Every request eventually exits by exactly one of the declared causes.",
            "Censoring is independent of all causes.",
            "1 - Kaplan-Meier per cause is NOT the cumulative incidence; it always exceeds it.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        n_censored=n_censored,
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        unit="cumulative probability",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# The demonstration figure
# ---------------------------------------------------------------------------


def naive_vs_km_gap(spells, window, *, clock="wall", alpha=0.05) -> Evidence:
    """
    survival.naive_vs_km_gap.

    The permanent regression test of docs/RULES.md section 7, rendered as a UI
    panel: the mean of the closed spells beside the Kaplan-Meier median, and the
    gap between them. The naive figure is computed here only so that it can be
    shown to be wrong; nothing else in the platform may report it.
    """
    method = "survival.naive_vs_km_gap"
    rows, excluded, _ = _request_rows(spells, clock=clock)
    phash = params_hash(method, 1, {**_window_params(window), "clock": clock, "alpha": alpha})
    as_of = window.end
    n = len(rows)
    n_censored = sum(1 for r in rows if not r.event)
    n_events = n - n_censored
    closed = [r.exit for r in rows if r.event]
    if n_events < MIN_EVENTS_KM:
        return insufficient(
            method, n=n, as_of=as_of, unit="days", n_censored=n_censored, params_hash=phash,
            empty_value={"naive_mean_closed_days": None, "km_median_days": None,
                         "gap_days": None, "n_closed": n_events, "n_open": n_censored},
            caveats=("needs " + str(MIN_EVENTS_KM) + " observed events, has " + str(n_events),),
        )
    curve = _km_fit(rows, alpha)
    km_median = _first_crossing(curve["t_days"], curve["survival"], 0.5)
    naive = mean(closed)
    checks = [
        Check(
            id="open-requests-present",
            label="There are still-open requests, so the naive figure is biased",
            status="PASS",
            statistic=float(n_censored),
            detail=(
                str(n_censored) + " of " + str(n) + " requests are still open. Excluding them "
                "does not make the average neutral, it biases it downward, because the slow "
                "requests are exactly the ones still open."
            ),
        ),
        _check_competing_risks(rows),
        _check_interval_censoring(rows),
    ]
    value = {
        "naive_mean_closed_days": naive,
        "km_median_days": km_median,
        "gap_days": (km_median - naive) if km_median is not None else None,
        "n_closed": n_events,
        "n_open": n_censored,
        "share_open": n_censored / n if n else 0.0,
        "headline": (
            "The average over closed requests alone is "
            + format(naive, ".1f") + " days. Counting the " + str(n_censored)
            + " still open, half of requests take at least "
            + (format(km_median, ".1f") + " days." if km_median is not None
               else "longer than the window observed.")
        ),
    }
    if _blocked(checks):
        value = {"naive_mean_closed_days": None, "km_median_days": None, "gap_days": None,
                 "n_closed": n_events, "n_open": n_censored}
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="none",
        assumptions=(
            "Open requests are censored at the observation boundary, never dropped (rule C1).",
            "The naive figure is shown only to be contradicted; it is never the reported number.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.detail and c.status in ("WARN", "FAIL")),
        n_censored=n_censored,
        n_excluded=excluded,
        exclusion_reason="merged_duplicate" if excluded else "",
        unit="days",
        params_hash=phash,
    )


__all__ = [
    "km_resolution_curve",
    "median_resolution_days",
    "sla_attainment",
    "first_response_curve",
    "churn_curve",
    "logrank_compare",
    "cox_hazard_ratios",
    "competing_risks_cif",
    "naive_vs_km_gap",
]
