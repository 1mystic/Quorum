"""
The numerical primitives every service in this package is built on.

Standard library only, and deliberately so. The scientific stack (numpy, scipy,
statsmodels, lifelines) is roughly half a gigabyte and `PLAN.md` splits deploy
into a light `web` process and a heavy `worker` for exactly that reason. Pack 1
is closed-form mathematics over at most a few thousand rows, so writing the
handful of special functions it needs by hand keeps the whole engine runnable on
the light tier and keeps `app/stats/` importable anywhere.

Every function here is deterministic. Randomness enters only through an explicit
`random.Random(seed)`, never a module-level generator.

Each special function carries the source of its approximation and the accuracy it
claims; `tests/unit/stats/test_numeric.py` checks each one against published
values rather than against itself.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Sequence

# ---------------------------------------------------------------------------
# Descriptive
# ---------------------------------------------------------------------------


def mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("mean of an empty sequence")
    return math.fsum(xs) / len(xs)


def variance(xs: Sequence[float], *, ddof: int = 1) -> float:
    """Sample variance by default. ddof=0 gives the population form."""
    n = len(xs)
    if n - ddof <= 0:
        raise ValueError("variance needs more than " + str(ddof) + " observations")
    m = mean(xs)
    return math.fsum((x - m) ** 2 for x in xs) / (n - ddof)


def std(xs: Sequence[float], *, ddof: int = 1) -> float:
    return math.sqrt(variance(xs, ddof=ddof))


def percentile(sorted_xs: Sequence[float], q: float) -> float:
    """
    Linear interpolation between order statistics, the numpy default. Input must
    already be sorted; sorting inside would hide an O(n log n) cost in a loop.
    """
    if not sorted_xs:
        raise ValueError("percentile of an empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("percentile q must be in [0, 1], got " + repr(q))
    if len(sorted_xs) == 1:
        return float(sorted_xs[0])
    pos = q * (len(sorted_xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_xs) - 1)
    frac = pos - lo
    return float(sorted_xs[lo]) * (1.0 - frac) + float(sorted_xs[hi]) * frac


def pearson_corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys):
        raise ValueError("pearson_corr needs equal-length sequences")
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = mean(xs), mean(ys)
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    syy = math.fsum((y - my) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


# ---------------------------------------------------------------------------
# Distributions
# ---------------------------------------------------------------------------


def norm_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def norm_ppf(p: float) -> float:
    """
    Inverse normal CDF. Acklam's rational approximation followed by one
    Halley refinement, which takes the relative error below 1e-15.
    """
    if not 0.0 < p < 1.0:
        if p == 0.0:
            return -math.inf
        if p == 1.0:
            return math.inf
        raise ValueError("norm_ppf needs p in (0, 1), got " + repr(p))
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    err = norm_cdf(x) - p
    density = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
    if density > 0.0:
        u = err / density
        x = x - u / (1.0 + 0.5 * x * u)
    return x


def _gamma_p_series(a: float, x: float) -> float:
    """Regularized lower incomplete gamma by series. Numerical Recipes gser."""
    ap = a
    total = 1.0 / a
    term = total
    for _ in range(1000):
        ap += 1.0
        term *= x / ap
        total += term
        if abs(term) < abs(total) * 1e-16:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_q_cf(a: float, x: float) -> float:
    """Regularized upper incomplete gamma by continued fraction. NR gcf."""
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gammainc_p(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x)."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("gammainc_p needs a > 0 and x >= 0")
    if x == 0.0:
        return 0.0
    if x < a + 1.0:
        return _gamma_p_series(a, x)
    return 1.0 - _gamma_q_cf(a, x)


def gammainc_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) = 1 - P(a, x)."""
    if x < 0.0 or a <= 0.0:
        raise ValueError("gammainc_q needs a > 0 and x >= 0")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gamma_p_series(a, x)
    return _gamma_q_cf(a, x)


def chi2_sf(x: float, df: int) -> float:
    """Upper tail of the chi-square distribution: the p-value of a chi-square statistic."""
    if df <= 0:
        raise ValueError("chi2_sf needs df >= 1")
    if x <= 0.0:
        return 1.0
    return gammainc_q(df / 2.0, x / 2.0)


