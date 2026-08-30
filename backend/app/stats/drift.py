"""
Distribution drift against a stored reference.

The reference distribution is not stream data. It is an artifact of a previous
fit, supplied by the caller. app/stats/ does not fetch it.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import newcombe_difference, wilson_interval

MIN_WINDOW = 200
MIN_PER_BIN = 20
MIN_LABELLED = 100

# Siddiqi's credit-scoring conventions. They are conventions, not quantiles of
# any distribution, and the Method Card says so: a threshold presented as if it
# were a p-value is a small lie.
PSI_INVESTIGATE = 0.10
PSI_SIGNIFICANT = 0.25


def _as_feature_mapping(data: Any) -> dict[str, list[float]]:
    """Accept either a mapping of feature name to values, or one bare sequence."""
    if isinstance(data, Mapping):
        return {str(k): [float(v) for v in values] for k, values in data.items()}
    return {"value": [float(v) for v in data]}


def quantile_edges(reference: Sequence[float], bins: int) -> list[float]:
    """
    Bin edges from the REFERENCE quantiles.

    Recomputing the edges on the current data is the standard implementation bug
    in this family and it makes PSI approximately zero always, because both
    histograms are then equal by construction. Deriving them once from the
    reference is the whole method.
    """
    ordered = sorted(float(v) for v in reference)
    n = len(ordered)
    if n == 0:
        raise ValueError("cannot derive bin edges from an empty reference")
    edges = [-math.inf]
    for i in range(1, bins):
        edges.append(ordered[min(n - 1, int(round(i * n / bins)))])
    edges.append(math.inf)
    deduplicated = [edges[0]]
    for edge in edges[1:]:
        if edge > deduplicated[-1]:
            deduplicated.append(edge)
    if len(deduplicated) < 2:
        deduplicated = [-math.inf, math.inf]
    return deduplicated


def _histogram(values: Sequence[float], edges: Sequence[float]) -> list[int]:
    counts = [0] * (len(edges) - 1)
    for value in values:
        v = float(value)
        for i in range(len(edges) - 1):
            if v <= edges[i + 1] or i == len(edges) - 2:
                counts[i] += 1
                break
    return counts


def psi_from_shares(reference_shares: Sequence[float], current_shares: Sequence[float]) -> float:
    """
    Population stability index: `sum((a_i - b_i) * ln(a_i / b_i))`.

    Exact and hand-computable, symmetric in its two arguments (swapping them
    negates both factors, so the product is unchanged), and zero when the two
    distributions are identical. All three facts are asserted in the tests.
    """
    if len(reference_shares) != len(current_shares):
        raise ValueError("the two share vectors have different lengths")
    total = 0.0
    for a, b in zip(reference_shares, current_shares):
        if a <= 0.0 or b <= 0.0:
            continue
        total += (a - b) * math.log(a / b)
    return total


def _shares(counts: Sequence[int], floor: float = 1e-6) -> list[float]:
    total = sum(counts)
    if total == 0:
        raise ValueError("cannot form shares from an empty histogram")
    return [max(c / total, floor) for c in counts]


def _merge_thin_bins(reference_counts: list[int], current_counts: list[int], floor: int
                     ) -> tuple[list[int], list[int], int]:
    """
    Merge bins that are thin IN THE REFERENCE, and only there.

    Merging on the current counts as well looks reasonable and is badly wrong:
    when a feature moves far enough that the current window empties most of the
    reference bins, every bin is thin, everything merges into one, and PSI
    reports 0.0 for the largest shift the system will ever see. An empty current
    bin is the finding, not a defect in the binning. The reference defines the
    bins because it is the side that is not supposed to be moving.
    """
    merges = 0
    ref = list(reference_counts)
    cur = list(current_counts)
    i = 0
    while i < len(ref) and len(ref) > 1:
        if ref[i] >= floor:
            i += 1
            continue
        partner = i + 1 if i == 0 else i - 1
        if partner >= len(ref):
            partner = i - 1
        a, b = (i, partner) if i < partner else (partner, i)
        ref = ref[:a] + [ref[a] + ref[b]] + ref[b + 1:]
        cur = cur[:a] + [cur[a] + cur[b]] + cur[b + 1:]
        merges += 1
        i = 0
    return ref, cur, merges


def ks_statistic(a: Sequence[float], b: Sequence[float]) -> float:
    """
    The two-sample Kolmogorov-Smirnov statistic: the maximum absolute difference
    of the two empirical CDFs. Hand-computable on small inputs and asserted
    exactly.
    """
    if not a or not b:
        return 0.0
    sorted_a = sorted(float(v) for v in a)
    sorted_b = sorted(float(v) for v in b)
    values = sorted(set(sorted_a) | set(sorted_b))
    n_a, n_b = len(sorted_a), len(sorted_b)
    statistic = 0.0
    i = j = 0
    for value in values:
        while i < n_a and sorted_a[i] <= value:
            i += 1
        while j < n_b and sorted_b[j] <= value:
            j += 1
        statistic = max(statistic, abs(i / n_a - j / n_b))
    return statistic


def ks_p_value(statistic: float, effective_n: float) -> float:
    """
    The asymptotic Kolmogorov distribution:
    `Q(lambda) = 2 * sum_k (-1)^(k-1) exp(-2 k^2 lambda^2)`.

    Checked against the published critical value: at D = 0.1358 with an
    effective n of 100 this returns 0.050, which is the standard
    one-sample 5% critical value 1.36 / sqrt(n). That number is the external
    ground truth for this function.
    """
    if statistic <= 0.0 or effective_n <= 0.0:
        return 1.0
    lam = math.sqrt(effective_n) * statistic
    total = math.fsum(
        (-1.0) ** (k - 1) * math.exp(-2.0 * k * k * lam * lam) for k in range(1, 101)
    )
    return max(0.0, min(1.0, 2.0 * total))


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """
    Holm's step-down correction.

    Testing thirty features at 0.05 guarantees a false alarm, and a drift
    dashboard that cries wolf every night is one nobody reads. Holm controls the
    family-wise error rate without assuming independence, which matters because
    features in a community dataset are correlated by construction.
    """
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted = [0.0] * n
    running = 0.0
    for rank, index in enumerate(order):
        value = (n - rank) * p_values[index]
        running = max(running, min(1.0, value))
        adjusted[index] = running
    return adjusted


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def psi(reference, current, as_of, *, bins=10, binning="quantile") -> Evidence:
    """drift.psi. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "drift.psi"
    if binning != "quantile":
        raise ValueError(
            "only quantile binning is implemented: equal-width bins on a skewed score put 80% "
            "of the data in one bin, which is the failure mode the Method Card names"
        )
    reference_features = _as_feature_mapping(reference)
    current_features = _as_feature_mapping(current)
    shared = sorted(set(reference_features) & set(current_features))
    if not shared:
        raise ValueError("the reference and current windows share no feature names")
    n_reference = min(len(v) for v in reference_features.values())
    n_current = min(len(v) for v in current_features.values())
    n = min(n_reference, n_current)
    phash = params_hash(method, 1, {
        "bins": bins, "binning": binning, "features": shared,
        "n_reference": n_reference, "n_current": n_current,
    })
    if n_reference < MIN_WINDOW or n_current < MIN_WINDOW:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash,
            caveats=(
                "needs " + str(MIN_WINDOW) + " observations in each window, has "
                + str(n_reference) + " reference and " + str(n_current) + " current",
            ),
        )
    rows = []
    total_merges = 0
    for feature in shared:
        edges = quantile_edges(reference_features[feature], int(bins))
        reference_counts = _histogram(reference_features[feature], edges)
        current_counts = _histogram(current_features[feature], edges)
        reference_counts, current_counts, merges = _merge_thin_bins(
            reference_counts, current_counts, MIN_PER_BIN
        )
        total_merges += merges
        a = _shares(reference_counts)
        b = _shares(current_counts)
        value = psi_from_shares(a, b)
        contributions = [(ai - bi) * math.log(ai / bi) for ai, bi in zip(a, b)]
        top = max(range(len(contributions)), key=lambda i: contributions[i])
        if value >= PSI_SIGNIFICANT:
            verdict = "significant shift"
        elif value >= PSI_INVESTIGATE:
            verdict = "investigate"
        else:
            verdict = "stable"
        rows.append({
            "feature": feature,
            "psi": value,
            "verdict": verdict,
            "top_shifted_bin": top,
            "n": len(current_features[feature]),
            "n_bins": len(a),
        })
    rows.sort(key=lambda r: -r["psi"])
    checks = [
        Check(
            id="bins-populated",
            label="Every bin holds enough observations in both windows",
            status="PASS" if total_merges == 0 else "WARN",
            statistic=float(total_merges),
            detail="" if total_merges == 0 else
            str(total_merges) + " thin bin(s) were merged; a bin of a handful of rows makes PSI "
            "unstable rather than informative",
        ),
        Check(
            id="reference-age",
            label="The reference distribution is recent enough to compare against",
            status="SKIPPED",
            detail="the reference is an artifact of a previous fit supplied by the caller; "
                   "app/stats/ does not fetch it and cannot date it",
        ),
    ]
    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The SAME binning applied to both windows, derived from the reference quantiles "
            "and not recomputed on the current data. Recomputing the bins is the standard "
            "implementation bug and makes PSI approximately zero always.",
            "The reference distribution is supplied by the caller.",
        ),
        checks=tuple(checks),
        caveats=(
            "PSI is a descriptive divergence, not an estimate, so it carries no interval. The "
            "0.1 and 0.25 thresholds are conventions from credit scoring and are not derived "
            "from any distribution; a threshold presented as if it were a p-value is a small lie",
        ),
        params_hash=phash,
    )


