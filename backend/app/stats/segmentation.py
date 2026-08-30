"""
Feature building and clustering over engagement.

The number of segments is never a parameter of this module. It is chosen by BIC
across the declared range, with the silhouette curve computed alongside and
their disagreement reported rather than resolved, because which of the two is
right is a question about the data and not about the code.

The honest uncertainty for a clustering is not an interval, it is whether the
same clustering comes back. Two things are therefore measured and one of them
blocks: a seeded bootstrap adjusted Rand index, and exact reproducibility from
the seed. A segmentation that does not survive resampling is a drawing.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.fairness import hungarian
from app.stats.numeric import mean, percentile

MIN_MEMBERS = 50
STABILITY_FLOOR = 0.5

FEATURE_NAMES = (
    "recency_days",
    "frequency_90d",
    "breadth",
    "volunteer_hours_365d",
    "tenure_days",
    "contribution_minor",
)


# ---------------------------------------------------------------------------
# segmentation.rfm_features
# ---------------------------------------------------------------------------


def _days(later, earlier) -> float:
    return (later - earlier).total_seconds() / 86400.0


def rfm_features(participation, ledger_entries, window) -> Evidence:
    """segmentation.rfm_features. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "segmentation.rfm_features"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
    })
    as_of = getattr(window, "end", None)
    start = getattr(window, "start", None)

    events = [e for e in participation if start <= e.at < as_of]
    entries = [e for e in ledger_entries if start <= e.at < as_of]

    currencies = {getattr(e, "currency", None) for e in entries if getattr(e, "currency", None)}
    if len(currencies) > 1:
        return Evidence(
            value=[],
            n=0,
            method=method,
            as_of=as_of,
            checks=(
                Check(
                    id="single-currency",
                    label="Contributions are all in one currency",
                    status="FAIL",
                    statistic=float(len(currencies)),
                    blocking=True,
                    detail=(
                        "Ledger entries span " + str(len(currencies)) + " currencies ("
                        + ", ".join(sorted(currencies)) + "). Summing them would produce a "
                        "contribution figure that is not an amount of anything, so nothing is "
                        "returned until they are converted upstream."
                    ),
                ),
            ),
            caveats=("Mixed currencies in the ledger. Convert before building features.",),
            unit="members",
            params_hash=phash,
        )

    members = sorted(
        {e.member_ref for e in events}
        | {e.member_ref for e in entries if getattr(e, "member_ref", None)}
    )
    if not members:
        return insufficient(
            method, n=0, as_of=as_of, params_hash=phash, empty_value=[], unit="members",
            caveats=("No participation or ledger activity falls inside this window.",),
        )

    ninety = as_of.timestamp() - 90 * 86400
    year = as_of.timestamp() - 365 * 86400

    rows = []
    for member in members:
        mine = [e for e in events if e.member_ref == member]
        my_entries = [e for e in entries if getattr(e, "member_ref", None) == member]
        stamps = [e.at for e in mine] + [e.at for e in my_entries]
        first_seen = min(stamps)
        tenure = _days(as_of, first_seen)

        if mine:
            recency = _days(as_of, max(e.at for e in mine))
        else:
            # A member with no participation gets their TENURE, not zero and not
            # None. Zero would make the never-engaged look freshly engaged,
            # which is the exact failure this boundary case exists to prevent.
            recency = tenure

        rows.append({
            "member_ref": member,
            "recency_days": recency,
            "frequency_90d": sum(1 for e in mine if e.at.timestamp() >= ninety),
            "breadth": len({e.kind for e in mine}),
            "volunteer_hours_365d": math.fsum(
                float(e.weight) for e in mine
                if e.kind == "volunteer_hours" and e.at.timestamp() >= year
            ),
            "tenure_days": tenure,
            "contribution_minor": int(sum(
                e.amount_minor for e in my_entries if e.amount_minor > 0
            )),
            "channels": sorted({e.channel for e in mine if getattr(e, "channel", None)}),
            "strata": dict(getattr(mine[-1], "strata", {}) or {}) if mine else {},
            "n": len(mine) + len(my_entries),
        })

    lag = getattr(window, "reporting_lag_days", 0.0)
    return Evidence(
        value=rows,
        n=len(rows),
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The window bounds every feature, so no feature is computed from data outside it.",
            "Tenure is measured from a member's first ATOM inside the window, so anyone who "
            "joined before it opened is left truncated and their tenure understated.",
        ),
        checks=(
            Check(
                id="single-currency",
                label="Contributions are all in one currency",
                status="PASS",
                statistic=float(len(currencies) or 1),
            ),
            Check(
                id="window-complete",
                label="The window is complete through its end",
                status="WARN" if lag > 1.0 else "PASS",
                statistic=lag,
                detail=(
                    "Data is believed complete only through " + "{:.1f}".format(lag)
                    + " days before the window end, so recency is measured against a boundary "
                    "the pipeline has not caught up to."
                ) if lag > 1.0 else "",
            ),
        ),
        caveats=(
            "A feature builder, not an estimator. It returns Evidence because everything "
            "crossing this boundary does, not because anything here is uncertain.",
            "A member with no participation carries recency equal to their tenure. Reading "
            "that as a recent visit would invert the meaning of the whole table.",
        ),
        unit="members",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# Scaling, mixtures and model selection