def chi2_ppf(p: float, df: int) -> float:
    """Chi-square quantile by bisection on the survival function."""
    if not 0.0 < p < 1.0:
        raise ValueError("chi2_ppf needs p in (0, 1)")
    lo, hi = 0.0, 1.0
    while chi2_sf(hi, df) > 1.0 - p:
        hi *= 2.0
        if hi > 1e12:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 1.0 - chi2_sf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta. Numerical Recipes betacf."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + b * math.log1p(-x) + a * math.log(x)
    ) * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """Upper tail of Student's t."""
    if df <= 0:
        raise ValueError("t_sf needs df > 0")
    x = df / (df + t * t)
    half = 0.5 * betainc(df / 2.0, 0.5, x)
    return half if t > 0 else 1.0 - half


def t_two_sided_p(t: float, df: float) -> float:
    return 2.0 * t_sf(abs(t), df)


def poisson_pmf(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    if mu <= 0.0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-mu + k * math.log(mu) - math.lgamma(k + 1.0))


def poisson_cdf(k: int, mu: float) -> float:
    """
    Exact, via the identity P(X <= k) = Q(k+1, mu) with Q the regularized upper
    incomplete gamma. Exact rather than a normal approximation because the
    Poisson rate chart's whole argument is that the approximation changes
    conclusions below a mean of five.
    """
    if k < 0:
        return 0.0
    if mu <= 0.0:
        return 1.0
    return gammainc_q(k + 1.0, mu)


