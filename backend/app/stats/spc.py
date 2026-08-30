"""
Statistical process control over periodised counts.

Control limits are a decision boundary, not an estimate: interval_kind is
"control-limits" and the Method Cards say what that means. The limit constant is
solved for a stated in-control average run length rather than defaulted to
3 sigma.

That distinction is the whole point of this module. A weekly chart on 3 sigma
false-alarms about once every 370 periods in theory, which is seven years, and
constantly in practice because weekly complaint counts are neither normal nor
independent. Solving L for a declared ARL0 makes the trade-off explicit and
puts the attained run length in the envelope where a reader can see it.

Average run lengths come from the Brook and Evans (1972) Markov-chain
approximation, which is the method Lucas and Saccucci used to build the
published tables this module is tested against.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Any, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import (
    chi2_sf,
    mean,
    nbinom_ppf,
    norm_cdf,
    poisson_ppf,
    solve,
    variance,
)
from app.stats.series import (
    lag_autocorrelation,
    ljung_box,
    moving_range_sigma,
    period_series,
)

MIN_PERIODS = 20
MIN_MEAN_COUNT = 5.0
OVERDISPERSION_LIMIT = 1.5

# Three-sigma-equivalent tails, used by the Poisson chart so that its exact
# quantiles are comparable with the textbook c-chart they replace.
POISSON_TAIL = 0.00135


# ---------------------------------------------------------------------------
# Average run lengths
# ---------------------------------------------------------------------------


def ewma_arl(lam: float, limit: float, *, shift: float = 0.0, grid: int = 101) -> float:
    """
    In-control (shift = 0) or out-of-control average run length of a two-sided
    EWMA chart with asymptotic limits at +/- limit * sigma * sqrt(lam/(2-lam)).

    Brook and Evans: discretize the interval between the control limits into
    `grid` states, build the one-step transition matrix, and solve
    (I - P) * ARL = 1. The chart starts on target, so the answer is the state at
    the centre.
    """
    if not 0.0 < lam <= 1.0:
        raise ValueError("lam must be in (0, 1], got " + repr(lam))
    if grid % 2 == 0:
        grid += 1                      # an odd grid puts a state exactly on target
    sigma_z = math.sqrt(lam / (2.0 - lam))
    upper = limit * sigma_z
    width = 2.0 * upper / grid
    centres = [-upper + width * (j + 0.5) for j in range(grid)]
    matrix = [[0.0] * grid for _ in range(grid)]
    for i, si in enumerate(centres):
        base = (1.0 - lam) * si
        for j, sj in enumerate(centres):
            hi = (sj + width / 2.0 - base) / lam - shift
            lo = (sj - width / 2.0 - base) / lam - shift
            probability = norm_cdf(hi) - norm_cdf(lo)
            matrix[i][j] = (1.0 if i == j else 0.0) - probability
    return solve(matrix, [1.0] * grid)[grid // 2]


def solve_ewma_limit(lam: float, target_arl0: float, *, grid: int = 101) -> float:
    """
    The limit constant L that gives the requested in-control average run length.

    Bisection on a monotone function, which is the whole algorithm. It exists so
    that `target_arl0` is a declared parameter of the chart rather than 3 being
    an inherited habit.
    """
    if target_arl0 < 10:
        raise ValueError("target_arl0 below 10 makes every chart a false alarm")
    lo, hi = 1.0, 6.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if ewma_arl(lam, mid, grid=grid) < target_arl0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-4:
            break
    return 0.5 * (lo + hi)


def _cusum_one_sided_arl(k: float, h: float, shift: float, grid: int) -> float:
    step = h / grid
    centres = [(j + 0.5) * step for j in range(grid)]
    matrix = [[0.0] * grid for _ in range(grid)]
    for i, si in enumerate(centres):
        for j, sj in enumerate(centres):
            hi = sj + step / 2.0 - si + k - shift
            if j == 0:
                probability = norm_cdf(hi)          # the reflecting barrier at zero
            else:
                lo = sj - step / 2.0 - si + k - shift
                probability = norm_cdf(hi) - norm_cdf(lo)
            matrix[i][j] = (1.0 if i == j else 0.0) - probability
    return solve(matrix, [1.0] * grid)[0]


def cusum_arl(k: float, h: float, *, shift: float = 0.0, grid: int = 60) -> float:
    """
    Two-sided CUSUM average run length, combining the two one-sided chains by
    1/ARL = 1/ARL+ + 1/ARL-.

    Brook and Evans converges slowly from below for the in-control run length,
    so the answer is Richardson-extrapolated from grids of `grid` and 2 * grid.
    Without that, reproducing the published ARL0 of 465 needs a matrix large
    enough to make the service slow.
    """
    def two_sided(size: int) -> float:
        up = _cusum_one_sided_arl(k, h, shift, size)
        down = _cusum_one_sided_arl(k, h, -shift, size)
        return 1.0 / (1.0 / up + 1.0 / down)

    coarse = two_sided(grid)
    fine = two_sided(2 * grid)
    return 2.0 * fine - coarse


# ---------------------------------------------------------------------------
# Shared chart preparation
# ---------------------------------------------------------------------------


def _baseline_checks(values: Sequence[float], baseline: Sequence[float], lam: float,
                     limit: float, target_arl0: float, signals_in_baseline: int,
                     incomplete: int) -> list[Check]:
    checks: list[Check] = [
        Check(
            id="baseline-stability",
            label="The baseline used to set the limits was itself in control",
            status="FAIL" if signals_in_baseline else "PASS",
            statistic=float(signals_in_baseline),
            blocking=bool(signals_in_baseline),
            detail=(
                str(signals_in_baseline) + " of the baseline periods are themselves out of "
                "control, which inflates the limits and blinds the chart. Pick a quiet baseline "
                "window with the baseline_periods parameter; a chart that says everything is "
                "fine because its own limits are too wide is worse than no chart."
            ) if signals_in_baseline else "",
        ),
    ]
    rho = lag_autocorrelation(baseline, 1)
    stat, df = ljung_box(baseline)
    p_value = chi2_sf(stat, df)
    if p_value < 0.05 and rho > 0.0:
        # Var(EWMA of an AR(1) series) = sigma^2 * lam/(2-lam) * (1+rho*a)/(1-rho*a)
        # with a = 1 - lam, by summing the geometric double series. The limits
        # were set for the independent case, so the attained run length is the
        # one for a chart whose limit constant is L divided by that inflation.
        a = 1.0 - lam
        inflation = math.sqrt((1.0 + rho * a) / max(1e-9, 1.0 - rho * a))
        try:
            attained = ewma_arl(lam, limit / inflation)
        except ValueError:
            attained = float("nan")
        checks.append(Check(
            id="residual-autocorrelation",
            label="Baseline observations are independent",
            status="WARN",
            statistic=rho,
            p_value=p_value,
            detail=(
                "lag-1 autocorrelation " + format(rho, ".2f") + " (Ljung-Box p="
                + format(p_value, ".4f") + "). The limits were solved for an in-control run "
                "length of " + format(target_arl0, ".0f") + " periods, but with this much "
                "autocorrelation the attained run length is nearer "
                + format(attained, ".0f") + ", so the chart signals more often than it claims."
            ),
        ))
    else:
        checks.append(Check(
            id="residual-autocorrelation",
            label="Baseline observations are independent",
            status="PASS", statistic=rho, p_value=p_value,
        ))
    if incomplete:
        checks.append(Check(
            id="incomplete-periods",
            label="Only complete periods are plotted",
            status="WARN",
            statistic=float(incomplete),
            detail=(
                str(incomplete) + " periods are not complete yet and were excluded. Plotting a "
                "partial final period reads the reporting lag as a collapse in the process."
            ),
        ))
    else:
        checks.append(Check(
            id="incomplete-periods", label="Only complete periods are plotted",
            status="PASS", statistic=0.0,
        ))
    if values:
        m = mean(values)
        if m > 0 and all(float(v).is_integer() and v >= 0 for v in values):
            dispersion = variance(values) / m
            checks.append(Check(
                id="overdispersion",
                label="Count variation is consistent with a Poisson process",
                status="WARN" if dispersion > OVERDISPERSION_LIMIT else "PASS",
                statistic=dispersion,
                detail=(
                    "variance over mean is " + format(dispersion, ".2f")
                    + ", above " + format(OVERDISPERSION_LIMIT, ".1f")
                    + ". For counts, spc.poisson_rate_chart with negative-binomial limits is "
                    "the better chart."
                ) if dispersion > OVERDISPERSION_LIMIT else "",
            ))
    return checks


def _blocked(checks: Sequence[Check]) -> bool:
    return any(c.status == "FAIL" and c.blocking for c in checks)


def _window_params(window: Any) -> dict[str, Any]:
    return {
        "window_start": getattr(window, "start", None),
        "window_end": getattr(window, "end", None),
        "complete_through": getattr(window, "complete_through", None),
    }


def _as_of(window: Any):
    return getattr(window, "end", None)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def ewma_chart(series, window, *, lam=0.2, target_arl0=500, baseline_periods=None,
               value_field=None) -> Evidence:
    """spc.ewma_chart. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "spc.ewma_chart"
    data = period_series(series, window, value_field=value_field)
    phash = params_hash(method, 1, {**_window_params(window), "lam": lam,
                                    "target_arl0": target_arl0,
                                    "baseline_periods": baseline_periods,
                                    "value_field": data.field})
    as_of = _as_of(window)
    n = len(data)
    empty = {"points": [], "ewma": [], "center": None, "ucl": None, "lcl": None, "signals": []}
    if n < MIN_PERIODS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("needs " + str(MIN_PERIODS) + " complete periods, has " + str(n),),
        )

    values = list(data.values)
    baseline = values[:baseline_periods] if baseline_periods else values
    if len(baseline) < 2:
        baseline = values
    centre = mean(baseline)
    sigma = moving_range_sigma(baseline)
    limit = solve_ewma_limit(lam, target_arl0)
    sigma_z = sigma * math.sqrt(lam / (2.0 - lam))
    ucl, lcl = centre + limit * sigma_z, centre - limit * sigma_z

    statistic: list[float] = []
    z = centre
    for v in values:
        z = lam * v + (1.0 - lam) * z
        statistic.append(z)
    signals = [
        {"index": i, "at": data.labels[i], "value": values[i], "ewma": statistic[i],
         "direction": "above" if statistic[i] > ucl else "below"}
        for i in range(n) if statistic[i] > ucl or statistic[i] < lcl
    ]
    baseline_signals = sum(1 for s in signals if s["index"] < len(baseline))

    checks = _baseline_checks(values, baseline, lam, limit, target_arl0,
                              baseline_signals, data.n_incomplete)
    value: dict[str, Any] = {
        "points": values,
        "at": list(data.labels),
        "ewma": statistic,
        "center": centre,
        "ucl": ucl,
        "lcl": lcl,
        "sigma": sigma,
        "lam": lam,
        "limit_constant": limit,
        "target_arl0": float(target_arl0),
        "attained_arl0": ewma_arl(lam, limit),
        "signals": signals,
    }
    if _blocked(checks):
        value = dict(empty)
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="control-limits",
        assumptions=(
            "Independent observations in the baseline period.",
            "A stable in-control mean and variance during that baseline.",
            "The limit constant was solved for a stated in-control average run length, not set "
            "to three sigma out of habit.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete_period" if (data.n_incomplete or data.n_after_complete_through) else "",
        unit=data.field,
        params_hash=phash,
    )


