"""
Simulation over ledger periods and forecast envelopes. Seeded, always.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

The one modelling choice worth stating up front: inflow and outflow shocks are
drawn JOINTLY with the correlation estimated from the ledger. If collections
fall in the same month that maintenance spend rises, independent sampling
understates the shortfall probability badly, and understating it is the
direction that costs a community money.
"""
import math
import random
from typing import Any, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import mean, norm_cdf, norm_ppf, pearson_corr, percentile

MIN_LEDGER_PERIODS = 12

# The 80% predictive band spans this many standard deviations either side.
Z80 = norm_ppf(0.9)


def _forecast_arrays(forecast: Any, horizon: int) -> tuple[list[float], list[float], bool]:
    """
    Pull per-period means and standard deviations out of a forecast Evidence.

    The standard deviation is recovered from the 80% predictive band rather than
    from any hidden field, so this works against any forecaster in the pack and
    against a hand-built envelope in a test. Returns the gate verdict too,
    because a runway probability built on a forecast that lost to naive is
    precision theatre.
    """
    if forecast is None:
        raise ValueError("a runway simulation needs both an inflow and an outflow forecast")
    value = getattr(forecast, "value", forecast)
    if not isinstance(value, dict) or "y" not in value:
        raise ValueError(
            "the forecast Evidence does not carry a series value; runway_shortfall consumes "
            "the output of a forecast service, not a bare number"
        )
    y = [float(v) for v in value["y"]][:horizon]
    lo = [float(v) for v in value.get("lo", [])][:horizon]
    hi = [float(v) for v in value.get("hi", [])][:horizon]
    if len(y) < horizon:
        raise ValueError(
            "the forecast covers " + str(len(y)) + " periods but the horizon is "
            + str(horizon) + "; stats/ does not extrapolate a forecast it was handed"
        )
    sd = []
    for i in range(horizon):
        if i < len(lo) and i < len(hi) and hi[i] > lo[i]:
            sd.append((hi[i] - lo[i]) / (2.0 * Z80))
        else:
            sd.append(0.0)
    passed = True
    for check in getattr(forecast, "checks", ()):
        if check.id == "beats-seasonal-naive" and check.status == "FAIL":
            passed = False
    return y, sd, passed


def _correlated_normals(rng: random.Random, rho: float) -> tuple[float, float]:
    """Two standard normals with correlation rho, by the Cholesky factor of a 2x2."""
    a = rng.gauss(0.0, 1.0)
    b = rng.gauss(0.0, 1.0)
    return a, rho * a + math.sqrt(max(0.0, 1.0 - rho * rho)) * b


def first_passage_probability(drift: float, sigma: float, distance: float, horizon: float) -> float:
    """
    The continuously monitored first-passage probability for Brownian motion
    with drift: the reflection-principle formula whose density is the inverse
    Gaussian.

    `distance` is how far the floor sits BELOW the opening balance and is
    positive. This is the continuous-time answer and it is an upper bound on
    what a ledger monitored at period ends can detect, since a path may dip
    below the floor and recover inside a single month. The service monitors at
    period ends, because that is when a treasurer actually looks, and the tests
    use this formula as the upper end of a bracket rather than as the target.
    """
    if sigma <= 0.0 or horizon <= 0.0 or distance <= 0.0:
        return 0.0
    b = -abs(distance)
    root = sigma * math.sqrt(horizon)
    first = norm_cdf((b - drift * horizon) / root)
    exponent = 2.0 * drift * b / (sigma * sigma)
    if exponent < -700.0:
        return first
    second = math.exp(exponent) * norm_cdf((b + drift * horizon) / root)
    return max(0.0, min(1.0, first + second))


def terminal_shortfall_probability(drift: float, sigma: float, distance: float,
                                   horizon: int) -> float:
    """
    The exact probability that the balance is below the floor AT the end of the
    horizon, for a Gaussian random walk: `Phi((-distance - h * drift) /
    (sigma * sqrt(h)))`.

    A closed form with no approximation in it, which is why it is the anchor the
    simulator is checked against.
    """
    if sigma <= 0.0 or horizon <= 0:
        return 1.0 if -distance - horizon * drift >= 0.0 else 0.0
    return norm_cdf((-distance - horizon * drift) / (sigma * math.sqrt(horizon)))


def simulate_balance_paths(opening: float, inflow_mean: Sequence[float],
                           inflow_sd: Sequence[float], outflow_mean: Sequence[float],
                           outflow_sd: Sequence[float], *, floor: float, rho: float,
                           draws: int, seed: int) -> dict:
    """
    Draw `draws` balance paths, monitored at period ends, and summarise them.

    Seeded and therefore exactly reproducible: the seed is part of `params_hash`
    so the same run reproduces byte for byte.
    """
    horizon = len(inflow_mean)
    rng = random.Random(seed)
    shortfalls = 0
    first_periods: list[float] = []
    by_period: list[list[float]] = [[] for _ in range(horizon)]
    for _ in range(draws):
        balance = opening
        hit = None
        for h in range(horizon):
            z_in, z_out = _correlated_normals(rng, rho)
            inflow = inflow_mean[h] + inflow_sd[h] * z_in
            outflow = outflow_mean[h] + outflow_sd[h] * z_out
            balance += inflow - outflow
            by_period[h].append(balance)
            if hit is None and balance < floor:
                hit = h + 1
        if hit is not None:
            shortfalls += 1
            first_periods.append(float(hit))
    quantiles = []
    for h in range(horizon):
        ordered = sorted(by_period[h])
        quantiles.append({
            "period": h + 1,
            "p05": percentile(ordered, 0.05),
            "p50": percentile(ordered, 0.50),
            "p95": percentile(ordered, 0.95),
        })
    first_periods.sort()
    return {
        "p_shortfall": shortfalls / draws,
        "first_shortfall_period_p50": percentile(first_periods, 0.5) if first_periods else None,
        "first_shortfall_lo": percentile(first_periods, 0.025) if first_periods else None,
        "first_shortfall_hi": percentile(first_periods, 0.975) if first_periods else None,
        "balance_paths_quantiles": quantiles,
    }


