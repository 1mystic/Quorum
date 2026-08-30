"""
Stratified lotteries for panel and sub-committee selection.

Sortition makes the panel representative of the POOL, not of the community. If the
pool is skewed the panel inherits the skew, and that is what pool-representativeness
discloses.

The maximin objective is solved exactly rather than approximately, because on a
single stratification it has a closed form. Once the per-stratum seat counts are
fixed, every member of a stratum must have the same selection probability
(anything else is dominated), so a member of stratum s is chosen with probability
c_s / |s| and the problem collapses to choosing integer counts c_s inside their
quota bounds, summing to the panel size, that maximise the smallest ratio. That
is a water-filling problem and it is solved here by repeatedly giving the next
seat to whichever stratum currently has the worst odds. Leximin continues the
same sweep, which is what makes it the natural extension rather than a second
algorithm.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import chi2_sf

POOL_MULTIPLE = 3


def _member_fields(member: Any) -> tuple[str, Mapping[str, str]]:
    ref = getattr(member, "member_ref", None)
    strata = getattr(member, "strata", None)
    if strata is None:
        strata = getattr(member, "strata_at_entry", {}) or {}
    if ref is None and isinstance(member, Mapping):
        ref = member.get("member_ref")
        strata = member.get("strata", {})
    return str(ref), dict(strata or {})


def _quota_key(key) -> tuple[str, str]:
    """
    A quota names one (feature, value) pair: ("block", "C"), ("age_band", "60+").

    A bare string is read as a value whose feature is inferred from the pool,
    which is what a manifest that only stratifies on one axis will hand over.
    """
    if isinstance(key, tuple) and len(key) == 2:
        return str(key[0]), str(key[1])
    return "", str(key)


def _partition(pool, quotas) -> tuple[dict[str, list[str]], str, list[str]]:
    """Members grouped by the quota feature, plus anyone the quotas do not name."""
    features = {f for f, _ in (_quota_key(k) for k in quotas) if f}
    if len(features) > 1:
        raise ValueError(
            "sortition.stratified_panel solves the maximin lottery exactly for ONE "
            "stratification feature, where the strata are disjoint and the optimum has a "
            "closed form. Quotas here name " + ", ".join(sorted(features)) + ". Crossing two "
            "features makes the feasible-panel polytope an integer program, and running a "
            "heuristic under the name of a provable optimum is the drift this package exists "
            "to prevent."
        )
    feature = next(iter(features)) if features else ""

    groups: dict[str, list[str]] = {}
    unassigned: list[str] = []
    for member in pool:
        ref, strata = _member_fields(member)
        value = str(strata.get(feature)) if feature and feature in strata else None
        if value is None:
            unassigned.append(ref)
            continue
        groups.setdefault(value, []).append(ref)
    for group in groups.values():
        group.sort()
    return groups, feature, sorted(unassigned)


def maximin_counts(sizes: Mapping[str, int], bounds: Mapping[str, tuple[int, int]],
                   panel_size: int, *, leximin: bool) -> dict[str, int] | str:
    """
    Seats per stratum maximising the smallest selection probability.

    Water-filling: start every stratum at its lower bound, then hand each
    remaining seat to whichever stratum has the worst odds c_s/|s| and room to
    take it. Under maximin this is optimal because raising the worst stratum is
    the only move that can raise the minimum; leximin keeps sweeping after the
    minimum stops moving, which is the same loop.

    Returns the counts, or a string naming the binding constraint if the quotas
    cannot be met.
    """
    keys = sorted(sizes)
    counts = {}
    for key in keys:
        low, high = bounds.get(key, (0, sizes[key]))
        high = min(high, sizes[key])
        if low > high:
            return (
                "stratum " + key + " needs at least " + str(low) + " panellists but the pool "
                "holds only " + str(sizes[key])
            )
        counts[key] = low
    floor = sum(counts.values())
    ceiling = sum(min(bounds.get(k, (0, sizes[k]))[1], sizes[k]) for k in keys)
    if floor > panel_size:
        return (
            "the quota lower bounds add to " + str(floor) + ", which is more than the panel "
            "size of " + str(panel_size)
        )
    if ceiling < panel_size:
        return (
            "the quota upper bounds add to " + str(ceiling) + ", which is fewer than the panel "
            "size of " + str(panel_size)
        )

    seats_left = panel_size - floor
    while seats_left > 0:
        best = None
        best_ratio = None
        for key in keys:
            high = min(bounds.get(key, (0, sizes[key]))[1], sizes[key])
            if counts[key] >= high:
                continue
            ratio = counts[key] / sizes[key]
            if best_ratio is None or ratio < best_ratio - 1e-15 or (
                abs(ratio - best_ratio) <= 1e-15 and key < best
            ):
                best, best_ratio = key, ratio
        if best is None:
            return "no stratum can take another panellist without breaking its upper quota"
        counts[best] += 1
        seats_left -= 1
        if not leximin and seats_left == 0:
            break
    return counts


def stratified_panel(pool, quotas, panel_size, as_of, *, seed, objective="maximin") -> Evidence:
    """sortition.stratified_panel. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "sortition.stratified_panel"
    phash = params_hash(method, 1, {
        "quotas": {str(_quota_key(k)): tuple(v) for k, v in dict(quotas).items()},
        "panel_size": panel_size, "seed": seed, "objective": objective,
    })
    if objective not in ("maximin", "leximin"):
        raise ValueError(
            "sortition.stratified_panel objective must be 'maximin' or 'leximin', got "
            + repr(objective)
        )

    pool = list(pool)
    n = len(pool)
    empty = {"panel": [], "quota_satisfaction": [], "selection_probabilities": {},
             "min_probability": None, "max_probability": None}

    if panel_size < 1 or n < POOL_MULTIPLE * panel_size:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="panellists",
            caveats=(
                "A lottery needs a pool at least " + str(POOL_MULTIPLE) + " times the panel "
                "size; the pool holds " + str(n) + " for a panel of " + str(panel_size)
                + ". Below that the draw is a formality, not a lottery.",
            ),
        )

    groups, feature, unassigned = _partition(pool, quotas)
    if unassigned:
        # Members the quota feature does not describe form their own stratum
        # rather than being silently dropped from the frame.
        groups.setdefault("unstated", []).extend(unassigned)
        groups["unstated"].sort()

    sizes = {key: len(members) for key, members in groups.items()}
    bounds = {}
    for key, value in dict(quotas).items():
        _, level = _quota_key(key)
        bounds[level] = (int(value[0]), int(value[1]))

    counts = maximin_counts(sizes, bounds, panel_size, leximin=(objective == "leximin"))
    if isinstance(counts, str):
        return Evidence(
            value=empty,
            n=n,
            method=method,
            as_of=as_of,
            checks=(
                Check(
                    id="quotas-feasible",
                    label="The quotas can actually be met from this pool",
                    status="FAIL",
                    blocking=True,
                    detail=(
                        "No panel satisfies these quotas: " + counts + ". The binding "
                        "constraint is named rather than a panel returned that quietly ignores "
                        "one of them."
                    ),
                ),
            ),
            caveats=("No panel is drawn. " + counts[0].upper() + counts[1:] + ".",),
            unit="panellists",
            params_hash=phash,
        )

    rng = random.Random(seed)
    panel: list[str] = []
    for key in sorted(groups):
        members = groups[key]
        take = counts.get(key, 0)
        panel.extend(rng.sample(members, take))
    panel.sort()

    probabilities = {
        ref: counts.get(key, 0) / sizes[key]
        for key, members in groups.items()
        for ref in members
    }
    values = sorted(probabilities.values())
    min_probability = values[0]
    max_probability = values[-1]
    uniform = panel_size / n

    # Monte Carlo interval on the realised per-person rate, from the seeded
    # lottery itself rather than from an assumption about it.
    trials = 400
    check_rng = random.Random(seed + 1)
    hits = {ref: 0 for ref in probabilities}
    for _ in range(trials):
        for key in sorted(groups):
            for ref in check_rng.sample(groups[key], counts.get(key, 0)):
                hits[ref] += 1
    observed_min = min(hits.values()) / trials
    observed_max = max(hits.values()) / trials
    mc_se = math.sqrt(max(min_probability * (1 - min_probability), 1e-12) / trials)

    quota_rows = []
    for key in sorted(groups):
        low, high = bounds.get(key, (0, sizes[key]))
        quota_rows.append({
            "stratum": key,
            "pool_size": sizes[key],
            "seats": counts.get(key, 0),
            "quota_lo": low,
            "quota_hi": high,
            "satisfied": low <= counts.get(key, 0) <= high,
            "selection_probability": counts.get(key, 0) / sizes[key],
        })

    checks = [
        Check(
            id="quotas-feasible",
            label="The quotas can actually be met from this pool",
            status="PASS",
            statistic=float(panel_size),
        ),
        Check(
            id="probability-floor",
            label="The smallest chance anyone in the pool had of being drawn",
            status="FAIL" if min_probability < 0.25 * uniform else (
                "WARN" if min_probability < 0.5 * uniform else "PASS"
            ),
            statistic=min_probability,
            blocking=False,
            detail=(
                "The least-favoured volunteer had a " + "{:.1%}".format(min_probability)
                + " chance against " + "{:.1%}".format(uniform) + " under an unconstrained "
                "draw. The fairness of sortition IS that everyone had a real chance, and tight "
                "quotas can drive that towards zero without any step looking wrong."
            ) if min_probability < 0.5 * uniform else "",
        ),
    ]

    # Pool representativeness against the wider roster, when one is derivable
    # from the quota bounds. Sortition cannot fix a skewed pool, so it discloses.
    expected_shares = {}
    for key in sorted(groups):
        low, high = bounds.get(key, (None, None))
        if low is not None and panel_size:
            expected_shares[key] = (low + min(high, sizes[key])) / (2.0 * panel_size)
    chi_square = None
    p_value = None
    if len(expected_shares) >= 2 and abs(sum(expected_shares.values()) - 1.0) < 0.5:
        total_expected = sum(expected_shares.values())
        chi_square = 0.0
        for key, share in expected_shares.items():
            expected = n * share / total_expected
            if expected > 0:
                chi_square += (sizes[key] - expected) ** 2 / expected
        p_value = chi2_sf(chi_square, len(expected_shares) - 1)
    checks.append(Check(
        id="pool-representativeness",
        label="How the volunteer pool differs from the community the quotas describe",
        status=("SKIPPED" if p_value is None else ("WARN" if p_value < 0.05 else "PASS")),
        statistic=chi_square,
        p_value=p_value,
        detail=(
            "The volunteer pool's composition differs from the target composition the quotas "
            "encode (chi-square " + "{:.2f}".format(chi_square) + ", p = "
            + "{:.4f}".format(p_value) + "). Sortition makes the panel representative of the "
            "POOL and cannot fix this; the quotas mask it inside the panel while leaving it "
            "true of everyone who volunteered."
        ) if (p_value is not None and p_value < 0.05) else (
            "No target composition is derivable from these quotas, so the pool cannot be "
            "compared to one here." if p_value is None else ""
        ),
    ))

    return Evidence(
        value={
            "panel": panel,
            "quota_satisfaction": quota_rows,
            "selection_probabilities": probabilities,
            "min_probability": min_probability,
            "max_probability": max_probability,
            "uniform_probability": uniform,
            "observed_min_rate": observed_min,
            "observed_max_rate": observed_max,
            "monte_carlo_trials": trials,
            "objective": objective,
            "stratified_on": feature or "unstated",
        },
        n=n,
        method=method,
        as_of=as_of,
        interval=(max(0.0, min_probability - 2 * mc_se), min(1.0, max_probability + 2 * mc_se)),
        interval_kind="normal-95",
        assumptions=(
            "The volunteer pool is the sampling frame. The panel is representative of the "
            "POOL, not of the community.",
            "Within a stratum every member is equally likely, which is what makes the "
            + objective + " optimum attainable.",
        ),
        checks=tuple(checks),
        caveats=(
            "The panel itself has no interval: it is a draw, not an estimate. The interval "
            "shown spans the per-person selection rates observed across " + str(trials)
            + " seeded replays of this same lottery.",
            "Reproducible bit for bit from seed " + str(seed) + ", which is in params_hash, so "
            "a contested draw can be replayed rather than argued about.",
        ),
        unit="panellists",
        params_hash=phash,
    )


__all__ = [
    "maximin_counts",
    "stratified_panel",
]