# ---------------------------------------------------------------------------


def robust_scale(matrix: Sequence[Sequence[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    """
    Median and interquartile scaling, per column.

    Mandatory rather than optional: volunteer hours and login counts differ by
    orders of magnitude, and an unscaled mixture clusters on whichever column
    happens to have the largest variance. A column with no spread is left alone
    rather than divided by zero, and contributes nothing to any distance.
    """
    if not matrix:
        return [], [], []
    p = len(matrix[0])
    centres, scales = [], []
    for j in range(p):
        column = sorted(row[j] for row in matrix)
        centre = percentile(column, 0.5)
        spread = percentile(column, 0.75) - percentile(column, 0.25)
        centres.append(centre)
        scales.append(spread if spread > 1e-12 else 1.0)
    scaled = [
        [(row[j] - centres[j]) / scales[j] for j in range(p)]
        for row in matrix
    ]
    return scaled, centres, scales


def _kmeans_plus_plus(points, k, rng):
    centroids = [list(points[rng.randrange(len(points))])]
    while len(centroids) < k:
        distances = [
            min(math.fsum((a - b) ** 2 for a, b in zip(point, c)) for c in centroids)
            for point in points
        ]
        total = math.fsum(distances)
        if total <= 0:
            centroids.append(list(points[rng.randrange(len(points))]))
            continue
        target = rng.random() * total
        running = 0.0
        for index, d in enumerate(distances):
            running += d
            if running >= target:
                centroids.append(list(points[index]))
                break
    return centroids


def gaussian_mixture(points: Sequence[Sequence[float]], k: int, *, seed: int,
                     covariance: str = "diag", n_init: int = 10, max_iter: int = 200):
    """
    Expectation maximisation for a Gaussian mixture, diagonal or full.

    Restarted `n_init` times from seeded k-means++ initialisations and the best
    log-likelihood kept, because EM finds a local optimum and one run of it is a
    coin flip dressed as a model.
    """
    n = len(points)
    p = len(points[0])
    best = None
    floor = 1e-6

    for restart in range(n_init):
        rng = random.Random(seed * 1000 + restart)
        means = _kmeans_plus_plus(points, k, rng)
        weights = [1.0 / k] * k
        if covariance == "full":
            variances = [[[1.0 if a == b else 0.0 for b in range(p)] for a in range(p)]
                         for _ in range(k)]
        else:
            variances = [[1.0] * p for _ in range(k)]
        loglik = -float("inf")

        for _ in range(max_iter):
            # E step, in log space so a far point does not underflow to zero
            # responsibility across every component at once.
            log_resp = []
            total_loglik = 0.0
            for point in points:
                logs = []
                for c in range(k):
                    if covariance == "full":
                        density = _log_normal_full(point, means[c], variances[c])
                    else:
                        density = _log_normal_diag(point, means[c], variances[c])
                    logs.append(math.log(max(weights[c], 1e-300)) + density)
                peak = max(logs)
                denominator = peak + math.log(math.fsum(math.exp(v - peak) for v in logs))
                total_loglik += denominator
                log_resp.append([v - denominator for v in logs])

            if abs(total_loglik - loglik) < 1e-7 * max(1.0, abs(loglik)):
                loglik = total_loglik
                break
            loglik = total_loglik

            # M step.
            for c in range(k):
                r = [math.exp(row[c]) for row in log_resp]
                mass = math.fsum(r)
                if mass < 1e-9:
                    rng2 = random.Random(seed * 7919 + restart * 31 + c)
                    means[c] = list(points[rng2.randrange(n)])
                    weights[c] = 1.0 / k
                    continue
                weights[c] = mass / n
                means[c] = [math.fsum(r[i] * points[i][j] for i in range(n)) / mass
                            for j in range(p)]
                if covariance == "full":
                    matrix = [[0.0] * p for _ in range(p)]
                    for i in range(n):
                        d = [points[i][j] - means[c][j] for j in range(p)]
                        for a in range(p):
                            for b in range(p):
                                matrix[a][b] += r[i] * d[a] * d[b]
                    for a in range(p):
                        for b in range(p):
                            matrix[a][b] /= mass
                        matrix[a][a] += floor
                    variances[c] = matrix
                else:
                    variances[c] = [
                        max(math.fsum(r[i] * (points[i][j] - means[c][j]) ** 2
                                      for i in range(n)) / mass, floor)
                        for j in range(p)
                    ]

        labels = [max(range(k), key=lambda c: row[c]) for row in log_resp]
        if best is None or loglik > best[0]:
            best = (loglik, means, variances, weights, labels)

    loglik, means, variances, weights, labels = best
    if covariance == "full":
        free = k - 1 + k * p + k * p * (p + 1) // 2
    else:
        free = k - 1 + k * p + k * p
    bic = -2.0 * loglik + free * math.log(n)
    return {"loglik": loglik, "bic": bic, "means": means, "variances": variances,
            "weights": weights, "labels": labels, "free_parameters": free}


def _log_normal_diag(point, mean_vector, variances) -> float:
    total = 0.0
    for j, value in enumerate(point):
        v = max(variances[j], 1e-12)
        total += -0.5 * (math.log(2 * math.pi * v) + (value - mean_vector[j]) ** 2 / v)
    return total


def _log_normal_full(point, mean_vector, matrix) -> float:
    from app.stats.numeric import inverse

    p = len(point)
    try:
        precision = inverse(matrix)
    except (ValueError, ZeroDivisionError):
        return -1e12
    determinant = _determinant(matrix)
    if determinant <= 0:
        return -1e12
    d = [point[j] - mean_vector[j] for j in range(p)]
    quadratic = math.fsum(d[a] * precision[a][b] * d[b] for a in range(p) for b in range(p))
    return -0.5 * (p * math.log(2 * math.pi) + math.log(determinant) + quadratic)


def _determinant(matrix) -> float:
    n = len(matrix)
    work = [list(row) for row in matrix]
    result = 1.0
    for i in range(n):
        pivot = max(range(i, n), key=lambda r: abs(work[r][i]))
        if abs(work[pivot][i]) < 1e-300:
            return 0.0
        if pivot != i:
            work[i], work[pivot] = work[pivot], work[i]
            result = -result
        result *= work[i][i]
        for r in range(i + 1, n):
            factor = work[r][i] / work[i][i]
            for c in range(i, n):
                work[r][c] -= factor * work[i][c]
    return result


def silhouette(points: Sequence[Sequence[float]], labels: Sequence[int]) -> float:
    """
    Rousseeuw (1987), mean over points of (b - a) / max(a, b).

    a is the mean distance to the point's own cluster, b the smallest mean
    distance to any other. A singleton cluster scores 0 by convention, which is
    the standard definition and matters here because singletons are common in
    engagement data.
    """
    n = len(points)
    clusters: dict[int, list[int]] = {}
    for i, label in enumerate(labels):
        clusters.setdefault(label, []).append(i)
    if len(clusters) < 2:
        return 0.0

    def distance(i, j):
        return math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(points[i], points[j])))

    scores = []
    for i in range(n):
        own = clusters[labels[i]]
        if len(own) == 1:
            scores.append(0.0)
            continue
        a = math.fsum(distance(i, j) for j in own if j != i) / (len(own) - 1)
        b = min(
            math.fsum(distance(i, j) for j in members) / len(members)
            for label, members in clusters.items()
            if label != labels[i]
        )
        scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return mean(scores)


def adjusted_rand(a: Sequence[int], b: Sequence[int]) -> float:
    """Hubert and Arabie's adjusted Rand index. 1.0 is exact agreement, 0.0 is chance."""
    if len(a) < 2:
        return 1.0
    table: dict[tuple[int, int], int] = {}
    rows: dict[int, int] = {}
    cols: dict[int, int] = {}
    for x, y in zip(a, b):
        table[(x, y)] = table.get((x, y), 0) + 1
        rows[x] = rows.get(x, 0) + 1
        cols[y] = cols.get(y, 0) + 1

    def choose2(v):
        return v * (v - 1) / 2.0

    total = choose2(len(a))
    index = math.fsum(choose2(v) for v in table.values())
    row_sum = math.fsum(choose2(v) for v in rows.values())
    col_sum = math.fsum(choose2(v) for v in cols.values())
    expected = row_sum * col_sum / total if total else 0.0
    maximum = (row_sum + col_sum) / 2.0
    if abs(maximum - expected) < 1e-15:
        return 1.0
    return (index - expected) / (maximum - expected)


def _matrix_from(features) -> tuple[list[list[float]], list[str], list[Mapping[str, str]]]:
    matrix, refs, strata = [], [], []
    for row in features:
        if isinstance(row, Mapping):
            values = [float(row.get(name, 0.0)) for name in FEATURE_NAMES]
            refs.append(str(row.get("member_ref")))
            strata.append(dict(row.get("strata", {}) or {}))
        else:
            values = [float(getattr(row, name, 0.0)) for name in FEATURE_NAMES]
            refs.append(str(getattr(row, "member_ref", None)))
            strata.append(dict(getattr(row, "strata", {}) or {}))
        matrix.append(values)
    return matrix, refs, strata


def gmm_select_k(features, window, *, seed, k_range=(2, 9), covariance="diag", n_init=10,
                 scale="robust", k_anonymity=5) -> Evidence:
    """segmentation.gmm_select_k. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "segmentation.gmm_select_k"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "seed": seed, "k_range": list(k_range), "covariance": covariance, "n_init": n_init,
        "scale": scale, "k_anonymity": k_anonymity,
    })
    as_of = getattr(window, "end", None)

    matrix, refs, strata = _matrix_from(features)
    n = len(matrix)
    empty = {"k": None, "bic_by_k": {}, "silhouette_by_k": {}, "labels": {},
             "centroids": [], "sizes": [], "separation": None}

    if scale != "robust":
        return Evidence(
            value=empty, n=n, method=method, as_of=as_of,
            checks=(
                Check(
                    id="feature-scaling",
                    label="Features are on a comparable scale before clustering",
                    status="FAIL",
                    blocking=True,
                    detail=(
                        "Robust scaling is mandatory here and " + repr(scale) + " was asked "
                        "for. Volunteer hours and login counts differ by orders of magnitude, "
                        "so an unscaled mixture clusters on the largest-variance column alone "
                        "and the segments describe that column rather than engagement."
                    ),
                ),
            ),
            caveats=("Unscaled clustering is refused rather than run.",),
            unit="segments", params_hash=phash,
        )

    if n < MIN_MEMBERS:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="segments",
            caveats=(
                "Needs " + str(MIN_MEMBERS) + " members; has " + str(n) + ". Below that, "
                "cluster structure is indistinguishable from noise and BIC will still return a "
                "k with every appearance of confidence.",
            ),
        )

    scaled, centres, scales = robust_scale(matrix)

    # A column with no spread cannot separate anyone, but it still costs a mean
    # and a variance per component in the BIC penalty. Left in, four dead
    # columns roughly triple the price of each extra component and BIC starts
    # preferring too few segments for reasons that have nothing to do with the
    # data. Dropped here, and named in a caveat so the reader knows which
    # features the segments actually rest on.
    live = [
        j for j in range(len(FEATURE_NAMES))
        if len({round(row[j], 12) for row in scaled}) > 1
    ]
    dropped = [FEATURE_NAMES[j] for j in range(len(FEATURE_NAMES)) if j not in live]
    if not live:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="segments",
            caveats=(
                "Every engagement feature is constant across these members, so there is "
                "nothing to segment on. That is a finding about the data, not a failure.",
            ),
        )
    points = [[row[j] for j in live] for row in scaled]

    lo, hi = int(k_range[0]), int(k_range[1])
    candidates = [k for k in range(lo, hi) if k < n]
    if not candidates:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="segments",
            caveats=("The declared k range " + repr(tuple(k_range)) + " contains no usable k.",),
        )

    fits = {k: gaussian_mixture(points, k, seed=seed, covariance=covariance, n_init=n_init)
            for k in candidates}
    bic_by_k = {k: fits[k]["bic"] for k in candidates}
    silhouette_by_k = {k: silhouette(points, fits[k]["labels"]) for k in candidates}

    # k comes from BIC. It is never a parameter of this service and never a
    # constant in this file.
    chosen = min(candidates, key=lambda k: (bic_by_k[k], k))
    silhouette_choice = max(candidates, key=lambda k: (silhouette_by_k[k], -k))
    fit = fits[chosen]
    labels = list(fit["labels"])

    # Stability by seeded bootstrap: refit a resample and compare on the points
    # both fits saw.
    stability_scores = []
    for replicate in range(10):
        rng = random.Random(seed * 977 + replicate)
        indices = sorted({rng.randrange(n) for _ in range(n)})
        if len(indices) < chosen * 2:
            continue
        subset = [points[i] for i in indices]
        refit = gaussian_mixture(subset, chosen, seed=seed + replicate,
                                 covariance=covariance, n_init=max(2, n_init // 3))
        stability_scores.append(
            adjusted_rand([labels[i] for i in indices], refit["labels"])
        )
    stability = mean(stability_scores) if stability_scores else 0.0

    sizes: dict[int, int] = {}
    for label in labels:
        sizes[label] = sizes.get(label, 0) + 1

    # Clusters below the tenant floor are merged into their nearest neighbour
    # rather than published as a group of three people.
    merged: list[int] = []
    centroids = [list(m) for m in fit["means"]]
    for label in sorted(sizes, key=lambda c: sizes[c]):
        if sizes.get(label, 0) >= k_anonymity or len(sizes) <= 2:
            continue
        others = [c for c in sizes if c != label]
        nearest = min(
            others,
            key=lambda c: math.fsum(
                (a - b) ** 2 for a, b in zip(centroids[label], centroids[c])
            ),
        )
        labels = [nearest if v == label else v for v in labels]
        sizes[nearest] = sizes.get(nearest, 0) + sizes.pop(label)
        merged.append(label)

    remaining = sorted(sizes)
    relabel = {old: new for new, old in enumerate(remaining)}
    labels = [relabel[v] for v in labels]
    final_centroids = []
    for old in remaining:
        members = [i for i in range(n) if labels[i] == relabel[old]]
        final_centroids.append([
            mean([points[i][j] for i in members]) for j in range(len(points[0]))
        ])

    separation = None
    if len(final_centroids) >= 2:
        separation = min(
            math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(final_centroids[i], final_centroids[j])))
            for i in range(len(final_centroids))
            for j in range(i + 1, len(final_centroids))
        )

    checks = [
        Check(
            id="feature-scaling",
            label="Features are on a comparable scale before clustering",
            status="PASS",
            statistic=float(len(FEATURE_NAMES)),
            detail="Robust median and interquartile scaling, which is mandatory here.",
        ),
        Check(
            id="k-selection-agreement",
            label="BIC and silhouette agree on how many segments there are",
            status="PASS" if chosen == silhouette_choice else "WARN",
            statistic=float(chosen),
            detail=(
                "BIC is minimised at k = " + str(chosen) + " and silhouette peaks at k = "
                + str(silhouette_choice) + ". That disagreement is itself the finding and both "
                "curves are returned rather than one of them being picked as the answer. BIC "
                "chose the served partition."
            ) if chosen != silhouette_choice else "",
        ),
        Check(
            id="cluster-stability",
            label="Whether the same segments come back under resampling",
            status="PASS" if stability >= 0.7 else (
                "WARN" if stability >= STABILITY_FLOOR else "FAIL"
            ),
            statistic=stability,
            blocking=stability < STABILITY_FLOOR,
            detail=(
                "Bootstrap adjusted Rand index " + "{:.2f}".format(stability) + ", below "
                + str(STABILITY_FLOOR) + ". A clustering that does not survive resampling is a "
                "drawing, not a segmentation, and the labels are not published."
            ) if stability < STABILITY_FLOOR else (
                "Bootstrap adjusted Rand index " + "{:.2f}".format(stability) + ". Engagement "
                "is usually a continuum, so these are cuts through a gradient and will move "
                "between months; this number is how much."
            ) if stability < 0.7 else "",
        ),
        Check(
            id="singleton-clusters",
            label="No segment describes fewer than k members",
            status="FAIL" if merged else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(len(merged)) + " segments held fewer than " + str(k_anonymity)
                + " members and were merged into their nearest neighbour rather than labelled."
            ) if merged else "",
        ),
    ]

    value = {
        "k": len(final_centroids),
        "k_from_bic": chosen,
        "k_from_silhouette": silhouette_choice,
        "bic_by_k": bic_by_k,
        "silhouette_by_k": silhouette_by_k,
        "labels": {refs[i]: labels[i] for i in range(n)},
        "centroids": final_centroids,
        "centroid_scale": {"centres": centres, "scales": scales,
                           "features": [FEATURE_NAMES[j] for j in live]},
        "features_used": [FEATURE_NAMES[j] for j in live],
        "features_dropped": dropped,
        "sizes": [sum(1 for v in labels if v == c) for c in range(len(final_centroids))],
        "separation": separation,
        "stability": stability,
        "n_merged": len(merged),
    }
    if stability < STABILITY_FLOOR:
        value = {**value, "labels": {}, "centroids": [], "sizes": []}

    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Clusters are roughly elliptical in the scaled feature space.",
            "Robust scaling is applied, which is mandatory rather than a default.",
        ),
        checks=tuple(checks),
        caveats=(
            "The labels carry no interval, because a label is not an estimate. The bootstrap "
            "adjusted Rand index is the honest uncertainty measure and belongs next to the "
            "segments always.",
            "The number of segments was chosen by BIC across k in " + repr(tuple(k_range))
            + ", not set by hand. The silhouette curve is returned so the choice is visible.",
        ) + ((
            "These segments rest on " + ", ".join(FEATURE_NAMES[j] for j in live) + ". "
            + ", ".join(dropped) + " were identical for every member here and were dropped, "
            "since a feature that does not vary cannot tell anyone apart.",
        ) if dropped else ()),
        unit="segments",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# segmentation.stable_labels
# ---------------------------------------------------------------------------


def stable_labels(current_labels, current_centroids, reference_labels, reference_centroids,
                  as_of, *, drift_threshold=0.5) -> Evidence:
    """segmentation.stable_labels. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "segmentation.stable_labels"
    phash = params_hash(method, 1, {"drift_threshold": drift_threshold})

    current = [list(map(float, c)) for c in current_centroids]
    reference = [list(map(float, c)) for c in reference_centroids]
    n = len(current_labels)

    if not current or not reference:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash,
            empty_value={"mapping": {}, "match_cost": None, "labels": {}},
            unit="segments",
            caveats=("Both runs must have produced at least one segment to match.",),
        )

    # Hungarian on centroid distance. Matching on label overlap instead would
    # make the answer depend on who happened to move house.
    rows, cols = len(current), len(reference)
    size = max(rows, cols)
    big = max(
        math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(x, y)))
        for x in current for y in reference
    ) + 1.0
    cost = [
        [
            math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(current[i], reference[j])))
            if i < rows and j < cols else big
            for j in range(size)
        ]
        for i in range(size)
    ]
    assignment = hungarian(cost)

    mapping: dict[int, int] = {}
    matched_costs = []
    for i in range(rows):
        j = assignment[i]
        if j < cols:
            mapping[i] = j
            matched_costs.append(cost[i][j])
    match_cost = mean(matched_costs) if matched_costs else float("inf")
    unmatched = rows - len(mapping)

    drifted = match_cost > drift_threshold
    relabelled = {
        ref: mapping.get(label, None)
        for ref, label in dict(current_labels).items()
    }

    checks = [
        Check(
            id="label-drift",
            label="Whether this month's segments are still last month's segments",
            status="FAIL" if drifted else "PASS",
            statistic=match_cost,
            blocking=drifted,
            detail=(
                "The best centroid match costs " + "{:.3f}".format(match_cost) + ", above the "
                "threshold of " + str(drift_threshold) + ". The segments genuinely changed, so "
                "no mapping is published: calling this month's group 3 the same as last "
                "month's would be worse than renumbering them and saying so."
            ) if drifted else "",
        ),
        Check(
            id="segment-count-stable",
            label="Both runs found the same number of segments",
            status="PASS" if rows == cols else "WARN",
            statistic=float(rows - cols),
            detail=(
                "This run found " + str(rows) + " segments against " + str(cols) + " last time, "
                "so " + str(abs(rows - cols)) + " have no counterpart at all."
            ) if rows != cols else "",
        ),
        Check(
            id="unmatched-segments",
            label="Segments with no counterpart in the reference run",
            status="WARN" if unmatched else "PASS",
            statistic=float(unmatched),
            detail=(
                str(unmatched) + " segments could not be matched and keep new numbers."
            ) if unmatched else "",
        ),
    ]

    value = {
        "mapping": mapping,
        "match_cost": match_cost,
        "labels": relabelled,
        "n_unmatched": unmatched,
        "is_identity": all(k == v for k, v in mapping.items()) and rows == cols,
    }
    if drifted:
        value = {**value, "mapping": {}, "labels": {}}

    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The two runs describe the same population with the same features on the same "
            "scaling. A change of scaling moves every centroid and this service cannot see it.",
            "Matching is on centroids by the Hungarian algorithm, not on label overlap.",
        ),
        checks=tuple(checks),
        caveats=(
            "A matching procedure, not an estimator. There is no interval on a permutation.",
        ),
        unit="segments",
        params_hash=phash,
    )


__all__ = [
    "adjusted_rand",
    "gaussian_mixture",
    "gmm_select_k",
    "rfm_features",
    "robust_scale",
    "silhouette",
    "stable_labels",
]
