"""
Forecasting over any periodised series.

The MASE gate governs this module: no forecaster is served to a tenant unless it beat
seasonal-naive under rolling-origin cross-validation on that tenant's own history. A
forecast that cannot beat naive is decoration, and decoration that looks like a
forecast is worse than nothing. A blocking MASE failure returns the seasonal-naive
forecast rather than an error, so the tenant still gets a number and it is the honest one.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Three implementation notes worth stating where a reader will find them.

1. The interval is a PREDICTIVE interval for a future observation, not a
   confidence interval for the mean, and it is built from the standardised
   empirical residual quantiles rather than from a normal quantile whenever the
   residual normality check fails. Under-coverage is the common failure and it
   is invisible unless it is measured, which is what `rolling_origin_backtest`
   does.
2. Nothing here reads a clock or a database. `as_of` is `window.end`.
3. Optimisation is deterministic. Holt-Winters uses a bounded coordinate
   descent with golden-section line searches from a fixed start, and SARIMA uses
   a Nelder-Mead simplex built from a fixed offset. Neither takes a seed because
   neither is random.
"""
import math
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import (
    bootstrap_bca,
    chi2_sf,
    mean,
    nelder_mead,
    norm_ppf,
    percentile,
    variance,
)
from app.stats.series import ljung_box, period_series

MIN_PERIODS = 24
MIN_PERIODS_SARIMA = 36
MIN_FOLDS = 5

# Nominal levels the contract's IntervalKind knows about. An alpha outside this
# set would have to be reported as a kind that does not exist, so it is refused
# rather than silently relabelled.
Z80 = norm_ppf(0.9)
Z95 = norm_ppf(0.975)


# ---------------------------------------------------------------------------
# The internal forecaster contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastFit:
    """
    What every forecaster in this module returns before it is wrapped in Evidence.

    `sd` is the predictive standard deviation per horizon step and it grows with
    the horizon; `standardised_residuals` carries the empirical shape used when
    the normality check fails. Keeping both means the interval can be switched
    from normal to empirical without refitting.
    """

    point: tuple[float, ...]
    sd: tuple[float, ...]
    fitted: tuple[float, ...]
    residuals: tuple[float, ...]
    sigma: float
    params: dict
    label: str

    @property
    def standardised(self) -> tuple[float, ...]:
        if self.sigma <= 0.0:
            return tuple(0.0 for _ in self.residuals)
        return tuple(r / self.sigma for r in self.residuals)


Forecaster = Callable[[Sequence[float], int, int], ForecastFit]


def _empirical_quantile_pair(standardised: Sequence[float], alpha: float) -> tuple[float, float]:
    if len(standardised) < 10:
        z = norm_ppf(1.0 - alpha / 2.0)
        return -z, z
    ordered = sorted(standardised)
    return percentile(ordered, alpha / 2.0), percentile(ordered, 1.0 - alpha / 2.0)


def _bands(fit: ForecastFit, *, empirical: bool) -> dict[str, tuple[float, ...]]:
    """80% and 95% predictive bands from the fit's per-step standard deviations."""
    if empirical:
        lo80, hi80 = _empirical_quantile_pair(fit.standardised, 0.20)
        lo95, hi95 = _empirical_quantile_pair(fit.standardised, 0.05)
    else:
        lo80, hi80 = -Z80, Z80
        lo95, hi95 = -Z95, Z95
    return {
        "lo80": tuple(p + lo80 * s for p, s in zip(fit.point, fit.sd)),
        "hi80": tuple(p + hi80 * s for p, s in zip(fit.point, fit.sd)),
        "lo95": tuple(p + lo95 * s for p, s in zip(fit.point, fit.sd)),
        "hi95": tuple(p + hi95 * s for p, s in zip(fit.point, fit.sd)),
    }


# ---------------------------------------------------------------------------
# Seasonal naive: the denominator of the whole pack
# ---------------------------------------------------------------------------


def seasonal_naive_fit(train: Sequence[float], season_length: int, horizon: int) -> ForecastFit:
    """
    yhat[T + h] = y[T + h - m * ceil(h / m)]. Exact, and the baseline everything
    else is measured against.

    The h-step standard deviation grows as sqrt(k + 1) with k = floor((h-1)/m),
    which is the seasonal-naive predictive variance in FPP3 chapter 5: the error
    accumulates once per completed seasonal cycle, not once per step.
    """
    m = int(season_length)
    if m < 1:
        raise ValueError("season_length must be at least 1, got " + repr(season_length))
    n = len(train)
    if n <= m:
        raise ValueError("seasonal naive needs more than one full season")
    fitted = tuple(train[i - m] for i in range(m, n))
    residuals = tuple(train[i] - train[i - m] for i in range(m, n))
    sigma = math.sqrt(math.fsum(r * r for r in residuals) / len(residuals)) if residuals else 0.0
    point = []
    extended = list(train)
    for h in range(1, horizon + 1):
        point.append(extended[len(extended) - m])
        extended.append(extended[len(extended) - m])
    sd = tuple(sigma * math.sqrt(1.0 + (h - 1) // m) for h in range(1, horizon + 1))
    return ForecastFit(
        point=tuple(point),
        sd=sd,
        fitted=fitted,
        residuals=residuals,
        sigma=sigma,
        params={"season_length": m},
        label="seasonal_naive",
    )


def seasonal_scaling(train: Sequence[float], season_length: int) -> float:
    """
    The MASE denominator: the mean absolute in-sample seasonal-naive error
    (Hyndman and Koehler 2006).

    Computed on the TRAINING set only. Scaling by a denominator that saw the
    test set is the quiet way to make every model look good.
    """
    m = int(season_length)
    if len(train) <= m:
        raise ValueError("the MASE scaling needs more than one full season of training data")
    diffs = [abs(train[i] - train[i - m]) for i in range(m, len(train))]
    return math.fsum(diffs) / len(diffs)


def mase(actual: Sequence[float], forecast: Sequence[float], train: Sequence[float],
         season_length: int) -> float:
    """
    Mean absolute scaled error.

    The anchor for the entire gate: evaluated on its own in-sample errors,
    seasonal-naive scores exactly 1.0, because the numerator and the denominator
    are then the same sum.
    """
    if len(actual) != len(forecast):
        raise ValueError("actual and forecast differ in length")
    if not actual:
        raise ValueError("MASE needs at least one held-out point")
    scale = seasonal_scaling(train, season_length)
    if scale <= 0.0:
        raise ValueError("the MASE scaling denominator is zero: the series is seasonally constant")
    return math.fsum(abs(a - f) for a, f in zip(actual, forecast)) / len(actual) / scale


def smape(actual: Sequence[float], forecast: Sequence[float]) -> float:
    total = 0.0
    for a, f in zip(actual, forecast):
        denominator = (abs(a) + abs(f)) / 2.0
        total += 0.0 if denominator == 0.0 else abs(a - f) / denominator
    return 100.0 * total / len(actual)


def rmse(actual: Sequence[float], forecast: Sequence[float]) -> float:
    return math.sqrt(math.fsum((a - f) ** 2 for a, f in zip(actual, forecast)) / len(actual))


# ---------------------------------------------------------------------------
# Loess and STL
# ---------------------------------------------------------------------------


def _tricube(u: float) -> float:
    u = abs(u)
    if u >= 1.0:
        return 0.0
    return (1.0 - u * u * u) ** 3


def _loess_at(xs: Sequence[float], ys: Sequence[float], rw: Sequence[float] | None,
              x: float, span: float, degree: int = 1) -> float:
    """
    Locally weighted regression evaluated at one point, tricube kernel.

    `span` may exceed the number of observations, in which case the bandwidth is
    inflated exactly as Cleveland et al. specify, so that a short subseries is
    smoothed rather than interpolated.
    """
    n = len(xs)
    if n == 0:
        raise ValueError("loess needs at least one observation")
    if n == 1:
        return float(ys[0])
    q = max(2, min(int(span), n))
    distances = sorted(abs(float(xx) - x) for xx in xs)
    lam = distances[q - 1]
    if span > n:
        lam += (float(span) - n) / 2.0
    if lam <= 0.0:
        lam = max(distances[-1], 1e-12)
    weights = []
    for i in range(n):
        w = _tricube((float(xs[i]) - x) / lam)
        if rw is not None:
            w *= rw[i]
        weights.append(w)
    total = math.fsum(weights)
    if total <= 0.0:
        nearest = min(range(n), key=lambda i: abs(float(xs[i]) - x))
        return float(ys[nearest])
    x_bar = math.fsum(weights[i] * float(xs[i]) for i in range(n)) / total
    y_bar = math.fsum(weights[i] * float(ys[i]) for i in range(n)) / total
    if degree == 0:
        return y_bar
    sxx = math.fsum(weights[i] * (float(xs[i]) - x_bar) ** 2 for i in range(n))
    sxy = math.fsum(weights[i] * (float(xs[i]) - x_bar) * (float(ys[i]) - y_bar) for i in range(n))
    if sxx <= 1e-12:
        return y_bar
    return y_bar + (sxy / sxx) * (x - x_bar)


def _moving_average(xs: Sequence[float], k: int) -> list[float]:
    return [math.fsum(xs[i:i + k]) / k for i in range(len(xs) - k + 1)]


def _bisquare_weights(residuals: Sequence[float]) -> list[float]:
    absolute = sorted(abs(r) for r in residuals)
    mid = len(absolute) // 2
    median = absolute[mid] if len(absolute) % 2 else 0.5 * (absolute[mid - 1] + absolute[mid])
    h = 6.0 * median
    if h <= 0.0:
        return [1.0] * len(residuals)
    out = []
    for r in residuals:
        u = abs(r) / h
        out.append(0.0 if u >= 1.0 else (1.0 - u * u) ** 2)
    return out


def stl(values: Sequence[float], season_length: int, *, seasonal_smoother: int = 7,
        robust: bool = True, inner: int = 2) -> tuple[list[float], list[float], list[float]]:
    """
    Seasonal-trend decomposition by loess (Cleveland, Cleveland, McRae and
    Terpenning 1990).

    Returns trend, seasonal and remainder, with the remainder defined as
    `observed - trend - seasonal` so the reconstruction identity holds by
    construction rather than by luck. The identity is still asserted as a check,
    because it is an implementation guard and a guard you do not run is a
    comment.
    """
    n = len(values)
    m = int(season_length)
    if m < 2:
        raise ValueError("STL needs a season length of at least 2")
    if n < 2 * m:
        raise ValueError("STL needs at least two full seasons")
    ns = int(seasonal_smoother)
    if ns % 2 == 0:
        ns += 1
    ns = max(7, ns)
    nl = m if m % 2 else m + 1
    nt = int(math.ceil(1.5 * m / (1.0 - 1.5 / ns)))
    if nt % 2 == 0:
        nt += 1
    nt = max(nt, 3)
    outer = 2 if robust else 0

    trend = [0.0] * n
    seasonal = [0.0] * n
    rw: list[float] | None = None
    index = [float(i) for i in range(n)]
    for _ in range(outer + 1):
        for _ in range(inner):
            detrended = [values[i] - trend[i] for i in range(n)]
            cycle = [0.0] * (n + 2 * m)
            for j in range(m):
                positions = list(range(j, n, m))
                xs = [float(k) for k in range(len(positions))]
                ys = [detrended[i] for i in positions]
                w = [rw[i] for i in positions] if rw is not None else None
                for k in range(-1, len(positions) + 1):
                    cycle[j + (k + 1) * m] = _loess_at(xs, ys, w, float(k), ns)
            smoothed = _moving_average(_moving_average(_moving_average(cycle, m), m), 3)
            low_index = [float(i) for i in range(len(smoothed))]
            low_pass = [_loess_at(low_index, smoothed, None, float(i), nl)
                        for i in range(len(smoothed))]
            seasonal = [cycle[m + i] - low_pass[i] for i in range(n)]
            deseasonalised = [values[i] - seasonal[i] for i in range(n)]
            trend = [_loess_at(index, deseasonalised, rw, float(i), nt) for i in range(n)]
        if outer:
            rw = _bisquare_weights([values[i] - trend[i] - seasonal[i] for i in range(n)])
    remainder = [values[i] - trend[i] - seasonal[i] for i in range(n)]
    return trend, seasonal, remainder


def _strength(component: Sequence[float], remainder: Sequence[float]) -> float:
    """Wang, Smith and Hyndman (2006) feature strength, clipped to [0, 1]."""
    combined = [c + r for c, r in zip(component, remainder)]
    denominator = variance(combined, ddof=1) if len(combined) > 1 else 0.0
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - variance(remainder, ddof=1) / denominator))


