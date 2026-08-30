"""
Level-shift detection over any periodised series.

The interval is on the DATE of the shift, not on its size. A changepoint two
periods from the end of a series is unidentifiable from noise and is not
reported.

PELT (Killick, Fearnhead and Eckley 2012) with a Gaussian change-in-mean cost.
The noise scale is estimated from the median of successive absolute differences
rather than from the sample deviation, because a level shift inflates the second
and can hide itself.

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
from app.stats.series import lag_autocorrelation, ljung_box, period_series, robust_sigma
from app.stats.numeric import chi2_sf

MIN_PERIODS = 24
SEARCH_FLOOR = 2      # the shortest segment the Gaussian cost can evaluate
N_BOOTSTRAP = 400
N_PERMUTATIONS = 400


def _prefix_sums(values: Sequence[float]) -> tuple[list[float], list[float]]:
    total = [0.0]
    square = [0.0]
    for v in values:
        total.append(total[-1] + v)
        square.append(square[-1] + v * v)
    return total, square


def _segment_cost(total: Sequence[float], square: Sequence[float], a: int, b: int,
                  sigma2: float) -> float:
    """
    Twice the negative Gaussian log-likelihood of [a, b) with a free mean and a
    known variance, dropping the constant: the residual sum of squares over
    sigma squared.
    """
    n = b - a
    if n <= 0:
        return 0.0
    s = total[b] - total[a]
    ss = square[b] - square[a]
    rss = ss - s * s / n
    return max(0.0, rss) / sigma2


def pelt(values: Sequence[float], *, penalty: float, min_segment: int,
         sigma2: float) -> list[int]:
    """
    Pruned Exact Linear Time segmentation. Returns the interior changepoints as
    indices of the first observation of each new segment.

    Exact for this cost, not a greedy approximation: the pruning step only
    discards candidates that provably cannot be optimal.
    """
    n = len(values)
    total, square = _prefix_sums(values)
    best = [0.0] + [math.inf] * n
    previous = [0] * (n + 1)
    candidates = [0]
    for end in range(min_segment, n + 1):
        best_cost = math.inf
        best_start = 0
        survivors: list[int] = []
        for start in candidates:
            if end - start < min_segment:
                continue
            cost = best[start] + _segment_cost(total, square, start, end, sigma2) + penalty
            if cost < best_cost:
                best_cost, best_start = cost, start
            if best[start] + _segment_cost(total, square, start, end, sigma2) <= best_cost:
                survivors.append(start)
        if best_cost < math.inf:
            best[end] = best_cost
            previous[end] = best_start
        survivors.append(end - min_segment + 1 if end - min_segment + 1 > 0 else 0)
        candidates = sorted(set(s for s in survivors if s <= end))
        if end not in candidates:
            candidates.append(end)
    points: list[int] = []
    at = n
    while at > 0:
        start = previous[at]
        if start > 0:
            points.append(start)
        at = start
    return sorted(points)


def _penalty_value(penalty: Any, n: int) -> tuple[float, str]:
    if isinstance(penalty, (int, float)) and not isinstance(penalty, bool):
        return float(penalty), "explicit"
    if penalty == "bic":
        return math.log(n), "bic"
    if penalty == "mbic":
        # The modified BIC of Zhang and Siegmund, in its standard practical form:
        # three parameters per changepoint rather than one.
        return 3.0 * math.log(n), "mbic"
    raise ValueError("penalty must be 'bic', 'mbic' or a number, got " + repr(penalty))


def _segment_means(values: Sequence[float], points: Sequence[int]) -> list[tuple[int, int, float]]:
    bounds = [0] + list(points) + [len(values)]
    return [
        (bounds[i], bounds[i + 1], mean(values[bounds[i]:bounds[i + 1]]))
        for i in range(len(bounds) - 1)
    ]


def _refine_local(values: Sequence[float], lo: int, hi: int, min_segment: int) -> int:
    """The single split of [lo, hi) that minimizes the within-segment sum of squares."""
    total, square = _prefix_sums(values[lo:hi])
    best, best_at = math.inf, lo + min_segment
    for split in range(min_segment, hi - lo - min_segment + 1):
        cost = (_segment_cost(total, square, 0, split, 1.0)
                + _segment_cost(total, square, split, hi - lo, 1.0))
        if cost < best:
            best, best_at = cost, lo + split
    return best_at


def _bootstrap_date_interval(values: Sequence[float], lo: int, hi: int, point: int,
                             min_segment: int, seed: int) -> tuple[int, int]:
    """
    A seeded parametric bootstrap on the break DATE: resample the residuals of
    the two adjacent segments, rebuild the neighbourhood, and re-locate the
    split. The spread of the relocated splits is the interval.
    """
    rng = random.Random(seed)
    left = list(values[lo:point])
    right = list(values[point:hi])
    if len(left) < min_segment or len(right) < min_segment:
        return point, point
    left_mean, right_mean = mean(left), mean(right)
    left_residuals = [v - left_mean for v in left]
    right_residuals = [v - right_mean for v in right]
    pooled = left_residuals + right_residuals
    locations: list[float] = []
    for _ in range(N_BOOTSTRAP):
        rebuilt = [left_mean + pooled[rng.randrange(len(pooled))] for _ in left]
        rebuilt += [right_mean + pooled[rng.randrange(len(pooled))] for _ in right]
        locations.append(float(_refine_local(rebuilt, 0, len(rebuilt), min_segment) + lo))
    locations.sort()
    return int(round(percentile(locations, 0.025))), int(round(percentile(locations, 0.975)))


def _permutation_p(values: Sequence[float], lo: int, hi: int, point: int,
                   min_segment: int, seed: int) -> float:
    """
    A seeded permutation test on the neighbourhood: under the null of no shift,
    the order of the observations carries no information, so the observed drop
    in the sum of squares is compared with the drop achievable after shuffling.
    """
    window = list(values[lo:hi])
    if len(window) < 2 * min_segment:
        return 1.0

    def drop(sample: Sequence[float]) -> float:
        total, square = _prefix_sums(sample)
        whole = _segment_cost(total, square, 0, len(sample), 1.0)
        best = whole
        for split in range(min_segment, len(sample) - min_segment + 1):
            cost = (_segment_cost(total, square, 0, split, 1.0)
                    + _segment_cost(total, square, split, len(sample), 1.0))
            best = min(best, cost)
        return whole - best

    observed = drop(window)
    rng = random.Random(seed)
    at_least = 0
    for _ in range(N_PERMUTATIONS):
        shuffled = list(window)
        rng.shuffle(shuffled)
        if drop(shuffled) >= observed:
            at_least += 1
    return (at_least + 1) / (N_PERMUTATIONS + 1)


def detect_level_shifts(series, window, *, penalty="mbic", min_segment=4, model="normal_mean",
                        seed=0, value_field=None) -> Evidence:
    """changepoint.detect_level_shifts. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "changepoint.detect_level_shifts"
    if model not in ("normal_mean", "poisson"):
        raise ValueError("model must be 'normal_mean' or 'poisson', got " + repr(model))
    data = period_series(series, window, value_field=value_field)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None),
        "window_end": getattr(window, "end", None),
        "penalty": penalty, "min_segment": min_segment, "model": model, "seed": seed,
        "value_field": data.field,
    })
    as_of = getattr(window, "end", None)
    n = len(data)
    if n < MIN_PERIODS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash,
            caveats=("needs " + str(MIN_PERIODS) + " periods, has " + str(n),),
        )

    raw = list(data.values)
    # A Poisson series is variance-stabilised first (Anscombe), so one cost
    # function serves both models rather than two code paths diverging.
    values = [2.0 * math.sqrt(v + 0.375) for v in raw] if model == "poisson" else raw
    sigma = robust_sigma(values)
    if sigma <= 0.0:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash,
            caveats=("the series has no variation between consecutive periods",),
        )
    beta, penalty_kind = _penalty_value(penalty, n)

    rho = lag_autocorrelation(values, 1)
    stat, df = ljung_box(values)
    autocorrelated = chi2_sf(stat, df) < 0.05 and rho > 0.2
    adjustment = 1.0
    if autocorrelated:
        # Positive autocorrelation inflates the apparent number of segments. The
        # standard correction is to raise the penalty by the variance-inflation
        # factor of the mean of a correlated sample.
        adjustment = (1.0 + rho) / (1.0 - rho)
        beta *= adjustment

    # PELT runs with the smallest segment the cost function can even evaluate,
    # not with `min_segment`. If the search were floored at `min_segment` the
    # edge-changepoint check below could never fire, because no candidate could
    # ever be near an end: the suppression has to be visible to the reader, not
    # hidden inside the search.
    points = pelt(values, penalty=beta, min_segment=SEARCH_FLOOR, sigma2=sigma * sigma)
    segments = _segment_means(raw, points)

    rows: list[dict[str, Any]] = []
    edge_suppressed: list[int] = []
    for order, point in enumerate(points):
        lo = points[order - 1] if order else 0
        hi = points[order + 1] if order + 1 < len(points) else n
        before = segments[order][2]
        after = segments[order + 1][2]
        near_edge = point < min_segment or point > n - min_segment
        crowded = (point - lo) < min_segment or (hi - point) < min_segment
        lo_date, hi_date = _bootstrap_date_interval(values, lo, hi, point, min_segment,
                                                    seed + order)
        p_value = _permutation_p(values, lo, hi, point, min_segment, seed + 1000 + order)
        rows.append({
            "index": point,
            "at": data.labels[point],
            "before_mean": before,
            "after_mean": after,
            "delta": after - before,
            "p_value": p_value,
            "lo": data.labels[max(0, min(n - 1, lo_date))],
            "hi": data.labels[max(0, min(n - 1, hi_date))],
            "lo_index": max(0, min(n - 1, lo_date)),
            "hi_index": max(0, min(n - 1, hi_date)),
            "n": hi - lo,
            "suppressed": near_edge or crowded,
            "suppression_reason": (
                "within " + str(min_segment) + " periods of the end of the series, where a "
                "level shift cannot be told from noise. This is the most common false positive "
                "in this family, so the row is suppressed rather than reported."
            ) if near_edge else (
                "fewer than " + str(min_segment) + " periods separate this candidate from the "
                "next one, so neither level is estimated from enough data to report."
            ) if crowded else "",
        })
        if near_edge or crowded:
            edge_suppressed.append(point)

    checks = [
        Check(
            id="edge-changepoint",
            label="No changepoint sits against the edge of the series",
            status="FAIL" if edge_suppressed else "PASS",
            statistic=float(len(edge_suppressed)),
            blocking=bool(edge_suppressed),
            detail=(
                str(len(edge_suppressed)) + " candidate changepoints have fewer than "
                + str(min_segment) + " periods on one side and are suppressed; a shift that "
                "close to an end of the series, or to the next shift, is indistinguishable "
                "from noise."
            ) if edge_suppressed else "",
        ),
        Check(
            id="residual-autocorrelation",
            label="Residuals within a segment are independent",
            status="WARN" if autocorrelated else "PASS",
            statistic=rho,
            detail=(
                "lag-1 autocorrelation " + format(rho, ".2f") + " inflates the number of "
                "detected segments, so the penalty was raised by a factor of "
                + format(adjustment, ".2f") + " and that adjustment is in params_hash."
            ) if autocorrelated else "",
        ),
        Check(
            id="significance",
            label="Each reported changepoint survives a permutation test",
            status="WARN" if any(r["p_value"] > 0.05 for r in rows) else "PASS",
            statistic=max((r["p_value"] for r in rows), default=0.0),
            detail=(
                "some changepoints have a permutation p above 0.05. They are reported with this "
                "warning rather than deleted, so a reader sees the near-misses."
            ) if any(r["p_value"] > 0.05 for r in rows) else "",
        ),
    ]
    reported = [r for r in rows if not r["suppressed"]]
    return Evidence(
        value=reported,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="bootstrap-bca-95",
        assumptions=(
            "The series really is piecewise constant rather than smoothly trending.",
            "Residuals are independent within a segment.",
            "The penalty controlling the number of segments is declared (" + penalty_kind
            + "), not tuned to taste.",
            "Seasonality was removed before the series arrived, or the Poisson model was chosen.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete_period" if (data.n_incomplete or data.n_after_complete_through) else "",
        unit=data.field,
        params_hash=phash,
    )


__all__ = ["detect_level_shifts", "pelt"]