def cusum_chart(series, window, *, k=0.5, h=5.0, baseline_periods=None,
                value_field=None) -> Evidence:
    """spc.cusum_chart. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "spc.cusum_chart"
    data = period_series(series, window, value_field=value_field)
    phash = params_hash(method, 1, {**_window_params(window), "k": k, "h": h,
                                    "baseline_periods": baseline_periods,
                                    "value_field": data.field})
    as_of = _as_of(window)
    n = len(data)
    empty = {"points": [], "c_hi": [], "c_lo": [], "h": h, "signals": []}
    if n < MIN_PERIODS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("needs " + str(MIN_PERIODS) + " complete periods, has " + str(n),),
        )
    values = list(data.values)
    baseline = values[:baseline_periods] if baseline_periods else values
    if len(baseline) < 2:
        baseline = values
    centre = mean(baseline)
    sigma = moving_range_sigma(baseline)
    if sigma <= 0.0:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("every period has the same value, so there is no variation to chart",),
        )

    c_hi: list[float] = []
    c_lo: list[float] = []
    hi = lo = 0.0
    for v in values:
        z = (v - centre) / sigma
        hi = max(0.0, hi + z - k)
        lo = max(0.0, lo - z - k)
        c_hi.append(hi)
        c_lo.append(lo)
    signals = [
        {"index": i, "at": data.labels[i], "value": values[i],
         "direction": "above" if c_hi[i] > h else "below"}
        for i in range(n) if c_hi[i] > h or c_lo[i] > h
    ]
    baseline_signals = sum(1 for s in signals if s["index"] < len(baseline))
    arl0 = cusum_arl(k, h)
    checks = _baseline_checks(values, baseline, 0.2, 3.0, arl0, baseline_signals,
                              data.n_incomplete)
    value: dict[str, Any] = {
        "points": values,
        "at": list(data.labels),
        "c_hi": c_hi,
        "c_lo": c_lo,
        "h": h,
        "k": k,
        "center": centre,
        "sigma": sigma,
        "attained_arl0": arl0,
        "arl1_one_sigma": cusum_arl(k, h, shift=1.0),
        "signals": signals,
    }
    if _blocked(checks):
        value = dict(empty)
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="control-limits",
        assumptions=(
            "Independent observations in the baseline period.",
            "A stable in-control mean, since the reference value k is set from it.",
            "The decision interval h is in sigma units and is declared, not fitted.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete_period" if (data.n_incomplete or data.n_after_complete_through) else "",
        unit=data.field,
        params_hash=phash,
    )


def poisson_rate_chart(series, window, *, exposure_field="exposure_days", dispersion="auto",
                       value_field=None) -> Evidence:
    """spc.poisson_rate_chart. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "spc.poisson_rate_chart"
    data = period_series(series, window, value_field=value_field, exposure_field=exposure_field)
    phash = params_hash(method, 1, {**_window_params(window), "exposure_field": exposure_field,
                                    "dispersion": dispersion, "value_field": data.field})
    as_of = _as_of(window)
    n = len(data)
    empty = {"points": [], "rates": [], "center": None, "ucl": [], "lcl": [], "signals": []}
    average = mean(data.values) if n else 0.0
    if n < MIN_PERIODS or average < MIN_MEAN_COUNT:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            unit="events per unit exposure",
            caveats=(
                "needs " + str(MIN_PERIODS) + " periods averaging at least "
                + format(MIN_MEAN_COUNT, ".0f") + " events each; has " + str(n)
                + " periods averaging " + format(average, ".1f"),
            ),
        )

    counts = list(data.values)
    exposure = list(data.exposure)
    total_exposure = math.fsum(exposure)
    centre_rate = math.fsum(counts) / total_exposure
    ratio = variance(counts) / mean(counts)
    overdispersed = dispersion == "negative_binomial" or (
        dispersion == "auto" and ratio > OVERDISPERSION_LIMIT
    )

    ucl: list[float] = []
    lcl: list[float] = []
    for e in exposure:
        expected = centre_rate * e
        if overdispersed:
            # Method of moments: match the observed variance-to-mean ratio.
            prob = min(0.999, max(1e-6, 1.0 / ratio))
            r = expected * prob / (1.0 - prob)
            upper = nbinom_ppf(1.0 - POISSON_TAIL, r, prob)
            lower = nbinom_ppf(POISSON_TAIL, r, prob)
        else:
            upper = poisson_ppf(1.0 - POISSON_TAIL, expected)
            lower = poisson_ppf(POISSON_TAIL, expected)
            lower = max(0, lower - 1)     # ppf is the smallest k reaching p
        ucl.append(upper / e)
        lcl.append(max(0.0, lower / e))

    rates = [c / e for c, e in zip(counts, exposure)]
    signals = [
        {"index": i, "at": data.labels[i], "value": counts[i], "rate": rates[i],
         "direction": "above" if rates[i] > ucl[i] else "below"}
        for i in range(n) if rates[i] > ucl[i] or rates[i] < lcl[i]
    ]
    unequal = len(set(round(e, 9) for e in exposure)) > 1
    checks = [
        Check(
            id="overdispersion",
            label="Count variation is consistent with a Poisson process",
            status="WARN" if overdispersed else "PASS",
            statistic=ratio,
            detail=(
                "variance over mean is " + format(ratio, ".2f") + ", so the limits are "
                "negative-binomial rather than Poisson. Poisson limits here would flag ordinary "
                "month-to-month variation as a special cause."
            ) if overdispersed else "",
        ),
        Check(
            id="unequal-exposure",
            label="Periods of different length get different limits",
            status="PASS",
            statistic=float(max(exposure) / min(exposure)) if min(exposure) > 0 else 1.0,
            detail=(
                "period lengths differ, which they do whenever the period is a calendar month, "
                "so this is a u-chart with limits that vary by period rather than a c-chart "
                "with one pair of lines."
            ) if unequal else "",
        ),
        Check(
            id="exact-quantile-limits",
            label="Limits are exact quantiles, not a normal approximation",
            status="PASS",
            statistic=average,
            detail=(
                "the average count is " + format(average, ".1f") + "; the textbook 3-sigma "
                "c-chart approximation is poor below about five and would change conclusions, "
                "so the limits are exact quantiles."
            ),
        ),
    ]
    if data.n_incomplete:
        checks.append(Check(
            id="incomplete-periods", label="Only complete periods are plotted", status="WARN",
            statistic=float(data.n_incomplete),
            detail=str(data.n_incomplete) + " incomplete periods were excluded",
        ))
    return Evidence(
        value={
            "points": counts,
            "at": list(data.labels),
            "exposure": exposure,
            "rates": rates,
            "center": centre_rate,
            "ucl": ucl,
            "lcl": lcl,
            "distribution": "negative-binomial" if overdispersed else "poisson",
            "dispersion_ratio": ratio,
            "signals": signals,
        },
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="control-limits",
        assumptions=(
            "Counts are Poisson with a rate proportional to exposure, unless the overdispersion "
            "check switches the limits to negative binomial and says so.",
            "Exposure per period is known and carried on the period, not assumed equal.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        n_excluded=data.n_incomplete + data.n_after_complete_through,
        exclusion_reason="incomplete_period" if (data.n_incomplete or data.n_after_complete_through) else "",
        unit="events per unit exposure",
        params_hash=phash,
    )


__all__ = [
    "cusum_arl",
    "cusum_chart",
    "ewma_arl",
    "ewma_chart",
    "poisson_rate_chart",
    "solve_ewma_limit",
]