def poisson_ppf(p: float, mu: float) -> int:
    """Smallest k with P(X <= k) >= p."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("poisson_ppf needs p in [0, 1]")
    if p <= 0.0:
        return 0
    k = 0
    total = poisson_cdf(0, mu)
    limit = int(mu + 20.0 * math.sqrt(mu + 1.0)) + 100
    while total < p and k < limit:
        k += 1
        total = poisson_cdf(k, mu)
    return k


def nbinom_cdf(k: int, r: float, prob: float) -> float:
    """
    Negative binomial P(X <= k) with `r` failures-shape and success probability
    `prob`, via the regularized incomplete beta identity I_prob(r, k+1).
    """
    if k < 0:
        return 0.0
    return betainc(r, k + 1.0, prob)


def nbinom_ppf(p: float, r: float, prob: float) -> int:
    if p <= 0.0:
        return 0
    k = 0
    while nbinom_cdf(k, r, prob) < p and k < 1_000_000:
        k += 1
    return k


# ---------------------------------------------------------------------------
# Linear algebra. Small dense systems only: a Cox model has single-digit
# covariates and an SPC Markov chain a few hundred states.
# ---------------------------------------------------------------------------


def solve(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float]:
    """Gaussian elimination with partial pivoting. Raises on a singular system."""
    n = len(rhs)
    a = [list(map(float, row)) + [float(rhs[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise ValueError("singular system at column " + str(col))
        a[col], a[pivot] = a[pivot], a[col]
        inv_pivot = 1.0 / a[col][col]
        for r in range(col + 1, n):
            factor = a[r][col] * inv_pivot
            if factor == 0.0:
                continue
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    out = [0.0] * n
    for row in range(n - 1, -1, -1):
        acc = a[row][n] - math.fsum(a[row][c] * out[c] for c in range(row + 1, n))
        out[row] = acc / a[row][row]
    return out


def inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(matrix)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(solve(matrix, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


# ---------------------------------------------------------------------------
# Regression and resampling
# ---------------------------------------------------------------------------


def ols_slope(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float]:
    """
    Simple linear regression. Returns (slope, standard error, two-sided p).

    Used by the steady-state check in `queueing.little_law_wait`, where a
    significant slope means there is no steady-state wait to report at all.
    """
    n = len(xs)
    if n < 3:
        return 0.0, math.inf, 1.0
    mx, my = mean(xs), mean(ys)
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    if sxx <= 0.0:
        return 0.0, math.inf, 1.0
    slope = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    if n <= 2:
        return slope, math.inf, 1.0
    sigma2 = math.fsum(r * r for r in resid) / (n - 2)
    if sigma2 <= 0.0:
        return slope, 0.0, 0.0 if slope != 0.0 else 1.0
    se = math.sqrt(sigma2 / sxx)
    return slope, se, t_two_sided_p(slope / se, n - 2)


def bootstrap_bca(
    data: Sequence,
    statistic: Callable[[Sequence], float],
    *,
    seed: int,
    n_boot: int = 1000,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """
    Bias-corrected and accelerated bootstrap interval (Efron and Tibshirani 1993,
    ch. 14). Seeded, so two runs with the same seed are byte-identical.

    Falls back to the plain percentile interval when the acceleration or the bias
    correction is undefined, which happens when every resample gives the same
    answer. That fallback is reported by the caller as a caveat, never silently.
    """
    n = len(data)
    if n < 2:
        raise ValueError("bootstrap needs at least two observations")
    theta_hat = statistic(data)
    rng = random.Random(seed)
    boots: list[float] = []
    for _ in range(n_boot):
        sample = [data[rng.randrange(n)] for _ in range(n)]
        try:
            boots.append(statistic(sample))
        except (ValueError, ZeroDivisionError):
            continue
    if len(boots) < 20:
        return theta_hat, theta_hat
    boots.sort()
    below = sum(1 for b in boots if b < theta_hat)
    proportion = below / len(boots)
    lo_q, hi_q = alpha / 2.0, 1.0 - alpha / 2.0
    if 0.0 < proportion < 1.0:
        z0 = norm_ppf(proportion)
        jack = []
        for i in range(n):
            reduced = list(data[:i]) + list(data[i + 1:])
            try:
                jack.append(statistic(reduced))
            except (ValueError, ZeroDivisionError):
                jack.append(theta_hat)
        jm = mean(jack)
        num = math.fsum((jm - j) ** 3 for j in jack)
        den = 6.0 * (math.fsum((jm - j) ** 2 for j in jack) ** 1.5)
        accel = num / den if den > 0.0 else 0.0
        za = norm_ppf(alpha / 2.0)
        zb = norm_ppf(1.0 - alpha / 2.0)
        denom_a = 1.0 - accel * (z0 + za)
        denom_b = 1.0 - accel * (z0 + zb)
        if denom_a > 0.0 and denom_b > 0.0:
            lo_q = norm_cdf(z0 + (z0 + za) / denom_a)
            hi_q = norm_cdf(z0 + (z0 + zb) / denom_b)
    lo_q = min(max(lo_q, 0.0), 1.0)
    hi_q = min(max(hi_q, 0.0), 1.0)
    if lo_q > hi_q:
        lo_q, hi_q = hi_q, lo_q
    return percentile(boots, lo_q), percentile(boots, hi_q)


def wilson_interval(successes: int, trials: int, *, alpha: float = 0.05) -> tuple[float, float]:
    """
    Wilson (1927) score interval for a binomial proportion.

    Preferred to the Wald interval everywhere in this package because Wald is
    degenerate at 0 and 1, which is exactly where a small community's rates sit:
    "0 of 7 late" under Wald is the interval [0, 0], which is a false statement.
    """
    if trials <= 0:
        raise ValueError("wilson_interval needs at least one trial")
    if successes < 0 or successes > trials:
        raise ValueError("wilson_interval got " + str(successes) + " successes in " + str(trials))
    z = norm_ppf(1.0 - alpha / 2.0)
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_difference(
    successes_a: int, trials_a: int, successes_b: int, trials_b: int, *, alpha: float = 0.05
) -> tuple[float, float]:
    """
    Newcombe (1998) hybrid-score interval for the difference of two proportions.

    Built from the two Wilson intervals rather than from a pooled normal
    approximation, so it inherits Wilson's behaviour at the boundary. The
    construction is exactly the one in Newcombe's method 10.
    """
    p_a = successes_a / trials_a
    p_b = successes_b / trials_b
    lo_a, hi_a = wilson_interval(successes_a, trials_a, alpha=alpha)
    lo_b, hi_b = wilson_interval(successes_b, trials_b, alpha=alpha)
    diff = p_a - p_b
    lower = diff - math.sqrt((p_a - lo_a) ** 2 + (hi_b - p_b) ** 2)
    upper = diff + math.sqrt((hi_a - p_a) ** 2 + (p_b - lo_b) ** 2)
    return max(-1.0, lower), min(1.0, upper)


def nelder_mead(
    objective: Callable[[Sequence[float]], float],
    start: Sequence[float],
    *,
    step: float = 0.1,
    max_iter: int = 800,
    tol: float = 1e-9,
) -> tuple[list[float], float]:
    """
    Derivative-free simplex minimisation (Nelder and Mead 1965).

    Deterministic: the initial simplex is built from `start` by a fixed offset
    per coordinate, never from a random perturbation, so two runs on the same
    input are byte identical. Used where an analytic gradient is not worth
    writing out, notably the conditional sum of squares for SARIMA.
    """
    dim = len(start)
    if dim == 0:
        return [], objective(start)
    simplex = [list(start)]
    for i in range(dim):
        point = list(start)
        point[i] += step if point[i] == 0.0 else step * (1.0 + abs(point[i]))
        simplex.append(point)
    scores = [objective(p) for p in simplex]
    for _ in range(max_iter):
        order = sorted(range(dim + 1), key=lambda i: scores[i])
        simplex = [simplex[i] for i in order]
        scores = [scores[i] for i in order]
        if abs(scores[-1] - scores[0]) <= tol * (abs(scores[0]) + tol):
            break
        centroid = [math.fsum(p[i] for p in simplex[:-1]) / dim for i in range(dim)]
        worst = simplex[-1]
        reflected = [centroid[i] + (centroid[i] - worst[i]) for i in range(dim)]
        f_reflected = objective(reflected)
        if f_reflected < scores[0]:
            expanded = [centroid[i] + 2.0 * (centroid[i] - worst[i]) for i in range(dim)]
            f_expanded = objective(expanded)
            if f_expanded < f_reflected:
                simplex[-1], scores[-1] = expanded, f_expanded
            else:
                simplex[-1], scores[-1] = reflected, f_reflected
            continue
        if f_reflected < scores[-2]:
            simplex[-1], scores[-1] = reflected, f_reflected
            continue
        contracted = [centroid[i] + 0.5 * (worst[i] - centroid[i]) for i in range(dim)]
        f_contracted = objective(contracted)
        if f_contracted < scores[-1]:
            simplex[-1], scores[-1] = contracted, f_contracted
            continue
        best = simplex[0]
        for i in range(1, dim + 1):
            simplex[i] = [best[j] + 0.5 * (simplex[i][j] - best[j]) for j in range(dim)]
            scores[i] = objective(simplex[i])
    best_index = min(range(dim + 1), key=lambda i: scores[i])
    return simplex[best_index], scores[best_index]


def logistic_l2_fit(
    design: Sequence[Sequence[float]],
    labels: Sequence[float],
    *,
    penalty: float = 1.0,
    max_iter: int = 100,
    tol: float = 1e-10,
) -> list[float]:
    """
    L2-penalised logistic regression by iteratively reweighted least squares.

    The first column of `design` is expected to be the intercept and is NOT
    penalised: shrinking the intercept would bias the fitted base rate, which is
    the one quantity a calibrated probability must get right.
    """
    if not design:
        raise ValueError("logistic_l2_fit needs at least one row")
    n = len(design)
    p = len(design[0])
    if len(labels) != n:
        raise ValueError("design and labels differ in length")
    beta = [0.0] * p
    for _ in range(max_iter):
        gradient = [0.0] * p
        hessian = [[0.0] * p for _ in range(p)]
        for i in range(n):
            row = design[i]
            eta = math.fsum(beta[j] * row[j] for j in range(p))
            eta = max(-35.0, min(35.0, eta))
            mu = 1.0 / (1.0 + math.exp(-eta))
            weight = max(mu * (1.0 - mu), 1e-9)
            residual = labels[i] - mu
            for j in range(p):
                gradient[j] += residual * row[j]
                for k in range(j, p):
                    hessian[j][k] += weight * row[j] * row[k]
        for j in range(1, p):
            gradient[j] -= penalty * beta[j]
            hessian[j][j] += penalty
        for j in range(p):
            for k in range(j):
                hessian[j][k] = hessian[k][j]
            hessian[j][j] += 1e-10
        try:
            step = solve(hessian, gradient)
        except ValueError:
            break
        beta = [beta[j] + step[j] for j in range(p)]
        if max(abs(s) for s in step) < tol:
            break
    return beta


def logistic_predict(design_row: Sequence[float], beta: Sequence[float]) -> float:
    eta = math.fsum(b * x for b, x in zip(beta, design_row))
    eta = max(-35.0, min(35.0, eta))
    return 1.0 / (1.0 + math.exp(-eta))


__all__ = [
    "betainc",
    "bootstrap_bca",
    "chi2_ppf",
    "chi2_sf",
    "gammainc_p",
    "gammainc_q",
    "inverse",
    "logistic_l2_fit",
    "logistic_predict",
    "mean",
    "nelder_mead",
    "newcombe_difference",
    "nbinom_cdf",
    "nbinom_ppf",
    "norm_cdf",
    "norm_ppf",
    "norm_sf",
    "ols_slope",
    "pearson_corr",
    "percentile",
    "poisson_cdf",
    "poisson_pmf",
    "poisson_ppf",
    "solve",
    "std",
    "t_sf",
    "t_two_sided_p",
    "variance",
    "wilson_interval",
]
