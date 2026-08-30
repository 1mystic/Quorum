"""
Survey analysis over ordinal responses.

There is nowhere in this module to put the mean of a 1 to 5 Likert item, and that is
deliberate: survey.likert_distribution returns a structure with no mean key.

`ordinal_logistic` is the Cox model's twin. Proportional odds is to an odds
ratio what proportional hazards is to a hazard ratio: if it fails, there is no
single number to report, only a different number at each cutpoint. The Brant
test measures it, per covariate, and a covariate that fails has its row emptied
and replaced by the per-cutpoint effects. That is a blocking check in the full
sense: the value goes.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import (
    bootstrap_bca,
    chi2_sf,
    inverse,
    mean,
    norm_ppf,
    percentile,
    solve,
)

MIN_LIKERT = 20
MIN_ORDINAL = 100
MIN_RAKING = 50
MIN_CELL = 5
SPARSE_LEVEL = 5
DEFF_WARN = 2.0


# ---------------------------------------------------------------------------
# Cliff's delta
# ---------------------------------------------------------------------------


def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """
    (# a > b minus # a < b) over all pairs, divided by mn.

    A probability-of-superiority effect size, and the right one for ordinal
    data because it never touches the spacing between levels. Its identity with
    the Mann-Whitney U statistic, delta = 2U/(mn) - 1, is asserted in the tests.
    """
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        raise ValueError("Cliff's delta needs two non-empty samples")
    greater = 0
    less = 0
    for x in a:
        for y in b:
            if x > y:
                greater += 1
            elif x < y:
                less += 1
    return (greater - less) / (m * n)


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> float:
    """U with the usual half-credit for ties. Here so the identity has two sides."""
    total = 0.0
    for x in a:
        for y in b:
            if x > y:
                total += 1.0
            elif x == y:
                total += 0.5
    return total


# ---------------------------------------------------------------------------
# survey.likert_distribution
# ---------------------------------------------------------------------------


def _responses_for(responses, item_id):
    return [r for r in responses if getattr(r, "item_id", None) == item_id]


def likert_distribution(responses, as_of, *, item_id, group_by=None, k_anonymity=5,
                        seed=0) -> Evidence:
    """survey.likert_distribution. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survey.likert_distribution"
    phash = params_hash(method, 1, {
        "item_id": item_id, "group_by": group_by, "k_anonymity": k_anonymity, "seed": seed,
    })

    rows = _responses_for(responses, item_id)
    n = len(rows)
    empty = {"counts_by_level": {}, "proportions": {}, "median": None, "iqr": None,
             "top_box": None, "bottom_box": None, "cliffs_delta_vs_reference": [],
             "lo": {}, "hi": {}}
    if n < MIN_LIKERT:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="responses",
            caveats=(
                "Needs " + str(MIN_LIKERT) + " responses to this item; has " + str(n) + ".",
            ),
        )

    scales = {(int(r.scale_min), int(r.scale_max)) for r in rows}
    if len(scales) > 1:
        described = ", ".join(str(a) + " to " + str(b) for a, b in sorted(scales))
        return Evidence(
            value=empty,
            n=n,
            method=method,
            as_of=as_of,
            checks=(
                Check(
                    id="scale-consistent",
                    label="Every response to this item is on the same scale",
                    status="FAIL",
                    statistic=float(len(scales)),
                    blocking=True,
                    detail=(
                        "Responses on " + str(len(scales)) + " different scales (" + described
                        + ") were pooled under one item id. A 4 on a 1 to 5 scale and a 4 on a "
                        "1 to 7 scale are different answers, so nothing is reported until they "
                        "are separated. This happens constantly in real survey data."
                    ),
                ),
            ),
            caveats=("Mixed response scales. Split the item and rerun.",),
            unit="responses",
            params_hash=phash,
        )

    scale_min, scale_max = next(iter(scales))
    levels = list(range(scale_min, scale_max + 1))
    values = [int(r.value) for r in rows]
    counts = {level: sum(1 for v in values if v == level) for level in levels}
    proportions = {level: counts[level] / n for level in levels}

    ordered = sorted(values)
    median = percentile(ordered, 0.5)
    q1 = percentile(ordered, 0.25)
    q3 = percentile(ordered, 0.75)
    top_box = counts[scale_max] / n
    bottom_box = counts[scale_min] / n

    lo: dict[int, float] = {}
    hi: dict[int, float] = {}
    indicator = [float(v) for v in values]
    for level in levels:
        lo[level], hi[level] = bootstrap_bca(
            indicator, lambda sample, lv=level: sum(1 for v in sample if v == lv) / len(sample),
            seed=seed, n_boot=500,
        )

    deltas = []
    n_suppressed = 0
    if group_by:
        groups: dict[str, list[int]] = {}
        for r in rows:
            strata = getattr(r, "strata", {}) or {}
            key = str(strata.get(group_by, "unstated"))
            groups.setdefault(key, []).append(int(r.value))
        for key in sorted(groups):
            here = groups[key]
            rest = [v for other, vs in groups.items() if other != key for v in vs]
            suppressed = len(here) < k_anonymity
            n_suppressed += 1 if suppressed else 0
            if suppressed or not rest:
                deltas.append({"group": key, "n": None, "delta": None, "lo": None,
                               "hi": None, "suppressed": True})
                continue
            delta = cliffs_delta(here, rest)
            d_lo, d_hi = bootstrap_bca(
                [float(v) for v in here],
                lambda sample, other=rest: cliffs_delta(sample, other),
                seed=seed, n_boot=400,
            )
            deltas.append({"group": key, "n": len(here), "delta": delta,
                           "lo": d_lo, "hi": d_hi, "suppressed": False})

    floor_ceiling = max(top_box, bottom_box)
    checks = [
        Check(
            id="scale-consistent",
            label="Every response to this item is on the same scale",
            status="PASS",
            statistic=1.0,
        ),
        Check(
            id="floor-ceiling",
            label="Whether the item can still tell people apart",
            status="WARN" if floor_ceiling > 0.6 else "PASS",
            statistic=floor_ceiling,
            detail=(
                "{:.0%}".format(floor_ceiling) + " of answers sit in one end box, so this item "
                "cannot discriminate and any comparison across groups will be driven by the "
                "bound rather than by opinion."
            ) if floor_ceiling > 0.6 else "",
        ),
        Check(
            id="k-anonymity-cells",
            label="No group row describes fewer than k respondents",
            status="FAIL" if n_suppressed else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(n_suppressed) + " group rows covered fewer than " + str(k_anonymity)
                + " respondents and are emptied."
            ) if n_suppressed else "",
        ),
    ]

    return Evidence(
        # There is deliberately no "mean" key. The shape does not permit it,
        # which is prevention by type rather than by review.
        value={
            "counts_by_level": counts,
            "proportions": proportions,
            "median": median,
            "iqr": (q1, q3),
            "top_box": top_box,
            "bottom_box": bottom_box,
            "cliffs_delta_vs_reference": deltas,
            "lo": lo,
            "hi": hi,
            "scale": [scale_min, scale_max],
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="bootstrap-bca-95",
        assumptions=(
            "The levels are ordered but NOT equally spaced. The gap between poor and fair is "
            "not the gap between good and excellent.",
            "All pooled responses share one scale.",
        ),
        checks=tuple(checks),
        caveats=(
            "There is no mean here and there cannot be. Averaging a 1 to 5 rating assumes the "
            "steps are equal, which is exactly what an ordinal scale does not promise.",
            "Cliff's delta is a probability of superiority: 0.3 means a randomly chosen member "
            "of this group rates higher than a randomly chosen member of the rest about 65% of "
            "the time.",
        ),
        unit="responses",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# Ordinal logistic regression
# ---------------------------------------------------------------------------


def _design(rows, covariates) -> tuple[list[list[float]], list[str]]:
    """
    Covariate matrix with no intercept: the cutpoints carry it.

    A string covariate is expanded into indicators against its first level in
    sorted order, so the reference category is stable across runs.
    """
    names: list[str] = []
    columns: list[list[float]] = []
    for covariate in covariates:
        raw = [getattr(r, "covariates", {}).get(covariate) for r in rows]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
            names.append(covariate)
            columns.append([float(v) for v in raw])
            continue
        levels = sorted({str(v) for v in raw})
        for level in levels[1:]:
            names.append(covariate + "=" + level)
            columns.append([1.0 if str(v) == level else 0.0 for v in raw])
    design = [[columns[j][i] for j in range(len(columns))] for i in range(len(rows))]
    return design, names


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def polr_fit(design: Sequence[Sequence[float]], y: Sequence[int], n_levels: int,
             *, max_iter: int = 100, tol: float = 1e-10):
    """
    Proportional-odds cumulative logit by Newton-Raphson.

    P(Y <= j | x) = logistic(theta_j - x'beta), with theta strictly increasing.
    Ordering is enforced by working in theta_1 and log-gaps, so no constrained
    optimiser is needed and the Hessian stays well conditioned. McCullagh (1980).
    """
    n = len(y)
    p = len(design[0]) if design and design[0] else 0
    k = n_levels - 1

    # Start from the marginal cumulative logits and beta = 0.
    counts = [sum(1 for v in y if v == level) for level in range(n_levels)]
    cumulative = 0
    theta0 = []
    for j in range(k):
        cumulative += counts[j]
        share = min(max(cumulative / n, 1e-6), 1 - 1e-6)
        theta0.append(math.log(share / (1 - share)))
    params = [theta0[0]] + [
        math.log(max(theta0[j] - theta0[j - 1], 1e-3)) for j in range(1, k)
    ] + [0.0] * p

    def unpack(vector):
        theta = [vector[0]]
        for j in range(1, k):
            theta.append(theta[-1] + math.exp(vector[j]))
        beta = list(vector[k:])
        return theta, beta

    def negative_log_likelihood(vector) -> float:
        theta, beta = unpack(vector)
        total = 0.0
        for i in range(n):
            eta = math.fsum(design[i][j] * beta[j] for j in range(p)) if p else 0.0
            level = y[i]
            upper = _sigmoid(theta[level] - eta) if level < k else 1.0
            lower = _sigmoid(theta[level - 1] - eta) if level > 0 else 0.0
            total -= math.log(max(upper - lower, 1e-300))
        return total

    current = list(params)
    value = negative_log_likelihood(current)
    size = len(current)
    for _ in range(max_iter):
        # Numerical gradient and Hessian. The parameter count here is small
        # (cutpoints plus covariates) and the closed-form derivatives through
        # the log-gap reparameterisation are error-prone enough that the
        # numerical route is the honest trade.
        step = 1e-5
        gradient = [0.0] * size
        for a in range(size):
            up = list(current); up[a] += step
            down = list(current); down[a] -= step
            gradient[a] = (negative_log_likelihood(up) - negative_log_likelihood(down)) / (2 * step)
        hessian = [[0.0] * size for _ in range(size)]
        for a in range(size):
            for b in range(a, size):
                shift = list(current)
                shift[a] += step; shift[b] += step
                f_pp = negative_log_likelihood(shift)
                shift = list(current)
                shift[a] += step; shift[b] -= step
                f_pm = negative_log_likelihood(shift)
                shift = list(current)
                shift[a] -= step; shift[b] += step
                f_mp = negative_log_likelihood(shift)
                shift = list(current)
                shift[a] -= step; shift[b] -= step
                f_mm = negative_log_likelihood(shift)
                hessian[a][b] = hessian[b][a] = (f_pp - f_pm - f_mp + f_mm) / (4 * step * step)
        try:
            direction = solve(hessian, [-g for g in gradient])
        except (ValueError, ZeroDivisionError):
            break
        stepsize = 1.0
        improved = False
        for _ in range(30):
            candidate = [current[a] + stepsize * direction[a] for a in range(size)]
            try:
                candidate_value = negative_log_likelihood(candidate)
            except (ValueError, OverflowError):
                stepsize *= 0.5
                continue
            if candidate_value < value - 1e-14:
                current, value, improved = candidate, candidate_value, True
                break
            stepsize *= 0.5
        if not improved or max(abs(g) for g in gradient) < tol:
            break

    theta, beta = unpack(current)

    # Covariance of (theta, beta) on the natural scale, by the observed
    # information in the unconstrained parameterisation transformed through the
    # Jacobian of the log-gap map.
    step = 1e-5
    size = len(current)
    hessian = [[0.0] * size for _ in range(size)]
    for a in range(size):
        for b in range(a, size):
            shift = list(current); shift[a] += step; shift[b] += step
            f_pp = negative_log_likelihood(shift)
            shift = list(current); shift[a] += step; shift[b] -= step
            f_pm = negative_log_likelihood(shift)
            shift = list(current); shift[a] -= step; shift[b] += step
            f_mp = negative_log_likelihood(shift)
            shift = list(current); shift[a] -= step; shift[b] -= step
            f_mm = negative_log_likelihood(shift)
            hessian[a][b] = hessian[b][a] = (f_pp - f_pm - f_mp + f_mm) / (4 * step * step)
    try:
        covariance = inverse(hessian)
    except (ValueError, ZeroDivisionError):
        covariance = [[float("nan")] * size for _ in range(size)]
    beta_cov = [[covariance[k + a][k + b] for b in range(p)] for a in range(p)]
    return theta, beta, beta_cov, -value


def _binary_logit(design, y_binary, *, ridge=1e-8, max_iter=60):
    """
    Logistic regression with an intercept, by iteratively reweighted least
    squares. Used by the Brant test, which needs one fit per cutpoint.

    Returns (intercept, beta, fitted probabilities) or None on separation.
    """
    n = len(y_binary)
    p = len(design[0]) if design and design[0] else 0
    x = [[1.0] + list(row) for row in design]
    size = p + 1
    beta = [0.0] * size
    for _ in range(max_iter):
        eta = [math.fsum(x[i][j] * beta[j] for j in range(size)) for i in range(n)]
        mu = [_sigmoid(e) for e in eta]
        w = [max(m * (1 - m), 1e-10) for m in mu]
        xtwx = [[math.fsum(x[i][a] * w[i] * x[i][b] for i in range(n)) for b in range(size)]
                for a in range(size)]
        for a in range(size):
            xtwx[a][a] += ridge
        xtwz = [
            math.fsum(x[i][a] * (w[i] * eta[i] + (y_binary[i] - mu[i])) for i in range(n))
            for a in range(size)
        ]
        try:
            new = solve(xtwx, xtwz)
        except (ValueError, ZeroDivisionError):
            return None
        if max(abs(new[j] - beta[j]) for j in range(size)) < 1e-10:
            beta = new
            break
        beta = new
        if max(abs(b) for b in beta) > 50:
            return None
    eta = [math.fsum(x[i][j] * beta[j] for j in range(size)) for i in range(n)]
    mu = [_sigmoid(e) for e in eta]
    return beta[0], beta[1:], mu


def brant_test(design, y, n_levels):
    """
    Brant (1990). Does the covariate effect change across cutpoints?

    Fit the k = J-1 binary logits P(Y <= j) separately, stack their slopes, and
    test that they are all equal. The covariance between two of those fits has
    a closed form,

        Var(b_j, b_l) = (X'W_j X)^-1 (X'W_jl X) (X'W_l X)^-1,

    with W_j = diag(pi_j (1 - pi_j)) and W_jl = diag(pi_l - pi_j pi_l) for j < l,
    where pi_j is the fitted P(Y <= j). The omnibus test has (J-2)p degrees of
    freedom and each covariate's own test has J-2.

    Returns (global_statistic, global_df, global_p, per_covariate, slopes) or
    None if any of the binary fits failed.
    """
    n = len(y)
    p = len(design[0]) if design and design[0] else 0
    k = n_levels - 1
    if k < 2 or p == 0:
        return None

    fits = []
    for j in range(k):
        binary = [1.0 if y[i] <= j else 0.0 for i in range(n)]
        fit = _binary_logit(design, binary)
        if fit is None:
            return None
        fits.append(fit)
    slopes = [fit[1] for fit in fits]
    pis = [fit[2] for fit in fits]

    x = [[1.0] + list(row) for row in design]
    size = p + 1
    inverses = []
    for j in range(k):
        w = [max(pis[j][i] * (1 - pis[j][i]), 1e-12) for i in range(n)]
        xtwx = [[math.fsum(x[i][a] * w[i] * x[i][b] for i in range(n)) for b in range(size)]
                for a in range(size)]
        try:
            inverses.append(inverse(xtwx))
        except (ValueError, ZeroDivisionError):
            return None

    def cross(j, l):
        # Z_j = 1{Y <= j} is nested in Z_l for j < l, so E[Z_j Z_l] = pi_j and
        # Cov(Z_j, Z_l) = pi_j (1 - pi_l), the SMALLER cumulative probability
        # times one minus the larger. Getting this the other way round makes the
        # stacked covariance non positive definite and the Wald statistic comes
        # out negative, which is how the sign error announced itself.
        lo, hi = (j, l) if j <= l else (l, j)
        w = [pis[lo][i] * (1.0 - pis[hi][i]) for i in range(n)]
        xtwx = [[math.fsum(x[i][a] * w[i] * x[i][b] for i in range(n)) for b in range(size)]
                for a in range(size)]
        left, right = inverses[j], inverses[l]
        middle = [[math.fsum(left[a][c] * xtwx[c][d] for c in range(size)) for d in range(size)]
                  for a in range(size)]
        return [[math.fsum(middle[a][d] * right[d][b] for d in range(size)) for b in range(size)]
                for a in range(size)]

    blocks = [[cross(j, l) for l in range(k)] for j in range(k)]

    # Stack the slopes (intercepts excluded) and test equality across cutpoints.
    stacked = [slopes[j][a] for j in range(k) for a in range(p)]
    big = [
        [blocks[j][l][1 + a][1 + b] for l in range(k) for b in range(p)]
        for j in range(k) for a in range(p)
    ]

    def wald(contrast_rows):
        d = [[float(v) for v in row] for row in contrast_rows]
        dv = [math.fsum(d[r][c] * stacked[c] for c in range(len(stacked))) for r in range(len(d))]
        dvd = [
            [
                math.fsum(
                    d[r][c] * big[c][cc] * d[s][cc]
                    for c in range(len(stacked)) for cc in range(len(stacked))
                )
                for s in range(len(d))
            ]
            for r in range(len(d))
        ]
        try:
            inv = inverse(dvd)
        except (ValueError, ZeroDivisionError):
            return None
        return math.fsum(
            dv[r] * inv[r][s] * dv[s] for r in range(len(d)) for s in range(len(d))
        )

    total = k * p
    global_rows = []
    for j in range(1, k):
        for a in range(p):
            row = [0.0] * total
            row[a] = 1.0
            row[j * p + a] = -1.0
            global_rows.append(row)
    global_stat = wald(global_rows)
    global_df = (k - 1) * p
    global_p = chi2_sf(global_stat, global_df) if global_stat is not None else None

    per_covariate = []
    for a in range(p):
        rows = []
        for j in range(1, k):
            row = [0.0] * total
            row[a] = 1.0
            row[j * p + a] = -1.0
            rows.append(row)
        stat = wald(rows)
        per_covariate.append({
            "statistic": stat,
            "df": k - 1,
            "p_value": chi2_sf(stat, k - 1) if stat is not None else None,
        })

    return global_stat, global_df, global_p, per_covariate, slopes


def ordinal_logistic(responses, as_of, *, item_id, covariates, link="logit", alpha=0.05,
                     k_anonymity=5) -> Evidence:
    """survey.ordinal_logistic. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survey.ordinal_logistic"
    phash = params_hash(method, 1, {
        "item_id": item_id, "covariates": list(covariates), "link": link, "alpha": alpha,
        "k_anonymity": k_anonymity,
    })
    if link != "logit":
        raise ValueError(
            "survey.ordinal_logistic implements the cumulative LOGIT link, which is what makes "
            "its coefficient a proportional ODDS ratio. Probit and cloglog are different models "
            "with different readings and are not implemented here; got " + repr(link)
        )

    rows = [
        r for r in _responses_for(responses, item_id)
        if all(getattr(r, "covariates", {}).get(c) is not None for c in covariates)
    ]
    n = len(rows)
    if n < MIN_ORDINAL or not covariates:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[], unit="odds ratio",
            caveats=(
                "Needs " + str(MIN_ORDINAL) + " complete responses; has " + str(n) + ". An "
                "ordinal model is estimated from its sparsest cutpoint, so a floor stated on "
                "the total n hides how little it rests on.",
            ),
        )

    values = sorted({int(r.value) for r in rows})
    counts = {v: sum(1 for r in rows if int(r.value) == v) for v in values}

    # Sparse levels are merged upwards and the merge is disclosed. A level with
    # three people in it cannot support a cutpoint.
    merged: list[tuple[int, ...]] = []
    pending: list[int] = []
    for v in values:
        pending.append(v)
        if sum(counts[u] for u in pending) >= SPARSE_LEVEL:
            merged.append(tuple(pending))
            pending = []
    if pending:
        if merged:
            merged[-1] = merged[-1] + tuple(pending)
        else:
            merged.append(tuple(pending))
    level_of = {v: i for i, group in enumerate(merged) for v in group}
    n_merges = sum(1 for group in merged if len(group) > 1)
    n_levels = len(merged)

    if n_levels < 3:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[], unit="odds ratio",
            caveats=(
                "After merging sparse levels this item has " + str(n_levels) + " usable levels. "
                "Proportional odds needs at least three; with two, this is ordinary logistic "
                "regression and should be reported as such.",
            ),
        )

    design, names = _design(rows, covariates)
    y = [level_of[int(r.value)] for r in rows]
    p = len(names)

    # Separation: a covariate that perfectly predicts a level.
    separated: set[str] = set()
    for j, name in enumerate(names):
        column = [row[j] for row in design]
        if len(set(column)) == 2:
            for level in range(n_levels):
                subset = {column[i] for i in range(n) if y[i] == level}
                other = {column[i] for i in range(n) if y[i] != level}
                if len(subset) == 1 and not (subset & other):
                    separated.add(name)

    theta, beta, beta_cov, loglik = polr_fit(design, y, n_levels)
    brant = brant_test(design, y, n_levels)

    z = norm_ppf(1.0 - alpha / 2.0)
    cell_counts = {}
    for j, name in enumerate(names):
        column = [row[j] for row in design]
        if set(column) <= {0.0, 1.0}:
            cell_counts[name] = int(sum(column))

    checks: list[Check] = []
    table = []
    for j, name in enumerate(names):
        variance = beta_cov[j][j] if beta_cov and beta_cov[j][j] == beta_cov[j][j] else None
        se = math.sqrt(variance) if variance and variance > 0 else None
        fails_po = False
        po_p = None
        if brant is not None:
            po_p = brant[3][j]["p_value"]
            fails_po = po_p is not None and po_p < alpha
        thin = name in cell_counts and cell_counts[name] < k_anonymity
        blocked = fails_po or name in separated or thin

        row = {
            "kind": "covariate",
            "covariate": name,
            "coef": None if blocked else beta[j],
            "odds_ratio": None if blocked else math.exp(beta[j]),
            "lo": None,
            "hi": None,
            "p_value": None,
            "n": cell_counts.get(name, n),
            "suppressed": blocked,
            # The binary logits behind the Brant test fit logistic(a + x'b) while
            # the model fits logistic(theta - x'beta), so their slopes are the
            # negatives of each other. Reported on the model's sign convention,
            # because a per-cutpoint effect that points the opposite way from the
            # pooled one it replaces is worse than no replacement at all.
            "per_cutpoint": (
                [{"cutpoint": c + 1, "coef": -brant[4][c][j],
                  "odds_ratio": math.exp(-brant[4][c][j])}
                 for c in range(n_levels - 1)]
                if (fails_po and brant is not None) else None
            ),
        }
        if not blocked and se:
            row["lo"] = math.exp(beta[j] - z * se)
            row["hi"] = math.exp(beta[j] + z * se)
            wald = beta[j] / se
            row["p_value"] = chi2_sf(wald * wald, 1)
        table.append(row)

        if fails_po:
            checks.append(Check(
                id="proportional-odds:" + name,
                label="The effect of " + name + " is the same at every step of the scale",
                status="FAIL",
                statistic=brant[3][j]["statistic"],
                p_value=po_p,
                blocking=True,
                detail=(
                    "Brant test p = " + "{:.4f}".format(po_p) + " on " + str(brant[3][j]["df"])
                    + " df. The effect of " + name + " is NOT the same at every cutpoint, so a "
                    "single odds ratio would be misleading and none is shown. What replaces it "
                    "is the per-cutpoint effects in this row: longer to read, and correct."
                ),
            ))
        else:
            checks.append(Check(
                id="proportional-odds:" + name,
                label="The effect of " + name + " is the same at every step of the scale",
                status="SKIPPED" if po_p is None else "PASS",
                statistic=(brant[3][j]["statistic"] if brant is not None else None),
                p_value=po_p,
                detail=("The Brant test could not be computed for this covariate."
                        if po_p is None else ""),
            ))

    if brant is not None:
        checks.insert(0, Check(
            id="proportional-odds",
            label="The proportional-odds assumption, tested across all covariates at once",
            status="FAIL" if (brant[2] is not None and brant[2] < alpha) else "PASS",
            statistic=brant[0],
            p_value=brant[2],
            blocking=False,
            detail=(
                "Omnibus Brant test p = " + "{:.4f}".format(brant[2]) + " on " + str(brant[1])
                + " df. At least one covariate's effect changes across the scale; which ones is "
                "in the per-covariate checks, and only those rows are suppressed."
            ) if (brant[2] is not None and brant[2] < alpha) else "",
        ))
    else:
        checks.insert(0, Check(
            id="proportional-odds",
            label="The proportional-odds assumption, tested across all covariates at once",
            status="SKIPPED",
            detail=(
                "The Brant test needs one binary logit per cutpoint and at least one did not "
                "converge, usually because a level is nearly empty. The assumption is therefore "
                "UNTESTED here, which is not the same as met."
            ),
        ))

    checks.append(Check(
        id="sparse-levels",
        label="Response levels too thin to support a cutpoint were merged",
        status="WARN" if n_merges else "PASS",
        statistic=float(n_merges),
        detail=(
            str(n_merges) + " adjacent response levels were merged because fewer than "
            + str(SPARSE_LEVEL) + " people chose them. The scale reported has " + str(n_levels)
            + " levels, not " + str(len(values)) + "."
        ) if n_merges else "",
    ))
    checks.append(Check(
        id="separation",
        label="No covariate perfectly predicts a response level",
        status="FAIL" if separated else "PASS",
        statistic=float(len(separated)),
        blocking=bool(separated),
        detail=(
            ", ".join(sorted(separated)) + " perfectly predicts a response level, so its "
            "coefficient is infinite and any finite number printed for it would be an artefact "
            "of where the optimiser stopped. Those rows are emptied."
        ) if separated else "",
    ))
    thin_rows = [name for name in cell_counts if cell_counts[name] < k_anonymity]
    checks.append(Check(
        id="k-anonymity-cells",
        label="No covariate row rests on fewer than k respondents",
        status="FAIL" if thin_rows else "PASS",
        statistic=float(k_anonymity),
        blocking=bool(thin_rows),
        detail=(
            ", ".join(sorted(thin_rows)) + " describes fewer than " + str(k_anonymity)
            + " respondents and is emptied."
        ) if thin_rows else "",
    ))

    for index, cut in enumerate(theta):
        table.append({
            "kind": "cutpoint",
            "covariate": "cutpoint " + str(index + 1) + "|" + str(index + 2),
            "coef": cut,
            "odds_ratio": None,
            "lo": None, "hi": None, "p_value": None,
            "n": n, "suppressed": False, "per_cutpoint": None,
        })

    return Evidence(
        value=table,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="profile-95",
        assumptions=(
            "Proportional odds: the effect of a covariate is the same at every cutpoint. "
            "Measured by the Brant test rather than assumed.",
            "Responses are independent. Two people in the same household are not.",
            "The ordinal levels are correctly ordered.",
        ),
        checks=tuple(checks),
        caveats=(
            "An odds ratio of 1.0 is no effect. The scale is multiplicative, so 2.0 and 0.5 are "
            "equal and opposite.",
            "Log-likelihood at the fit: " + "{:.4f}".format(loglik) + " over " + str(n_levels)
            + " levels.",
        ),
        unit="proportional odds ratio",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# Raking and the design effect
# ---------------------------------------------------------------------------


def raking_weights(respondent_strata, population_margins, as_of, *, max_iter=100, tol=1e-6,
                   trim=(0.2, 5.0)) -> Evidence:
    """survey.raking_weights. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survey.raking_weights"
    phash = params_hash(method, 1, {
        "margins": {k: dict(v) for k, v in dict(population_margins).items()},
        "max_iter": max_iter, "tol": tol, "trim": list(trim),
    })

    rows = [dict(s) for s in respondent_strata]
    n = len(rows)
    margins = {str(k): {str(level): float(share) for level, share in dict(v).items()}
               for k, v in dict(population_margins).items()}

    if n < MIN_RAKING or not margins:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[], unit="weight",
            caveats=(
                "Needs " + str(MIN_RAKING) + " respondents and at least one declared margin; "
                "has " + str(n) + " and " + str(len(margins)) + ".",
            ),
        )

    # Targets are normalised to n, so a caller may pass shares or headcounts.
    targets: dict[str, dict[str, float]] = {}
    for variable, levels in margins.items():
        total = math.fsum(levels.values())
        targets[variable] = {level: n * share / total for level, share in levels.items()}

    empty_cells = []
    for variable, levels in targets.items():
        for level, target in levels.items():
            present = sum(1 for r in rows if str(r.get(variable)) == level)
            if present == 0 and target > 0:
                empty_cells.append(variable + "=" + level)
            elif 0 < present < MIN_CELL:
                empty_cells.append(variable + "=" + level + " (only " + str(present) + ")")

    hard_empty = [c for c in empty_cells if "(only" not in c]
    if hard_empty:
        return Evidence(
            value=[],
            n=n,
            method=method,
            as_of=as_of,
            checks=(
                Check(
                    id="empty-cells",
                    label="Every cell being raked has someone in it",
                    status="FAIL",
                    statistic=float(len(hard_empty)),
                    blocking=True,
                    detail=(
                        "No respondent falls in " + ", ".join(sorted(hard_empty)) + ". That "
                        "margin cannot be raked to and the cell is named rather than the margin "
                        "silently dropped, because dropping it would produce weights that look "
                        "fine and represent nobody from that group."
                    ),
                ),
            ),
            caveats=("Raking is impossible until every declared cell has a respondent in it.",),
            unit="weight",
            params_hash=phash,
        )

    low, high = float(trim[0]), float(trim[1])
    weights = [1.0] * n
    iterations = 0
    converged = False
    trimmed = 0
    # Rake, cap, rake again, cap again. Every pass ENDS on a cap, so the
    # returned weights always honour the declared bounds: raking after the last
    # cap would put them straight back over it, which is a real bug and is what
    # the trimming test caught. The price is that the margins are then met only
    # as closely as the bounds permit, and the check reports that residual
    # rather than claiming convergence.
    for pass_index in range(6):
        converged = False
        for iterations in range(1, max_iter + 1):
            worst = 0.0
            for variable in sorted(targets):
                for level, target in sorted(targets[variable].items()):
                    members = [i for i in range(n) if str(rows[i].get(variable)) == level]
                    if not members:
                        continue
                    achieved = math.fsum(weights[i] for i in members)
                    if achieved <= 0:
                        continue
                    factor = target / achieved
                    worst = max(worst, abs(achieved - target))
                    for i in members:
                        weights[i] *= factor
            if worst < tol:
                converged = True
                break
        capped = [min(max(w, low), high) for w in weights]
        now_trimmed = sum(1 for a, b in zip(weights, capped) if abs(a - b) > 1e-12)
        weights = capped
        if now_trimmed == 0:
            break
        trimmed = now_trimmed
        converged = False

    achieved_rows = []
    max_deviation = 0.0
    for variable in sorted(targets):
        for level, target in sorted(targets[variable].items()):
            members = [i for i in range(n) if str(rows[i].get(variable)) == level]
            achieved = math.fsum(weights[i] for i in members)
            max_deviation = max(max_deviation, abs(achieved - target))
            achieved_rows.append({
                "kind": "margin",
                "key": variable + "=" + level,
                "weight": None,
                "target": target,
                "achieved": achieved,
                "n": len(members),
            })

    total = math.fsum(weights)
    deff = n * math.fsum(w * w for w in weights) / (total * total) if total > 0 else None

    table = [
        {"kind": "weight", "key": str(i), "weight": weights[i], "target": None,
         "achieved": None, "n": 1}
        for i in range(n)
    ] + achieved_rows

    checks = [
        Check(
            id="convergence",
            label="Iterative proportional fitting reached the declared margins",
            status="PASS" if converged or max_deviation < max(tol, 1e-6) else "FAIL",
            statistic=max_deviation,
            blocking=not (converged or max_deviation < max(tol, 1e-6)) and not trimmed,
            detail=(
                "The margins were not reached after " + str(max_iter) + " iterations; the worst "
                "cell is off by " + "{:.4f}".format(max_deviation) + ". Non-convergence means "
                "the declared margins are mutually inconsistent, so no weights are usable."
            ) if not (converged or max_deviation < max(tol, 1e-6)) and not trimmed else "",
        ),
        Check(
            id="extreme-weights",
            label="Weights outside the declared trim bounds",
            status="WARN" if trimmed else "PASS",
            statistic=float(trimmed),
            detail=(
                str(trimmed) + " weights were outside the trim bounds " + repr(trim)
                + " and were capped, after which the margins were re-raked. A weight of 40 "
                "means one person is speaking for forty and the estimate is that person's "
                "opinion. The margins are now off by at most "
                + "{:.4f}".format(max_deviation) + " as the price of that cap."
            ) if trimmed else "",
        ),
        Check(
            id="empty-cells",
            label="Every cell being raked has enough people in it",
            status="WARN" if empty_cells else "PASS",
            statistic=float(len(empty_cells)),
            detail=(
                "Thin cells: " + ", ".join(sorted(empty_cells)) + ". Each is being asked to "
                "represent its whole share of the community."
            ) if empty_cells else "",
        ),
        Check(
            id="design-effect-acceptable",
            label="How much precision the weighting costs",
            status="WARN" if (deff or 0) > DEFF_WARN else "PASS",
            statistic=deff,
            detail=(
                "Design effect " + "{:.2f}".format(deff) + ", so " + str(n) + " respondents "
                "carry the precision of about " + "{:.0f}".format(n / deff) + ". That is the "
                "number that should be in the reader's head."
            ) if (deff or 0) > DEFF_WARN else "",
        ),
    ]

    return Evidence(
        value=table,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The population margins are correct.",
            "Non-response is ignorable WITHIN the raking cells. That is the assumption which "
            "actually carries the inference and it is untestable from the sample alone.",
        ),
        checks=tuple(checks),
        caveats=(
            "Raking fixes composition, never motivation. If the people who did not respond "
            "differ from those who did in a way the raking variables do not capture, these "
            "weights do not help and may hurt.",
            "The weights themselves have no interval. Every downstream estimate must widen its "
            "own by the design effect, which survey.design_effect reports.",
        ),
        unit="weight",
        params_hash=phash,
    )