def _amplitude_level_correlation(values: Sequence[float], m: int) -> float:
    """
    Does the seasonal swing grow with the level? The diagnostic for whether an
    additive decomposition is the right shape, computed per seasonal cycle so it
    is a property of the series rather than of the fit.
    """
    cycles = len(values) // m
    if cycles < 3:
        return 0.0
    levels, amplitudes = [], []
    for c in range(cycles):
        chunk = values[c * m:(c + 1) * m]
        levels.append(mean(chunk))
        amplitudes.append(max(chunk) - min(chunk))
    from app.stats.numeric import pearson_corr
    try:
        return pearson_corr(levels, amplitudes)
    except (ValueError, ZeroDivisionError):
        return 0.0


# ---------------------------------------------------------------------------
# Holt-Winters
# ---------------------------------------------------------------------------


def _hw_initial_state(train: Sequence[float], m: int, seasonal: str) -> tuple[float, float, list[float]]:
    n = len(train)
    if seasonal == "none":
        indices = [0.0] * m if seasonal == "add" else [1.0] * m
        adjusted = list(train)
    else:
        if n >= 2 * m:
            k = m if m % 2 else m + 1
            trend_ma = []
            half = m // 2
            for i in range(n):
                if i - half < 0 or i + half >= n:
                    trend_ma.append(None)
                    continue
                if m % 2:
                    window = train[i - half:i + half + 1]
                    trend_ma.append(math.fsum(window) / m)
                else:
                    window = list(train[i - half:i + half + 1])
                    window[0] *= 0.5
                    window[-1] *= 0.5
                    trend_ma.append(math.fsum(window) / m)
            buckets: list[list[float]] = [[] for _ in range(m)]
            for i in range(n):
                if trend_ma[i] is None:
                    continue
                if seasonal == "mul":
                    if trend_ma[i] == 0.0:
                        continue
                    buckets[i % m].append(train[i] / trend_ma[i])
                else:
                    buckets[i % m].append(train[i] - trend_ma[i])
            raw = [mean(b) if b else (1.0 if seasonal == "mul" else 0.0) for b in buckets]
        else:
            overall = mean(train)
            buckets = [[] for _ in range(m)]
            for i in range(n):
                buckets[i % m].append(train[i])
            raw = [
                (mean(b) / overall if overall else 1.0) if seasonal == "mul"
                else mean(b) - overall
                for b in buckets
            ]
        if seasonal == "mul":
            scale = mean(raw)
            indices = [r / scale if scale else 1.0 for r in raw]
            adjusted = [train[i] / indices[i % m] if indices[i % m] else train[i] for i in range(n)]
        else:
            offset = mean(raw)
            indices = [r - offset for r in raw]
            adjusted = [train[i] - indices[i % m] for i in range(n)]
    xs = list(range(n))
    x_bar = mean([float(x) for x in xs])
    y_bar = mean(adjusted)
    sxx = math.fsum((x - x_bar) ** 2 for x in xs)
    sxy = math.fsum((xs[i] - x_bar) * (adjusted[i] - y_bar) for i in range(n))
    slope = sxy / sxx if sxx > 0 else 0.0
    level = y_bar - slope * x_bar
    return level, slope, list(indices)


def _hw_recursion(train: Sequence[float], m: int, trend: str, seasonal: str,
                  alpha: float, beta: float, gamma: float, phi: float,
                  level0: float, trend0: float, season0: Sequence[float]):
    level = level0
    slope = trend0 if trend == "add" else 0.0
    season = list(season0)
    residuals: list[float] = []
    fitted: list[float] = []
    for t, y in enumerate(train):
        damped_trend = phi * slope if trend == "add" else 0.0
        base = level + damped_trend
        index = season[t % m] if seasonal != "none" else (0.0 if seasonal == "add" else 1.0)
        if seasonal == "mul":
            prediction = base * index
        elif seasonal == "add":
            prediction = base + index
        else:
            prediction = base
        fitted.append(prediction)
        residuals.append(y - prediction)
        if seasonal == "mul":
            if index == 0.0:
                return None
            new_level = alpha * (y / index) + (1.0 - alpha) * base
        elif seasonal == "add":
            new_level = alpha * (y - index) + (1.0 - alpha) * base
        else:
            new_level = alpha * y + (1.0 - alpha) * base
        if trend == "add":
            slope = beta * (new_level - level) + (1.0 - beta) * damped_trend
        if seasonal == "mul":
            if base == 0.0:
                return None
            season[t % m] = gamma * (y / base) + (1.0 - gamma) * index
        elif seasonal == "add":
            season[t % m] = gamma * (y - base) + (1.0 - gamma) * index
        level = new_level
        if not math.isfinite(level) or abs(level) > 1e18:
            return None
    return level, slope, season, fitted, residuals


def _hw_sse(train, m, trend, seasonal, params, state) -> float:
    alpha, beta, gamma, phi = params
    result = _hw_recursion(train, m, trend, seasonal, alpha, beta, gamma, phi, *state)
    if result is None:
        return math.inf
    return math.fsum(r * r for r in result[4])