def ks_test(reference, current, as_of, *, alpha=0.05) -> Evidence:
    """drift.ks_test. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "drift.ks_test"
    reference_features = _as_feature_mapping(reference)
    current_features = _as_feature_mapping(current)
    shared = sorted(set(reference_features) & set(current_features))
    if not shared:
        raise ValueError("the reference and current windows share no feature names")
    n_reference = min(len(v) for v in reference_features.values())
    n_current = min(len(v) for v in current_features.values())
    n = min(n_reference, n_current)
    phash = params_hash(method, 1, {
        "alpha": alpha, "features": shared,
        "n_reference": n_reference, "n_current": n_current,
    })
    if n_reference < MIN_WINDOW or n_current < MIN_WINDOW:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash,
            caveats=(
                "needs " + str(MIN_WINDOW) + " observations in each window, has "
                + str(n_reference) + " reference and " + str(n_current) + " current",
            ),
        )
    statistics = []
    raw_p = []
    for feature in shared:
        a = reference_features[feature]
        b = current_features[feature]
        statistic = ks_statistic(a, b)
        effective = len(a) * len(b) / (len(a) + len(b))
        statistics.append(statistic)
        raw_p.append(ks_p_value(statistic, effective))
    adjusted = holm_adjust(raw_p)
    rows = []
    for i, feature in enumerate(shared):
        rows.append({
            "feature": feature,
            "statistic": statistics[i],
            "p_value": raw_p[i],
            "p_value_holm": adjusted[i],
            "drifted": adjusted[i] < alpha,
            "n": len(current_features[feature]),
        })
    rows.sort(key=lambda r: r["p_value_holm"])
    drifted = sum(1 for r in rows if r["drifted"])
    ties = any(len(set(current_features[f])) < len(current_features[f]) / 2 for f in shared)
    checks = [
        Check(
            id="multiplicity-controlled",
            label="The p-values are corrected for testing many features at once",
            status="PASS",
            statistic=float(len(shared)),
            detail="Holm correction across " + str(len(shared)) + " features",
        ),
        Check(
            id="continuous-features",
            label="The features are continuous enough for this test",
            status="WARN" if ties else "PASS",
            detail="at least one feature is heavily tied or discrete, which degrades the "
                   "Kolmogorov-Smirnov statistic" if ties else "",
        ),
    ]
    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Continuous features; ties degrade the statistic.",
            "A Holm correction across features, because testing thirty features at 0.05 "
            "guarantees a false alarm.",
        ),
        checks=tuple(checks),
        caveats=(
            str(drifted) + " of " + str(len(rows)) + " features drifted after correction",
            "the statistic is reported alongside the p-value because at a large enough sample "
            "a trivially small shift is significant",
        ),
        params_hash=phash,
    )


def label_shift(reference_labels, current_labels, as_of, *, alpha=0.05) -> Evidence:
    """drift.label_shift. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "drift.label_shift"
    reference = [1 if y else 0 for y in reference_labels]
    current = [1 if y else 0 for y in current_labels]
    n_reference = len(reference)
    n_current = len(current)
    n = n_reference + n_current
    phash = params_hash(method, 1, {
        "alpha": alpha, "n_reference": n_reference, "n_current": n_current,
    })
    if n_reference < MIN_LABELLED or n_current < MIN_LABELLED:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=(
                "needs " + str(MIN_LABELLED) + " labelled outcomes in each window, has "
                + str(n_reference) + " and " + str(n_current),
            ),
        )
    successes_reference = sum(reference)
    successes_current = sum(current)
    rate_reference = successes_reference / n_reference
    rate_current = successes_current / n_current
    lo_reference, hi_reference = wilson_interval(successes_reference, n_reference, alpha=alpha)
    lo_current, hi_current = wilson_interval(successes_current, n_current, alpha=alpha)
    difference_lo, difference_hi = newcombe_difference(
        successes_current, n_current, successes_reference, n_reference, alpha=alpha
    )
    shifted = not (difference_lo <= 0.0 <= difference_hi)
    checks = [
        Check(
            id="base-rate-stable",
            label="The thing being predicted is as common as it was when the model was fitted",
            status="FAIL" if shifted else "PASS",
            statistic=rate_current - rate_reference,
            detail=(
                "the base rate moved from " + ("%.1f%%" % (100 * rate_reference)) + " to "
                + ("%.1f%%" % (100 * rate_current)) + " and the difference interval excludes "
                "zero; a risk model fitted at the old rate is no longer meaningful and "
                "risk.late_payment_risk treats this as blocking"
            ) if shifted else "",
        ),
        Check(
            id="windows-complete",
            label="Neither window is a partial period read as a collapse",
            status="SKIPPED",
            detail="window completeness is the caller's to assert; app/stats/ sees only labels",
        ),
    ]
    return Evidence(
        value={
            "reference_rate": rate_reference,
            "reference_lo": lo_reference,
            "reference_hi": hi_reference,
            "reference_n": n_reference,
            "current_rate": rate_current,
            "current_lo": lo_current,
            "current_hi": hi_current,
            "current_n": n_current,
            "difference": rate_current - rate_reference,
            "difference_lo": difference_lo,
            "difference_hi": difference_hi,
            "shifted": shifted,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval=(difference_lo, difference_hi),
        interval_kind="normal-95" if abs(alpha - 0.05) < 1e-12 else "none",
        assumptions=(
            "The label definition is unchanged between windows.",
            "Both windows are complete, so a partial current window is not read as a collapse.",
        ),
        checks=tuple(checks),
        caveats=(
            "the envelope interval is the Newcombe hybrid-score interval on the DIFFERENCE of "
            "the two rates; each window's own Wilson interval is in the structure",
            "cheap, and it catches the most consequential drift: a risk model fitted when 12% "
            "of dues were late is meaningless once 30% are",
        ),
        unit="probability",
        params_hash=phash,
    )


__all__ = [
    "holm_adjust",
    "ks_p_value",
    "ks_statistic",
    "ks_test",
    "label_shift",
    "psi",
    "psi_from_shares",
    "quantile_edges",
]