def design_effect(weights, as_of) -> Evidence:
    """survey.design_effect. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "survey.design_effect"
    phash = params_hash(method, 1, {})

    values = [float(w) for w in weights]
    n = len(values)
    if n < 1:
        return insufficient(
            method, n=0, as_of=as_of, params_hash=phash, unit="design effect",
            caveats=("No weights were supplied.",),
        )

    total = math.fsum(values)
    if total <= 0:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, unit="design effect",
            caveats=("The weights sum to zero, so no effective sample size exists.",),
        )
    deff = n * math.fsum(w * w for w in values) / (total * total)
    n_eff = n / deff

    return Evidence(
        value=deff,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=("The weights are the ones actually applied to the estimate being reported.",),
        checks=(
            Check(
                id="design-effect-acceptable",
                label="How much precision the weighting costs",
                status="WARN" if deff > DEFF_WARN else "PASS",
                statistic=deff,
                detail=(
                    "Design effect " + "{:.2f}".format(deff) + " is above " + str(DEFF_WARN)
                    + ", so the weighting costs more than half the sample's precision."
                ) if deff > DEFF_WARN else "",
            ),
            Check(
                id="uniform-weights",
                label="Whether any weighting was applied at all",
                status="PASS",
                statistic=1.0 if abs(deff - 1.0) < 1e-12 else 0.0,
                detail=("Every weight is equal, so the design effect is exactly 1 and the "
                        "effective sample size is the raw one.")
                if abs(deff - 1.0) < 1e-12 else "",
            ),
        ),
        caveats=(
            str(n) + " respondents, weighted, carry the precision of about "
            + "{:.0f}".format(n_eff) + ". The second number is the one to quote.",
            "Kish's deff is exact given the weights. It has no interval because it is not "
            "estimating anything.",
        ),
        unit="design effect",
        params_hash=phash,
    )


__all__ = [
    "brant_test",
    "cliffs_delta",
    "design_effect",
    "likert_distribution",
    "mann_whitney_u",
    "ordinal_logistic",
    "polr_fit",
    "raking_weights",
]