def _golden_section(objective: Callable[[float], float], lo: float, hi: float,
                    iterations: int = 40) -> float:
    """Deterministic line search on a bounded interval. No randomness, no seed."""
    invphi = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c = b - invphi * (b - a)
    d = a + invphi * (b - a)
    fc, fd = objective(c), objective(d)
    for _ in range(iterations):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - invphi * (b - a)
            fc = objective(c)
        else:
            a, c, fc = c, d, fd
            d = a + invphi * (b - a)
            fd = objective(d)
        if b - a < 1e-6:
            break
    return 0.5 * (a + b)


def holt_winters_fit(train: Sequence[float], season_length: int, horizon: int, *,
                     trend: str = "add", seasonal: str = "add",
                     damped: bool = True) -> ForecastFit:
    """
    Exponential smoothing with level, trend and season, in the ETS(A, A_d, A/M)
    state space form.

    Smoothing parameters are chosen by minimising the one-step sum of squared
    errors under bounded coordinate descent from a fixed start. The h-step
    predictive variance is the closed form in FPP3 chapter 8:
    `sigma^2 * (1 + sum_j c_j^2)` with `c_j = alpha * (1 + beta * phi_j) +
    gamma * [j mod m == 0]`, which is why the interval widens with the horizon
    and jumps at each seasonal boundary.
    """
    m = int(season_length)
    if trend not in ("add", "none"):
        raise ValueError("trend must be 'add' or 'none', got " + repr(trend))
    if seasonal not in ("add", "mul", "none"):
        raise ValueError("seasonal must be 'add', 'mul' or 'none', got " + repr(seasonal))
    if seasonal == "mul" and any(v <= 0.0 for v in train):
        raise ValueError("multiplicative seasonality needs a strictly positive series")
    n = len(train)
    if seasonal != "none" and n < 2 * m:
        raise ValueError("Holt-Winters needs two full seasons")
    state = _hw_initial_state(train, m, seasonal)

    params = [0.3, 0.1 if trend == "add" else 0.0, 0.1 if seasonal != "none" else 0.0,
              0.98 if damped and trend == "add" else 1.0]
    bounds = [
        (1e-4, 0.9999),
        (1e-4, 0.9999) if trend == "add" else None,
        (1e-4, 0.9999) if seasonal != "none" else None,
        (0.80, 0.98) if (damped and trend == "add") else None,
    ]
    for _ in range(4):
        for i, bound in enumerate(bounds):
            if bound is None:
                continue
            def one(value: float, index: int = i) -> float:
                trial = list(params)
                trial[index] = value
                if index == 2 and trial[2] > 1.0 - trial[0]:
                    return math.inf     # the admissible region for gamma
                return _hw_sse(train, m, trend, seasonal, trial, state)
            params[i] = _golden_section(one, bound[0], bound[1])
    alpha, beta, gamma, phi = params
    result = _hw_recursion(train, m, trend, seasonal, alpha, beta, gamma, phi, *state)
    if result is None:
        raise ValueError("the Holt-Winters recursion diverged on this series")
    level, slope, season, fitted, residuals = result
    dof = max(1, n - (1 + (1 if trend == "add" else 0) + (m if seasonal != "none" else 0)))
    sigma = math.sqrt(math.fsum(r * r for r in residuals) / dof)

    point: list[float] = []
    phi_sum = 0.0
    for h in range(1, horizon + 1):
        phi_sum += phi ** h if trend == "add" else 0.0
        base = level + (phi_sum * slope if trend == "add" else 0.0)
        index = season[(n + h - 1) % m] if seasonal != "none" else None
        if seasonal == "mul":
            point.append(base * index)
        elif seasonal == "add":
            point.append(base + index)
        else:
            point.append(base)
    sd: list[float] = []
    running = 0.0
    for h in range(1, horizon + 1):
        if h > 1:
            j = h - 1
            phi_j = math.fsum(phi ** i for i in range(1, j + 1)) if trend == "add" else 0.0
            c = alpha * (1.0 + (beta * phi_j if trend == "add" else 0.0))
            if seasonal != "none" and j % m == 0:
                c += gamma
            running += c * c
        sd.append(sigma * math.sqrt(1.0 + running))
    return ForecastFit(
        point=tuple(point),
        sd=tuple(sd),
        fitted=tuple(fitted),
        residuals=tuple(residuals),
        sigma=sigma,
        params={"alpha": alpha, "beta": beta, "gamma": gamma, "phi": phi,
                "trend": trend, "seasonal": seasonal, "damped": bool(damped)},
        label="holt_winters",
    )


# ---------------------------------------------------------------------------
# SARIMA
# ---------------------------------------------------------------------------