def runway_shortfall(opening_balance_minor, inflow_forecast, outflow_forecast, ledger_periods,
                     *, horizon, seed, floor_minor=0, draws=20000) -> Evidence:
    """montecarlo.runway_shortfall. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "montecarlo.runway_shortfall"
    horizon = int(horizon)
    phash = params_hash(method, 1, {
        "opening_balance_minor": int(opening_balance_minor), "horizon": horizon,
        "floor_minor": int(floor_minor), "draws": int(draws), "seed": int(seed),
        "inflow_params_hash": getattr(inflow_forecast, "params_hash", ""),
        "outflow_params_hash": getattr(outflow_forecast, "params_hash", ""),
    })
    as_of = getattr(inflow_forecast, "as_of", None) or getattr(outflow_forecast, "as_of", None)
    periods = list(ledger_periods or ())
    n = len(periods)
    if getattr(inflow_forecast, "insufficient_data", False) or getattr(
        outflow_forecast, "insufficient_data", False
    ):
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=("one of the two forecasts could not be produced, so there is nothing to "
                     "simulate from",),
        )
    inflow_mean, inflow_sd, inflow_passed = _forecast_arrays(inflow_forecast, horizon)
    outflow_mean, outflow_sd, outflow_passed = _forecast_arrays(outflow_forecast, horizon)

    rho = 0.0
    correlation_estimable = n >= MIN_LEDGER_PERIODS
    if correlation_estimable:
        inflows = [float(p.inflow_minor) for p in periods]
        outflows = [abs(float(p.outflow_minor)) for p in periods]
        try:
            rho = pearson_corr(inflows, outflows)
        except (ValueError, ZeroDivisionError):
            rho = 0.0
            correlation_estimable = False

    expected_share = 0.0
    total_inflow = math.fsum(inflow_mean)
    if total_inflow > 0.0:
        receivable = math.fsum(
            float(getattr(p, "by_category", {}).get("expected", 0)) for p in periods
        )
        historic = math.fsum(float(p.inflow_minor) for p in periods) or 1.0
        expected_share = min(1.0, abs(receivable) / abs(historic))

    gate_passed = inflow_passed and outflow_passed
    checks = [
        Check(
            id="forecast-gate-inherited",
            label="Both input forecasts beat the naive baseline",
            status="PASS" if gate_passed else "FAIL",
            blocking=not gate_passed,
            detail="" if gate_passed else
            "at least one input forecast lost to seasonal-naive, and a runway probability built "
            "on a forecast that loses to naive is precision theatre; no probability is served",
        ),
        Check(
            id="correlation-estimable",
            label="Enough ledger history to estimate the inflow-outflow correlation",
            status="PASS" if correlation_estimable else "WARN",
            statistic=rho,
            detail="" if correlation_estimable else
            "fewer than " + str(MIN_LEDGER_PERIODS) + " ledger periods, so inflow and outflow "
            "are drawn independently; if collections fall in the same month maintenance spend "
            "rises, this UNDERSTATES the shortfall probability",
        ),
        Check(
            id="expected-entries-share",
            label="How much of the projected inflow is receivable rather than received",
            status="PASS" if expected_share < 0.5 else "WARN",
            statistic=expected_share,
            detail="" if expected_share < 0.5 else
            "a large share of the projected inflow is entries marked expected, which are "
            "receivables and not actuals (spine rule L2)",
        ),
        Check(
            id="seed-recorded",
            label="The simulation is reproducible from its recorded parameters",
            status="PASS",
            statistic=float(seed),
        ),
    ]
    if not gate_passed:
        return Evidence(
            value={},
            n=n,
            method=method,
            as_of=as_of,
            interval_kind="none",
            assumptions=("Both input forecasts passed the MASE gate.",),
            checks=tuple(checks),
            caveats=("the inputs did not qualify, so no shortfall probability is computed",),
            unit="probability",
            params_hash=phash,
        )
    result = simulate_balance_paths(
        float(opening_balance_minor), inflow_mean, inflow_sd, outflow_mean, outflow_sd,
        floor=float(floor_minor), rho=rho, draws=int(draws), seed=int(seed),
    )
    interval = None
    if result["first_shortfall_lo"] is not None:
        interval = (result["first_shortfall_lo"], result["first_shortfall_hi"])
    value = dict(result)
    value["correlation"] = rho
    value["draws"] = int(draws)
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=interval,
        interval_kind="predictive-95" if interval else "none",
        assumptions=(
            "The forecast predictive distributions are correct, and both passed the MASE gate.",
            "Inflow and outflow shocks are drawn jointly with the estimated correlation.",
            "Committed outflows are treated as certain and are disclosed separately from "
            "forecast ones.",
            "The balance is monitored at period ends, which is when a treasurer looks. A path "
            "that dips below the floor and recovers inside one month is not counted.",
        ),
        checks=tuple(checks),
        caveats=(
            "p_shortfall is a probability under the model, not a frequency observed anywhere",
            "the interval is on the FIRST shortfall period over simulated paths and widens fast",
            "no emergency assessment is modelled mid-horizon, which is exactly what a committee "
            "would do and would change the answer",
        ),
        unit="probability",
        params_hash=phash,
    )


__all__ = [
    "first_passage_probability",
    "runway_shortfall",
    "simulate_balance_paths",
    "terminal_shortfall_probability",
]