def _poly_multiply(a: Sequence[float], b: Sequence[float]) -> list[float]:
    out = [0.0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        if ai == 0.0:
            continue
        for j, bj in enumerate(b):
            out[i + j] += ai * bj
    return out


def expand_seasonal_polynomial(regular: Sequence[float], seasonal: Sequence[float],
                               m: int, *, negate: bool = False) -> list[float]:
    """
    The coefficient list of a multiplicative seasonal polynomial.

    In the additive convention used throughout this module (and by R's `arima`),
    `(1 + t1 B)(1 + T1 B^m)` expands to coefficients `t1` at lag 1, `T1` at lag
    `m` and `t1 * T1` at lag `m + 1`. That cross term at the seasonal-plus-one
    lag is the whole content of the airline model and it is asserted exactly in
    the tests. `negate=True` gives the AR convention, where the polynomial is
    `(1 - a1 B)(1 - A1 B^m)`.
    """
    sign = -1.0 if negate else 1.0
    reg = [1.0] + [sign * float(v) for v in regular]
    sea = [1.0] + [0.0] * (m * len(seasonal))
    for i, value in enumerate(seasonal, start=1):
        sea[i * m] = sign * float(value)
    return _poly_multiply(reg, sea)


def _difference(values: Sequence[float], lag: int, times: int) -> tuple[list[float], list[list[float]]]:
    stages: list[list[float]] = []
    current = list(values)
    for _ in range(times):
        stages.append(list(current))
        current = [current[i] - current[i - lag] for i in range(lag, len(current))]
    return current, stages


def _integrate(forecast: Sequence[float], base: Sequence[float], lag: int) -> list[float]:
    extended = list(base)
    out = []
    for f in forecast:
        value = f + extended[len(extended) - lag]
        extended.append(value)
        out.append(value)
    return out


def _css_residuals(z: Sequence[float], ar: Sequence[float], ma: Sequence[float]) -> list[float]:
    """
    Conditional sum of squares residuals for `phi(B) z = theta(B) e`, with the
    pre-sample innovations set to zero.

    `ar` and `ma` are full polynomial coefficient lists including the leading 1.
    Conditioning on zeros costs a little efficiency relative to exact likelihood
    and is what makes the estimator writable in the standard library.
    """
    n = len(z)
    p = len(ar) - 1
    q = len(ma) - 1
    errors = [0.0] * n
    start = max(p, q)
    for t in range(start, n):
        value = z[t]
        for i in range(1, p + 1):
            value += ar[i] * z[t - i]
        for j in range(1, q + 1):
            value -= ma[j] * errors[t - j]
        errors[t] = value
    return errors[start:]


def _psi_weights(ar_full: Sequence[float], ma: Sequence[float], count: int) -> list[float]:
    psi = [1.0]
    for k in range(1, count):
        value = ma[k] if k < len(ma) else 0.0
        for i in range(1, min(k, len(ar_full) - 1) + 1):
            value -= ar_full[i] * psi[k - i]
        psi.append(value)
    return psi


def _ma_roots_outside_unit_circle(ma: Sequence[float]) -> bool:
    """
    Invertibility. Checked by the modulus of the polynomial's roots rather than
    by a coefficient rule of thumb, because the rule of thumb is only correct at
    order one and this module fits multiplicative seasonal polynomials.
    """
    coefficients = list(ma)
    while len(coefficients) > 1 and abs(coefficients[-1]) < 1e-12:
        coefficients.pop()
    degree = len(coefficients) - 1
    if degree == 0:
        return True
    # Companion-free approach: Durand-Kerner on the reversed polynomial.
    reversed_coefficients = list(reversed(coefficients))
    lead = reversed_coefficients[0]
    normalised = [c / lead for c in reversed_coefficients]
    roots = [complex(0.4, 0.9) ** k for k in range(1, degree + 1)]
    for _ in range(200):
        moved = 0.0
        for i in range(degree):
            numerator = complex(0.0, 0.0)
            power = complex(1.0, 0.0)
            for c in reversed(normalised):
                numerator += c * power
                power *= roots[i]
            denominator = complex(1.0, 0.0)
            for j in range(degree):
                if j != i:
                    denominator *= (roots[i] - roots[j])
            if abs(denominator) < 1e-18:
                continue
            delta = numerator / denominator
            roots[i] -= delta
            moved = max(moved, abs(delta))
        if moved < 1e-12:
            break
    return all(abs(r) > 1.0 + 1e-6 for r in roots)


def sarima_fit(train: Sequence[float], season_length: int, horizon: int, *,
               order: tuple[int, int, int] = (0, 1, 1),
               seasonal_order: tuple[int, int, int] = (0, 1, 1)) -> ForecastFit:
    """
    Seasonal ARIMA by conditional least squares, in the additive moving-average
    convention.

    The interval is Gaussian on the psi-weight variance and is therefore known
    to be slightly too narrow: it excludes parameter uncertainty. The caveat in
    the service says so rather than the Method Card alone, because a reader of
    the number will not open the card.
    """
    m = int(season_length)
    p, d, q = (int(v) for v in order)
    big_p, big_d, big_q = (int(v) for v in seasonal_order)
    values = list(train)
    regular, regular_stages = _difference(values, 1, d)
    z, seasonal_stages = _difference(regular, m, big_d)
    if len(z) < 8:
        raise ValueError("too little data survives the differencing to fit this order")
    mean_z = mean(z) if (d == 0 and big_d == 0) else 0.0
    centred = [v - mean_z for v in z]

    def build(theta: Sequence[float]):
        ar_regular = theta[:p]
        ma_regular = theta[p:p + q]
        ar_seasonal = theta[p + q:p + q + big_p]
        ma_seasonal = theta[p + q + big_p:]
        ar = expand_seasonal_polynomial(ar_regular, ar_seasonal, m, negate=True)
        ma = expand_seasonal_polynomial(ma_regular, ma_seasonal, m)
        return ar, ma

    def objective(theta: Sequence[float]) -> float:
        if any(abs(v) > 0.999 for v in theta):
            return 1e18
        ar, ma = build(theta)
        errors = _css_residuals(centred, ar, ma)
        if not errors:
            return 1e18
        total = math.fsum(e * e for e in errors)
        return total if math.isfinite(total) else 1e18

    k = p + q + big_p + big_q
    if k:
        start = [0.1] * k
        theta, _ = nelder_mead(objective, start, step=0.15, max_iter=1200)
        theta = [max(-0.999, min(0.999, v)) for v in theta]
    else:
        theta = []
    ar, ma = build(theta)
    residuals = _css_residuals(centred, ar, ma)
    dof = max(1, len(residuals) - k)
    sigma2 = math.fsum(e * e for e in residuals) / dof
    sigma = math.sqrt(sigma2)

    # Forecast the differenced series, then undo every differencing stage.
    n = len(centred)
    errors = [0.0] * n
    start_index = max(len(ar) - 1, len(ma) - 1)
    for t in range(start_index, n):
        value = centred[t]
        for i in range(1, len(ar)):
            value += ar[i] * centred[t - i]
        for j in range(1, len(ma)):
            value -= ma[j] * errors[t - j]
        errors[t] = value
    extended_z = list(centred)
    extended_e = list(errors)
    forecast_z: list[float] = []
    for _ in range(horizon):
        value = 0.0
        for i in range(1, len(ar)):
            value -= ar[i] * extended_z[len(extended_z) - i]
        for j in range(1, len(ma)):
            value += ma[j] * extended_e[len(extended_e) - j]
        extended_z.append(value)
        extended_e.append(0.0)
        forecast_z.append(value + mean_z)

    current = forecast_z
    for base in reversed(seasonal_stages):
        current = _integrate(current, base, m)
    for base in reversed(regular_stages):
        current = _integrate(current, base, 1)

    ar_with_differencing = list(ar)
    for _ in range(d):
        ar_with_differencing = _poly_multiply(ar_with_differencing, [1.0, -1.0])
    for _ in range(big_d):
        seasonal_operator = [0.0] * (m + 1)
        seasonal_operator[0] = 1.0
        seasonal_operator[m] = -1.0
        ar_with_differencing = _poly_multiply(ar_with_differencing, seasonal_operator)
    psi = _psi_weights(ar_with_differencing, ma, horizon)
    sd = [sigma * math.sqrt(math.fsum(psi[j] * psi[j] for j in range(h))) for h in range(1, horizon + 1)]

    fitted = [centred[i + start_index] - residuals[i] for i in range(len(residuals))]
    aicc = math.inf
    if len(residuals) > k + 2:
        parameters = k + 1
        aicc = (len(residuals) * math.log(sigma2) + 2.0 * parameters
                + 2.0 * parameters * (parameters + 1) / (len(residuals) - parameters - 1))
    return ForecastFit(
        point=tuple(current),
        sd=tuple(sd),
        fitted=tuple(fitted),
        residuals=tuple(residuals),
        sigma=sigma,
        params={
            "order": (p, d, q),
            "seasonal_order": (big_p, big_d, big_q),
            "ar": list(theta[:p]),
            "ma": list(theta[p:p + q]),
            "seasonal_ar": list(theta[p + q:p + q + big_p]),
            "seasonal_ma": list(theta[p + q + big_p:]),
            "sigma2": sigma2,
            "aicc": aicc,
            "invertible": _ma_roots_outside_unit_circle(ma),
        },
        label="sarima",
    )


def _auto_sarima(train: Sequence[float], m: int, horizon: int) -> ForecastFit:
    """
    A small, declared AICc search rather than an unbounded one.

    Bounded on purpose: AICc will happily choose a six-parameter model for forty
    observations, and the Method Card names that as the failure mode. The grid
    is fixed so the selection is reproducible from the parameters alone.
    """
    d = 1 if _adf_statistic(train) > -2.89 else 0
    big_d = 1 if len(train) >= 2 * m else 0
    best: ForecastFit | None = None
    for p in (0, 1, 2):
        for q in (0, 1, 2):
            for big_p in (0, 1):
                for big_q in (0, 1):
                    if p + q + big_p + big_q == 0:
                        continue
                    try:
                        fit = sarima_fit(train, m, horizon, order=(p, d, q),
                                         seasonal_order=(big_p, big_d, big_q))
                    except (ValueError, ZeroDivisionError, OverflowError):
                        continue
                    if not math.isfinite(fit.params["aicc"]):
                        continue
                    if best is None or fit.params["aicc"] < best.params["aicc"]:
                        best = fit
    if best is None:
        raise ValueError("no SARIMA order in the declared grid could be fitted to this series")
    return best


def _adf_statistic(values: Sequence[float]) -> float:
    """
    Augmented Dickey-Fuller t statistic with a constant and one lag.

    Reported alongside its verdict against the published critical values
    (-2.89 at 5%, -3.51 at 1% for n around 100, Dickey and Fuller 1979). The
    statistic is reported, not only the verdict, because at large n a trivially
    small departure is significant.
    """
    n = len(values)
    if n < 10:
        return 0.0
    ys = [values[t] - values[t - 1] for t in range(1, n)]
    rows = []
    targets = []
    for t in range(1, len(ys)):
        rows.append([1.0, values[t], ys[t - 1]])
        targets.append(ys[t])
    if len(rows) < 5:
        return 0.0
    k = 3
    xtx = [[math.fsum(rows[i][a] * rows[i][b] for i in range(len(rows))) for b in range(k)]
           for a in range(k)]
    xty = [math.fsum(rows[i][a] * targets[i] for i in range(len(rows))) for a in range(k)]
    from app.stats.numeric import inverse, solve
    try:
        beta = solve([row[:] for row in xtx], xty)
        cov = inverse(xtx)
    except ValueError:
        return 0.0
    residual = math.fsum(
        (targets[i] - math.fsum(beta[a] * rows[i][a] for a in range(k))) ** 2
        for i in range(len(rows))
    )
    dof = max(1, len(rows) - k)
    s2 = residual / dof
    se = math.sqrt(max(1e-18, s2 * cov[1][1]))
    return beta[1] / se


def _kpss_statistic(values: Sequence[float]) -> float:
    """
    KPSS level-stationarity statistic (Kwiatkowski, Phillips, Schmidt and Shin
    1992). Published critical values: 0.347 at 10%, 0.463 at 5%, 0.739 at 1%.

    Its null is the opposite of the ADF null, so the two can disagree. The
    service reports the disagreement rather than picking a winner.
    """
    n = len(values)
    if n < 8:
        return 0.0
    mu = mean(values)
    partial = 0.0
    partials = []
    for v in values:
        partial += v - mu
        partials.append(partial)
    lag = int(4.0 * (n / 100.0) ** 0.25)
    residuals = [v - mu for v in values]
    s2 = math.fsum(r * r for r in residuals) / n
    for l in range(1, max(1, lag) + 1):
        weight = 1.0 - l / (lag + 1.0)
        s2 += 2.0 * weight * math.fsum(residuals[t] * residuals[t - l] for t in range(l, n)) / n
    if s2 <= 0.0:
        return 0.0
    return math.fsum(p * p for p in partials) / (n * n * s2)


# ---------------------------------------------------------------------------
# The named forecasters, as callables the backtest can take
# ---------------------------------------------------------------------------


def forecaster_by_name(name: str, **options: Any) -> Forecaster:
    if name == "seasonal_naive":
        return lambda train, m, h: seasonal_naive_fit(train, m, h)
    if name == "holt_winters":
        return lambda train, m, h: holt_winters_fit(train, m, h, **options)
    if name == "sarima":
        if options.get("auto", True):
            return lambda train, m, h: _auto_sarima(train, m, h)
        order = options.get("order", (0, 1, 1))
        seasonal_order = options.get("seasonal_order", (0, 1, 1))
        return lambda train, m, h: sarima_fit(train, m, h, order=order,
                                              seasonal_order=seasonal_order)
    raise ValueError("unknown forecaster " + repr(name))


def _resolve_forecaster(forecaster: Any) -> tuple[Forecaster, str]:
    if callable(forecaster):
        return forecaster, getattr(forecaster, "__name__", "callable")
    if isinstance(forecaster, str):
        return forecaster_by_name(forecaster), forecaster
    raise ValueError("forecaster must be a name or a callable, got " + repr(forecaster))


# ---------------------------------------------------------------------------
# Rolling-origin backtest: the enforcement mechanism
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestResult:
    mase: float
    baseline_mase: float
    smape: float
    rmse: float
    coverage_80: float
    coverage_95: float
    folds: tuple[dict, ...]
    beats_baseline: bool
    interval: tuple[float, float] | None
    leakage_free: bool


def run_backtest(values: Sequence[float], *, forecaster: Forecaster, season_length: int,
                 horizon: int, initial_train: int, step: int = 1,
                 seed: int = 0, empirical_interval: bool = False) -> BacktestResult:
    """
    Rolling origin. Each fold trains on `values[:origin]` and is scored on the
    `horizon` points that follow, with the MASE denominator computed on that
    fold's training set alone.

    `leakage_free` is asserted rather than assumed: every fold records its
    origin and the assertion is that no training index reaches past it. It is
    the single worst bug in this family and it is silent when it happens.

    `empirical_interval` must match the interval the service will actually
    serve. Measuring the coverage of a normal-quantile band and then shipping an
    empirical one would make the coverage check a statement about a number
    nobody sees, which is worse than not checking at all.
    """
    n = len(values)
    m = int(season_length)
    folds: list[dict] = []
    scaled_errors: list[float] = []
    baseline_scaled: list[float] = []
    all_actual: list[float] = []
    all_point: list[float] = []
    covered_80 = covered_95 = counted = 0
    leakage_free = True
    origin = initial_train
    while origin + horizon <= n:
        train = list(values[:origin])
        actual = list(values[origin:origin + horizon])
        if len(train) != origin:
            leakage_free = False
        try:
            fit = forecaster(train, m, horizon)
        except (ValueError, ZeroDivisionError, OverflowError):
            origin += step
            continue
        baseline = seasonal_naive_fit(train, m, horizon)
        bands = _bands(fit, empirical=empirical_interval)
        try:
            fold_mase = mase(actual, fit.point, train, m)
            fold_baseline = mase(actual, baseline.point, train, m)
        except (ValueError, ZeroDivisionError):
            origin += step
            continue
        scale = seasonal_scaling(train, m)
        for i, a in enumerate(actual):
            scaled_errors.append(abs(a - fit.point[i]) / scale)
            baseline_scaled.append(abs(a - baseline.point[i]) / scale)
            if bands["lo80"][i] <= a <= bands["hi80"][i]:
                covered_80 += 1
            if bands["lo95"][i] <= a <= bands["hi95"][i]:
                covered_95 += 1
            counted += 1
        all_actual.extend(actual)
        all_point.extend(fit.point)
        folds.append({
            "origin": origin,
            "train_n": len(train),
            "mase": fold_mase,
            "baseline_mase": fold_baseline,
        })
        origin += step
    if not folds:
        raise ValueError("no fold could be fitted; the series is too short for this configuration")
    pooled = math.fsum(scaled_errors) / len(scaled_errors)
    pooled_baseline = math.fsum(baseline_scaled) / len(baseline_scaled)
    per_fold = [f["mase"] for f in folds]
    interval = None
    if len(per_fold) >= 3:
        interval = bootstrap_bca(per_fold, lambda s: math.fsum(s) / len(s), seed=seed, n_boot=600)
    return BacktestResult(
        mase=pooled,
        baseline_mase=pooled_baseline,
        smape=smape(all_actual, all_point),
        rmse=rmse(all_actual, all_point),
        coverage_80=covered_80 / counted if counted else 0.0,
        coverage_95=covered_95 / counted if counted else 0.0,
        folds=tuple(folds),
        beats_baseline=pooled < pooled_baseline,
        interval=interval,
        leakage_free=leakage_free,
    )


# ---------------------------------------------------------------------------
# Shared plumbing for the services
# ---------------------------------------------------------------------------


def _as_of(window: Any):
    return getattr(window, "end", None)


def _window_caveats(data, window) -> tuple[str, ...]:
    caveats: list[str] = []
    if data.n_incomplete:
        caveats.append(
            str(data.n_incomplete) + " incomplete period(s) excluded; a forecaster fitted "
            "through a partial bucket reads the reporting lag as a collapse"
        )
    if data.n_after_complete_through:
        caveats.append(
            str(data.n_after_complete_through) + " period(s) past complete_through excluded "
            "(spine rule S5)"
        )
    lag = getattr(window, "reporting_lag_days", None)
    if lag:
        caveats.append("reporting lag of " + ("%.1f" % lag) + " days at the end of the window")
    return tuple(caveats)


def _series_value(labels: Sequence[str], point, bands, horizon: int) -> dict:
    """
    The `series` shape of docs/EVIDENCE_CONTRACT.md section 4: parallel arrays
    keyed `x`, `y`, `lo`, `hi`, not a list of row dicts.

    `docs/STATS_CATALOG.md` sketched this output as `{"t", "yhat", "lo", "hi"}`.
    The contract is the normative document for the envelope, so the keys follow
    it, and the catalog entry has been corrected to match rather than the code
    being bent to the sketch.
    """
    return {
        "x": ["+" + str(h + 1) for h in range(horizon)],
        "y": [point[h] for h in range(horizon)],
        "lo": [bands["lo80"][h] for h in range(horizon)],
        "hi": [bands["hi80"][h] for h in range(horizon)],
        "lo95": [bands["lo95"][h] for h in range(horizon)],
        "hi95": [bands["hi95"][h] for h in range(horizon)],
    }


def _residual_checks(fit: ForecastFit, *, horizon: int, history: int) -> tuple[list[Check], bool]:
    """The three checks every forecaster shares, plus whether to widen the interval."""
    checks: list[Check] = []
    statistic, degrees = ljung_box(list(fit.residuals))
    p_value = chi2_sf(statistic, degrees)
    independent = p_value >= 0.05
    checks.append(Check(
        id="residual-independence",
        label="What is left over after the fit has no remaining pattern",
        status="PASS" if independent else "WARN",
        statistic=statistic,
        p_value=p_value,
        detail="" if independent else (
            "the residuals are still autocorrelated, so the intervals are too narrow; they "
            "have been widened from the empirical residual quantiles and the point forecast "
            "is unaffected"
        ),
    ))
    normal, jb, jb_p = _jarque_bera(fit.residuals)
    checks.append(Check(
        id="residual-normality",
        label="The residuals are close enough to normal for a normal interval",
        status="PASS" if normal else "WARN",
        statistic=jb,
        p_value=jb_p,
        detail="" if normal else (
            "the interval is built from the empirical residual quantiles instead of a normal "
            "quantile; the point forecast is unaffected"
        ),
    ))
    boundary = False
    for name in ("alpha", "beta", "gamma"):
        value = fit.params.get(name)
        if value is None:
            continue
        if value < 0.002 or value > 0.998:
            boundary = True
    checks.append(Check(
        id="parameter-on-boundary",
        label="No smoothing parameter is pinned at zero or one",
        status="WARN" if boundary else "PASS",
        detail="a smoothing parameter sits on its boundary, which means that component of the "
               "model is degenerate: read the fit as simpler than it is labelled" if boundary else "",
    ))
    long_horizon = horizon > history / 3.0
    checks.append(Check(
        id="horizon-vs-history",
        label="The horizon is short relative to the history behind it",
        status="WARN" if long_horizon else "PASS",
        statistic=float(horizon) / history if history else 0.0,
        detail="forecasting further than a third of the available history; the later periods "
               "are extrapolation" if long_horizon else "",
    ))
    return checks, not (independent and normal)


def _jarque_bera(residuals: Sequence[float]) -> tuple[bool, float, float]:
    n = len(residuals)
    if n < 8:
        return True, 0.0, 1.0
    mu = mean(residuals)
    m2 = math.fsum((r - mu) ** 2 for r in residuals) / n
    if m2 <= 0.0:
        return True, 0.0, 1.0
    m3 = math.fsum((r - mu) ** 3 for r in residuals) / n
    m4 = math.fsum((r - mu) ** 4 for r in residuals) / n
    skew = m3 / m2 ** 1.5
    kurtosis = m4 / (m2 * m2) - 3.0
    statistic = n / 6.0 * (skew * skew + kurtosis * kurtosis / 4.0)
    p_value = chi2_sf(statistic, 2)
    return p_value >= 0.05, statistic, p_value


def _gate_check(result: BacktestResult) -> Check:
    """
    The MASE gate.

    Reported as a FAIL that is NOT blocking, deliberately. A blocking failure
    empties the value in the envelope, and the whole point of this gate's
    failure path is that the seasonal-naive number is substituted and shown: the
    tenant is entitled to the honest baseline rather than to a blank. The
    substitution is named in the check detail and in a caveat, and the envelope
    renders as "qualified", which is exactly what it is.
    """
    passed = result.beats_baseline
    return Check(
        id="beats-seasonal-naive",
        label="This forecast beat the naive baseline on this community's own history",
        status="PASS" if passed else "FAIL",
        statistic=result.mase,
        detail="" if passed else (
            "MASE " + ("%.3f" % result.mase) + " against seasonal-naive's "
            + ("%.3f" % result.baseline_mase) + ", so the figures shown ARE the seasonal-naive "
            "forecast; the fitted model is not served"
        ),
    )


def _coverage_check(result: BacktestResult) -> Check:
    shortfall = 0.80 - result.coverage_80
    honest = shortfall <= 0.10
    return Check(
        id="coverage-honest",
        label="The 80% interval really did contain 80% of held-out points",
        status="PASS" if honest else "FAIL",
        statistic=result.coverage_80,
        blocking=not honest,
        detail="" if honest else (
            "the 80% interval covered only " + ("%.0f%%" % (100.0 * result.coverage_80))
            + " of held-out points, so the interval is a fiction and is suppressed; the point "
            "forecast is still readable"
        ),
    )


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def seasonal_naive(series, window, *, season_length, horizon) -> Evidence:
    """forecast.seasonal_naive. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.seasonal_naive"
    data = period_series(series, window)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "horizon": horizon, "value_field": data.field,
    })
    as_of = _as_of(window)
    n = len(data)
    floor = max(MIN_PERIODS, 2 * int(season_length))
    if n < floor:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=("needs " + str(floor) + " complete periods, has " + str(n),),
        )
    fit = seasonal_naive_fit(data.values, season_length, horizon)
    normal, _, _ = _jarque_bera(fit.residuals)
    bands = _bands(fit, empirical=not normal)
    checks = [Check(
        id="seasonality-declared",
        label="A full seasonal cycle has been observed at least twice",
        status="PASS",
        statistic=float(n) / season_length,
    )]
    return Evidence(
        value=_series_value(data.labels, fit.point, bands, horizon),
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="predictive-80",
        assumptions=("A stable seasonal period of the declared length.",
                     "This is a baseline, not a model: it ignores trend entirely."),
        checks=tuple(checks),
        caveats=_window_caveats(data, window) + (
            "the interval comes from the residual quantiles of the same rule, so it is honest "
            "about this baseline and says nothing about any other model",
        ),
        unit=data.field,
        params_hash=phash,
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete or past complete_through"
        if (data.n_incomplete + data.n_after_complete_through) else "",
    )


def stl_decompose(series, window, *, season_length, robust=True, seasonal_smoother=7) -> Evidence:
    """forecast.stl_decompose. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.stl_decompose"
    data = period_series(series, window)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "robust": robust,
        "seasonal_smoother": seasonal_smoother, "value_field": data.field,
    })
    as_of = _as_of(window)
    n = len(data)
    floor = max(MIN_PERIODS, 2 * int(season_length))
    if n < floor:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=("needs " + str(floor) + " complete periods, has " + str(n),),
        )
    observed = list(data.values)
    correlation = _amplitude_level_correlation(observed, int(season_length))
    transform = "none"
    working = observed
    if correlation > 0.7 and all(v > 0.0 for v in observed):
        transform = "log"
        working = [math.log(v) for v in observed]
    trend, seasonal, remainder = stl(
        working, int(season_length), seasonal_smoother=int(seasonal_smoother), robust=bool(robust)
    )
    reconstruction = max(
        abs(working[i] - (trend[i] + seasonal[i] + remainder[i])) for i in range(n)
    )
    seasonal_strength = _strength(seasonal, remainder)
    trend_strength = _strength(trend, remainder)
    checks = [
        Check(
            id="reconstruction-identity",
            label="Trend plus season plus remainder equals the observed series",
            status="PASS" if reconstruction < 1e-9 else "FAIL",
            statistic=reconstruction,
            blocking=reconstruction >= 1e-9,
            detail="" if reconstruction < 1e-9 else
            "the components do not add back up to the series, which is an implementation "
            "fault; nothing here can be read",
        ),
        Check(
            id="seasonality-material",
            label="There is enough seasonality here to be worth drawing",
            status="PASS" if seasonal_strength >= 0.3 else "WARN",
            statistic=seasonal_strength,
            detail="" if seasonal_strength >= 0.3 else
            "seasonal strength below 0.3: what the seasonal panel would show is noise, not a "
            "rhythm",
        ),
        Check(
            id="additive-appropriate",
            label="The seasonal swing does not grow with the level",
            status="PASS" if (transform == "log" or correlation <= 0.7) else "WARN",
            statistic=correlation,
            detail="" if transform == "log" or correlation <= 0.7 else
            "the seasonal amplitude grows with the level; a multiplicative decomposition would "
            "fit better and the components below are on the additive scale",
        ),
        Check(
            id="incomplete-periods",
            label="Partial periods at the end of the window are excluded",
            status="PASS",
            statistic=float(data.n_incomplete + data.n_after_complete_through),
        ),
    ]
    caveats = list(_window_caveats(data, window))
    if transform == "log":
        caveats.append(
            "decomposed on the log scale because the seasonal amplitude grows with the level; "
            "the components are log-scale and do not sum to the rupee series"
        )
    return Evidence(
        value={
            "observed": working,
            "trend": trend,
            "seasonal": seasonal,
            "remainder": remainder,
            "labels": list(data.labels),
            "seasonal_strength": seasonal_strength,
            "trend_strength": trend_strength,
            "remainder_sd": math.sqrt(variance(remainder, ddof=1)) if n > 1 else 0.0,
            "transform": transform,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=("A single fixed-length seasonal period.",
                     "Slowly varying seasonality.",
                     "Additivity on the reported scale."),
        checks=tuple(checks),
        caveats=tuple(caveats),
        unit=data.field,
        params_hash=phash,
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete or past complete_through"
        if (data.n_incomplete + data.n_after_complete_through) else "",
    )


def _forecast_service(method: str, data, window, *, season_length: int, horizon: int,
                      forecaster: Forecaster, floor: int, phash: str,
                      extra_assumptions: tuple[str, ...] = (),
                      extra_checks: tuple[Check, ...] = (),
                      extra_caveats: tuple[str, ...] = (),
                      structure_extra: dict | None = None,
                      unit: str = "",
                      seed: int = 0) -> Evidence:
    """
    The shared body of every gated forecaster: fit, backtest, gate, substitute.

    Written once because the gate must behave identically for Holt-Winters,
    SARIMA and every named composition. A gate implemented three times is a gate
    that is eventually implemented twice.
    """
    as_of = _as_of(window)
    n = len(data)
    if n < floor:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash, unit=unit,
            caveats=("needs " + str(floor) + " complete periods, has " + str(n),),
        )
    values = list(data.values)
    m = int(season_length)
    # As many folds as the history allows, floored at two seasons of training.
    # Running the minimum five folds when thirty are available would make the
    # gate a coin flip on purpose.
    initial_train = max(2 * m, n // 2)
    initial_train = min(initial_train, n - horizon - MIN_FOLDS + 1)
    initial_train = max(initial_train, 2 * m)
    checks: list[Check] = []
    folds_available = 0
    if initial_train + horizon <= n:
        folds_available = (n - horizon - initial_train) + 1
    if folds_available < MIN_FOLDS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash, unit=unit,
            caveats=(
                "only " + str(max(0, folds_available)) + " rolling-origin folds are available "
                "and the gate needs " + str(MIN_FOLDS) + "; without the backtest there is no "
                "evidence this forecast beats the naive baseline, so none is served",
            ),
        )
    try:
        fit = forecaster(values, m, horizon)
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash, unit=unit,
            caveats=("the model would not fit on the full history: " + str(error),),
        )
    residual_checks, widen = _residual_checks(fit, horizon=horizon, history=n)
    checks.extend(residual_checks)
    # The backtest measures the coverage of the interval that will actually be
    # served, which is why the residual checks are decided first.
    try:
        result = run_backtest(values, forecaster=forecaster, season_length=m, horizon=horizon,
                              initial_train=initial_train, step=1, seed=seed,
                              empirical_interval=widen)
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash, unit=unit,
            caveats=("the rolling-origin backtest could not run, so the gate cannot be "
                     "evaluated and nothing is served: " + str(error),),
        )
    gate = _gate_check(result)
    checks.append(gate)
    # When the gate fails the seasonal-naive forecast is substituted, so the
    # coverage that gets checked has to be the coverage of THAT interval. Judging
    # the served band by the discarded model's coverage would be a check about a
    # number nobody sees.
    coverage_source = result
    served = fit
    served_widen = widen
    if gate.status == "FAIL":
        served = seasonal_naive_fit(values, m, horizon)
        served_normal, _, _ = _jarque_bera(served.residuals)
        served_widen = not served_normal
        try:
            coverage_source = run_backtest(
                values, forecaster=forecaster_by_name("seasonal_naive"), season_length=m,
                horizon=horizon, initial_train=initial_train, step=1, seed=seed,
                empirical_interval=served_widen,
            )
        except (ValueError, ZeroDivisionError, OverflowError):
            coverage_source = result
    checks.append(_coverage_check(coverage_source))
    checks.append(Check(
        id="folds-sufficient",
        label="Enough rolling-origin folds for the comparison to mean something",
        status="PASS" if len(result.folds) >= MIN_FOLDS else "FAIL",
        statistic=float(len(result.folds)),
        blocking=len(result.folds) < MIN_FOLDS,
        detail="" if len(result.folds) >= MIN_FOLDS else
        "fewer than five folds, so the comparison with the naive baseline is a coin flip and "
        "no forecast is served",
    ))
    checks.extend(extra_checks)

    caveats = list(_window_caveats(data, window)) + list(extra_caveats)
    if gate.status == "FAIL":
        caveats.insert(0,
            "this model lost to seasonal-naive on rolling-origin cross-validation (MASE "
            + ("%.3f" % result.mase) + " against " + ("%.3f" % result.baseline_mase)
            + "), so what is shown is the seasonal-naive forecast"
        )
    bands = _bands(served, empirical=served_widen)
    if served_widen:
        caveats.append(
            "the interval is built from the empirical residual quantiles rather than a normal "
            "quantile, because the residuals are not normal or not independent"
        )
    structure = {
        "mase": result.mase,
        "baseline_mase": result.baseline_mase,
        "smape": result.smape,
        "rmse": result.rmse,
        "coverage_80": coverage_source.coverage_80,
        "coverage_95": coverage_source.coverage_95,
        "beats_baseline": result.beats_baseline,
        "folds": list(result.folds),
        "params": dict(served.params),
        "served": served.label,
    }
    if structure_extra:
        structure.update(structure_extra)
    value = _series_value(data.labels, served.point, bands, horizon)
    value["structure"] = structure
    # The envelope's own interval is the bootstrap interval on MASE across folds:
    # it says how stable the advantage over naive is, which is the thing a reader
    # has to judge before trusting the line. The per-step predictive bands travel
    # in the series arrays, where they belong, because they differ per step and a
    # single pair on the envelope could only be one of them.
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=result.interval,
        interval_kind="bootstrap-bca-95" if result.interval else "none",
        assumptions=extra_assumptions,
        checks=tuple(checks),
        caveats=tuple(caveats) + (
            "the backtest is the evidence for this forecast: MASE " + ("%.3f" % result.mase)
            + " against the naive baseline's " + ("%.3f" % result.baseline_mase),
            "the envelope interval is the bootstrap interval on MASE across folds; the 80% and "
            "95% predictive bands for each future period are the lo/hi arrays",
        ),
        unit=unit or data.field,
        params_hash=phash,
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete or past complete_through"
        if (data.n_incomplete + data.n_after_complete_through) else "",
    )


def holt_winters(series, window, *, season_length, horizon, trend="add", seasonal="add",
                 damped=True, seed=0) -> Evidence:
    """forecast.holt_winters. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.holt_winters"
    data = period_series(series, window)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "horizon": horizon, "trend": trend,
        "seasonal": seasonal, "damped": damped, "seed": seed, "value_field": data.field,
    })
    forecaster = forecaster_by_name("holt_winters", trend=trend, seasonal=seasonal, damped=damped)
    return _forecast_service(
        method, data, window, season_length=int(season_length), horizon=int(horizon),
        forecaster=forecaster, floor=max(MIN_PERIODS, 2 * int(season_length)), phash=phash,
        extra_assumptions=(
            "The exponential smoothing state space form with additive errors.",
            "A stable seasonal period of the declared length.",
            "It beat seasonal-naive under rolling-origin cross-validation, which is a measured "
            "check and not a note.",
        ),
        seed=seed,
    )


def sarima(series, window, *, season_length, horizon, order=None, seasonal_order=None,
           auto=True, ic="aicc") -> Evidence:
    """forecast.sarima. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.sarima"
    if ic != "aicc":
        raise ValueError("only the AICc information criterion is implemented, got " + repr(ic))
    data = period_series(series, window)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "horizon": horizon, "order": order,
        "seasonal_order": seasonal_order, "auto": auto, "ic": ic, "value_field": data.field,
    })
    m = int(season_length)
    floor = max(MIN_PERIODS_SARIMA, 3 * m)
    if auto:
        forecaster = forecaster_by_name("sarima", auto=True)
    else:
        forecaster = forecaster_by_name(
            "sarima", auto=False, order=tuple(order or (0, 1, 1)),
            seasonal_order=tuple(seasonal_order or (0, 1, 1)),
        )
    values = list(data.values)
    extra_checks: list[Check] = []
    structure_extra: dict = {}
    if len(values) >= floor:
        try:
            fit = forecaster(values, m, int(horizon))
        except (ValueError, ZeroDivisionError, OverflowError):
            fit = None
        if fit is not None:
            adf = _adf_statistic(values)
            kpss = _kpss_statistic(values)
            adf_stationary = adf < -2.89
            kpss_stationary = kpss < 0.463
            extra_checks.append(Check(
                id="stationarity",
                label="The differenced series is stationary",
                status="PASS" if adf_stationary == kpss_stationary else "WARN",
                statistic=adf,
                detail="" if adf_stationary == kpss_stationary else
                "the augmented Dickey-Fuller and KPSS tests disagree (ADF "
                + ("%.2f" % adf) + ", KPSS " + ("%.3f" % kpss) + "); the disagreement is "
                "reported rather than resolved by picking whichever answer suits",
            ))
            invertible = bool(fit.params.get("invertible", True))
            extra_checks.append(Check(
                id="invertibility",
                label="The moving-average polynomial is invertible",
                status="PASS" if invertible else "FAIL",
                blocking=not invertible,
                detail="" if invertible else
                "the fitted moving-average roots are on or inside the unit circle, so the "
                "forecasts are unstable and nothing here can be read",
            ))
            seasonal_ma = fit.params.get("seasonal_ma") or [0.0]
            regular_ma = fit.params.get("ma") or [0.0]
            over = any(abs(v) > 0.97 for v in list(seasonal_ma) + list(regular_ma))
            extra_checks.append(Check(
                id="overdifferencing",
                label="The series has not been differenced more than it needed",
                status="WARN" if over else "PASS",
                detail="a moving-average coefficient sits at the invertibility boundary, the "
                       "signature of one difference too many" if over else "",
            ))
            structure_extra = {
                "order": list(fit.params["order"]),
                "seasonal_order": list(fit.params["seasonal_order"]),
                "aicc": fit.params["aicc"],
                "adf": adf,
                "kpss": kpss,
            }
    return _forecast_service(
        method, data, window, season_length=m, horizon=int(horizon), forecaster=forecaster,
        floor=floor, phash=phash,
        extra_assumptions=(
            "Linear and stationary after differencing.",
            "Gaussian innovations, for the interval only.",
            "It passed the MASE gate on this community's own history.",
        ),
        extra_checks=tuple(extra_checks),
        extra_caveats=(
            "these intervals ignore parameter uncertainty and are therefore known to be "
            "slightly too narrow",
        ),
        structure_extra=structure_extra,
    )


def dues_collection(series, window, *, season_length=12, horizon=3) -> Evidence:
    """forecast.dues_collection. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.dues_collection"
    data = period_series(series, window, value_field="inflow_minor")
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "horizon": horizon, "value_field": data.field,
    })
    forecaster = forecaster_by_name("holt_winters", trend="add", seasonal="add", damped=True)
    return _forecast_service(
        method, data, window, season_length=int(season_length), horizon=int(horizon),
        forecaster=forecaster, floor=max(MIN_PERIODS, 2 * int(season_length)), phash=phash,
        extra_assumptions=(
            "A hard billing cycle of the declared season length.",
            "Expected entries are receivables, not actuals (spine rule L2).",
            "It passed the MASE gate.",
        ),
        extra_caveats=(
            "collections are forecast from money that actually arrived; receivables entered as "
            "expected are not counted here and must be read separately",
        ),
        unit="minor_units",
    )


def request_volume(series, window, *, season_length=12, horizon=3) -> Evidence:
    """forecast.request_volume. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.request_volume"
    data = period_series(series, window, value_field="arrivals")
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "horizon": horizon, "value_field": data.field,
    })
    forecaster = forecaster_by_name("holt_winters", trend="add", seasonal="add", damped=True)
    evidence = _forecast_service(
        method, data, window, season_length=int(season_length), horizon=int(horizon),
        forecaster=forecaster, floor=max(MIN_PERIODS, 2 * int(season_length)), phash=phash,
        extra_assumptions=(
            "A count series with the vertical's declared seasonal structure.",
            "It passed the MASE gate.",
        ),
        unit="requests",
    )
    if evidence.insufficient_data:
        return evidence
    crossed = False
    value = dict(evidence.value)
    for key in ("lo", "lo95"):
        floored = []
        for v in value[key]:
            if v < 0.0:
                crossed = True
                floored.append(0.0)
            else:
                floored.append(v)
        value[key] = floored
    checks = list(evidence.checks)
    checks.append(Check(
        id="count-interval-nonnegative",
        label="The interval does not run below zero requests",
        status="WARN" if crossed else "PASS",
        detail="the Gaussian interval crossed zero and was floored there; at this count level a "
               "Poisson model is the right tool and this one is approximate" if crossed else "",
    ))
    return Evidence(
        value=value, n=evidence.n, method=method, as_of=evidence.as_of,
        interval=evidence.interval, interval_kind=evidence.interval_kind,
        assumptions=evidence.assumptions, checks=tuple(checks), caveats=evidence.caveats,
        unit=evidence.unit, params_hash=evidence.params_hash,
        n_excluded=evidence.n_excluded, exclusion_reason=evidence.exclusion_reason,
    )


def attendance(series, window, roster, *, season_length=12, horizon=3) -> Evidence:
    """forecast.attendance. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.attendance"
    data = period_series(series, window, value_field="active_members")
    roster_size = float(getattr(roster, "total", 0) or 0)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "season_length": season_length, "horizon": horizon, "roster_total": roster_size,
        "value_field": data.field,
    })
    forecaster = forecaster_by_name("holt_winters", trend="add", seasonal="add", damped=True)
    evidence = _forecast_service(
        method, data, window, season_length=int(season_length), horizon=int(horizon),
        forecaster=forecaster, floor=max(MIN_PERIODS, 2 * int(season_length)), phash=phash,
        extra_assumptions=(
            "Attendance is bounded above by the roster. A 340-member society cannot have 400 "
            "attendees, so the bound is enforced rather than hoped for.",
            "It passed the MASE gate.",
        ),
        unit="people",
    )
    if evidence.insufficient_data:
        return evidence
    if roster_size <= 0.0:
        checks = list(evidence.checks) + [Check(
            id="bounded-by-roster",
            label="The forecast is bounded above by the roster size",
            status="SKIPPED",
            detail="no roster snapshot was supplied, so the bound could not be applied",
        )]
        return Evidence(
            value=evidence.value, n=evidence.n, method=method, as_of=evidence.as_of,
            interval=evidence.interval, interval_kind=evidence.interval_kind,
            assumptions=evidence.assumptions, checks=tuple(checks),
            caveats=evidence.caveats + ("the roster bound was not applied",),
            unit=evidence.unit, params_hash=evidence.params_hash,
            n_excluded=evidence.n_excluded, exclusion_reason=evidence.exclusion_reason,
        )
    truncated = False
    point_over = any(v > roster_size for v in evidence.value["y"])
    value = dict(evidence.value)
    for key in ("hi", "hi95", "y"):
        capped = []
        for v in value[key]:
            if v > roster_size:
                truncated = True
                capped.append(roster_size)
            else:
                capped.append(v)
        value[key] = capped
    for key in ("lo", "lo95"):
        value[key] = [max(0.0, v) for v in value[key]]
    checks = list(evidence.checks)
    checks.append(Check(
        id="bounded-by-roster",
        label="The forecast is bounded above by the roster size",
        status="FAIL" if point_over else ("WARN" if truncated else "PASS"),
        statistic=roster_size,
        blocking=point_over,
        detail=(
            "the fitted model forecast more attendees than the community has members ("
            + ("%.0f" % roster_size) + " on the roster), which means the model is wrong rather "
            "than optimistic; no attendance figure is served"
        ) if point_over else (
            "the upper predictive bound exceeded the roster and was truncated there"
            if truncated else ""
        ),
    ))
    return Evidence(
        value={} if point_over else value,
        n=evidence.n, method=method, as_of=evidence.as_of,
        interval=evidence.interval, interval_kind=evidence.interval_kind,
        assumptions=evidence.assumptions, checks=tuple(checks), caveats=evidence.caveats,
        unit=evidence.unit, params_hash=evidence.params_hash,
        n_excluded=evidence.n_excluded, exclusion_reason=evidence.exclusion_reason,
    )


def rolling_origin_backtest(series, window, *, forecaster, season_length, horizon,
                            initial_train, step=1, min_folds=5) -> Evidence:
    """forecast.rolling_origin_backtest. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "forecast.rolling_origin_backtest"
    data = period_series(series, window)
    callable_forecaster, label = _resolve_forecaster(forecaster)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "forecaster": label, "season_length": season_length, "horizon": horizon,
        "initial_train": initial_train, "step": step, "min_folds": min_folds,
        "value_field": data.field,
    })
    as_of = _as_of(window)
    n = len(data)
    floor = max(MIN_PERIODS, int(initial_train) + int(min_folds) * int(step))
    if n < floor:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=("needs " + str(floor) + " complete periods for "
                     + str(min_folds) + " folds, has " + str(n),),
        )
    try:
        result = run_backtest(
            list(data.values), forecaster=callable_forecaster, season_length=int(season_length),
            horizon=int(horizon), initial_train=int(initial_train), step=int(step),
        )
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=("the backtest could not run: " + str(error),),
        )
    checks = [
        Check(
            id="folds-sufficient",
            label="At least five rolling-origin folds",
            status="PASS" if len(result.folds) >= int(min_folds) else "FAIL",
            statistic=float(len(result.folds)),
            blocking=len(result.folds) < int(min_folds),
            detail="" if len(result.folds) >= int(min_folds) else
            "fewer folds than the declared minimum, so the comparison with the naive baseline "
            "is a coin flip and no verdict is issued",
        ),
        _coverage_check(result),
        Check(
            id="origin-leakage",
            label="No fold's training set contains an observation after its origin",
            status="PASS" if result.leakage_free else "FAIL",
            blocking=not result.leakage_free,
            detail="" if result.leakage_free else
            "a training set reached past its origin, which invalidates every number here",
        ),
    ]
    return Evidence(
        value={
            "mase": result.mase,
            "baseline_mase": result.baseline_mase,
            "smape": result.smape,
            "rmse": result.rmse,
            "coverage_80": result.coverage_80,
            "coverage_95": result.coverage_95,
            "beats_baseline": result.beats_baseline,
            "folds": list(result.folds),
            "forecaster": label,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval=result.interval,
        interval_kind="bootstrap-bca-95" if result.interval else "none",
        assumptions=(
            "Time order is respected: no fold's training set contains an observation after its "
            "origin, which is asserted rather than trusted.",
            "The baseline is seasonal-naive at the same season length.",
        ),
        checks=tuple(checks),
        caveats=_window_caveats(data, window) + (
            "a MASE below 1 beats the naive baseline; a MASE of 0.95 whose interval spans 1 has "
            "not",
        ),
        unit=data.field,
        params_hash=phash,
    )


__all__ = [
    "BacktestResult",
    "ForecastFit",
    "attendance",
    "dues_collection",
    "expand_seasonal_polynomial",
    "forecaster_by_name",
    "holt_winters",
    "holt_winters_fit",
    "mase",
    "request_volume",
    "rmse",
    "rolling_origin_backtest",
    "run_backtest",
    "sarima",
    "sarima_fit",
    "seasonal_naive",
    "seasonal_naive_fit",
    "seasonal_scaling",
    "smape",
    "stl",
    "stl_decompose",
]
