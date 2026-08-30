"""
Queueing models over request_flow.

Every service here needs active_servers, which comes from the declared cross-stream
reducer app/stats/streams/capacity.py rather than being inferred inside this module.
"How many resolvers do you actually have" is the least well-defined input in Pack 1,
so its definition is part of each Method Card.

Two rules run through the whole module. First, an unstable queue has no finite
expected wait, so the stability check is blocking everywhere: reporting a number
for a queue whose backlog grows without bound is a lie, and the minimum team size
that would stabilise it is the useful answer instead. Second, a service rate
estimated from closed requests only is optimistic, so `service-time-censoring` is
always a WARN and never silent, with the censoring-aware figure from
`survival.km_resolution_curve` offered as the honest alternative.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Any, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import bootstrap_bca, mean, ols_slope, variance
from app.stats.series import period_series

MIN_PERIODS = 8
MIN_CLOSED_SPELLS = 30


# ---------------------------------------------------------------------------
# Closed forms
# ---------------------------------------------------------------------------


def erlang_b(servers: int, offered_load: float) -> float:
    """
    Erlang's loss formula, by the numerically stable recursion
    B(n, a) = a B(n-1, a) / (n + a B(n-1, a)), B(0, a) = 1.

    Published check values: B(1, 1) = 0.5, B(2, 1) = 0.2, B(3, 1) = 0.0625.
    """
    if servers < 0:
        raise ValueError("servers cannot be negative")
    b = 1.0
    for n in range(1, servers + 1):
        b = offered_load * b / (n + offered_load * b)
    return b


def erlang_c(servers: int, offered_load: float) -> float:
    """
    The probability that an arrival has to wait at all, from Erlang B. Returns
    1.0 for an unstable queue, where every arrival eventually waits forever.
    """
    if servers <= 0:
        return 1.0
    rho = offered_load / servers
    if rho >= 1.0:
        return 1.0
    b = erlang_b(servers, offered_load)
    return b / (1.0 - rho * (1.0 - b))


def erlang_c_service_level(servers: int, offered_load: float, target_over_service: float) -> float:
    """
    P(wait <= target) = 1 - C * exp(-(c - a) * target / mean_service_time).

    `target_over_service` is the target answered in units of the mean service
    time, which is what makes the formula scale-free.
    """
    if servers <= offered_load:
        return 0.0
    return 1.0 - erlang_c(servers, offered_load) * math.exp(
        -(servers - offered_load) * target_over_service
    )


def mmc_wait_in_queue(arrival_rate: float, service_rate: float, servers: int) -> float:
    """Expected time in queue for M/M/c: C / (c*mu - lambda)."""
    offered = arrival_rate / service_rate
    if servers <= offered:
        return math.inf
    return erlang_c(servers, offered) / (servers * service_rate - arrival_rate)


def pollaczek_khinchine_wait(arrival_rate: float, service_mean: float,
                             service_var: float) -> float:
    """M/G/1 expected time in queue: lambda (var + mean^2) / (2 (1 - rho))."""
    rho = arrival_rate * service_mean
    if rho >= 1.0:
        return math.inf
    return arrival_rate * (service_var + service_mean ** 2) / (2.0 * (1.0 - rho))


# ---------------------------------------------------------------------------
# Shared checks
# ---------------------------------------------------------------------------


def _stability_check(arrival_rate: float, service_rate: float, servers: float) -> Check:
    capacity = servers * service_rate
    rho = arrival_rate / capacity if capacity > 0 else math.inf
    if rho >= 1.0:
        needed = math.floor(arrival_rate / service_rate) + 1 if service_rate > 0 else None
        return Check(
            id="stability",
            label="Capacity exceeds demand, so a finite wait exists",
            status="FAIL",
            statistic=rho,
            blocking=True,
            detail=(
                "arrivals exceed capacity (utilisation "
                + (format(rho, ".2f") if math.isfinite(rho) else "infinite")
                + "). The backlog grows without bound and no wait time exists to report. "
                + ("It would take at least " + str(needed) + " active servers to stabilise the "
                   "queue." if needed else "")
            ),
        )
    return Check(
        id="stability",
        label="Capacity exceeds demand, so a finite wait exists",
        status="WARN" if rho > 0.9 else "PASS",
        statistic=rho,
        detail=(
            "utilisation is " + format(rho, ".2f") + ". Above 0.9 the expected wait is extremely "
            "sensitive to small changes in either rate, so read the figure as an order of "
            "magnitude, not a promise."
        ) if rho > 0.9 else "",
    )


def _censoring_check() -> Check:
    return Check(
        id="service-time-censoring",
        label="The service rate is estimated from closed requests only",
        status="WARN",
        detail=(
            "the mean service time can only be measured on requests that finished, which makes "
            "it optimistic: the slow ones are still open. Read it beside the "
            "censoring-aware figure from survival.km_resolution_curve, which counts them."
        ),
    )


def _service_shape_check(service_cv: float | None) -> Check:
    if service_cv is None:
        return Check(
            id="exponential-service",
            label="Service times are roughly exponential",
            status="SKIPPED",
            detail="no service-time sample was supplied, so the shape could not be tested",
        )
    if service_cv > 2.0:
        return Check(
            id="exponential-service", label="Service times are roughly exponential",
            status="FAIL", statistic=service_cv, blocking=False,
            detail=(
                "the coefficient of variation of service time is " + format(service_cv, ".2f")
                + ", far above the 1.0 that M/M/c assumes. This model understates the wait by "
                "roughly the factor (1 + cv^2)/2. Use queueing.mg1_wait, which takes the "
                "variance as an input."
            ),
        )
    status = "PASS" if 0.5 <= service_cv <= 1.5 else "WARN"
    return Check(
        id="exponential-service", label="Service times are roughly exponential",
        status=status, statistic=service_cv,
        detail=(
            "the coefficient of variation of service time is " + format(service_cv, ".2f")
            + "; M/M/c assumes 1.0, so the wait is understated when it is above and overstated "
            "when it is below."
        ) if status == "WARN" else "",
    )


def _arrival_check(counts: Sequence[float] | None) -> Check:
    if not counts or len(counts) < 3:
        return Check(
            id="poisson-arrivals", label="Arrivals are Poisson",
            status="SKIPPED", detail="no per-period arrival counts were supplied",
        )
    m = mean(counts)
    if m <= 0:
        return Check(id="poisson-arrivals", label="Arrivals are Poisson",
                     status="SKIPPED", detail="no arrivals in the window")
    dispersion = variance(counts) / m
    if 0.5 <= dispersion <= 1.5:
        return Check(id="poisson-arrivals", label="Arrivals are Poisson",
                     status="PASS", statistic=dispersion)
    direction = ("bursty: arrivals cluster, so the real wait is longer than this model says"
                 if dispersion > 1.5 else
                 "smoother than Poisson, so the real wait is shorter than this model says")
    return Check(
        id="poisson-arrivals", label="Arrivals are Poisson", status="WARN",
        statistic=dispersion,
        detail="variance over mean of the arrival counts is " + format(dispersion, ".2f")
               + ", " + direction,
    )


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


def little_law_wait(periods, window, *, seed=0) -> Evidence:
    """queueing.little_law_wait. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "queueing.little_law_wait"
    phash = params_hash(method, 1, {**_window_params(window), "seed": seed})
    as_of = _as_of(window)
    usable = [p for p in periods if getattr(p, "complete", True)]
    n = len(usable)
    if n < MIN_PERIODS:
        return insufficient(
            method, n=n, as_of=as_of, unit="days", params_hash=phash,
            caveats=("needs " + str(MIN_PERIODS) + " complete periods, has " + str(n),),
        )
    backlogs = [float(p.backlog_end) for p in usable]
    rates = [float(p.arrival_rate_per_day) for p in usable]
    average_rate = mean(rates)
    if average_rate <= 0.0:
        return insufficient(
            method, n=n, as_of=as_of, unit="days", params_hash=phash,
            caveats=("no arrivals in the window, so there is no wait to report",),
        )

    def statistic(sample) -> float:
        rate = mean([r for _, r in sample])
        if rate <= 0.0:
            raise ValueError("degenerate resample")
        return mean([b for b, _ in sample]) / rate

    pairs = list(zip(backlogs, rates))
    value = statistic(pairs)
    lo, hi = bootstrap_bca(pairs, statistic, seed=seed, n_boot=800)

    slope, se, p_value = ols_slope(list(range(n)), backlogs)
    trending = p_value < 0.05 and abs(slope) > 0.0
    checks = [
        Check(
            id="steady-state",
            label="The backlog has no trend, so a long-run average wait exists",
            status="FAIL" if trending else "PASS",
            statistic=slope,
            p_value=p_value,
            blocking=trending,
            detail=(
                "the backlog moved from " + format(backlogs[0], ".0f") + " to "
                + format(backlogs[-1], ".0f") + " over this window (slope "
                + format(slope, ".2f") + " per period, p=" + format(p_value, ".4f")
                + "). There is no steady-state wait to report: the queue is "
                + ("diverging" if slope > 0 else "draining")
                + ", and that sentence is more useful than a number."
            ) if trending else "",
        ),
    ]
    return Evidence(
        value=None if trending else value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None if trending else (lo, hi),
        interval_kind="none" if trending else "bootstrap-bca-95",
        assumptions=(
            "The system is in steady state over the window: arrivals and departures balance and "
            "the backlog has no trend. That is the whole assumption, and it is the one that fails.",
            "No arrival distribution and no service distribution are assumed. Little's Law is an "
            "identity.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        unit="days",
        params_hash=phash,
    )


def mmc_metrics(arrival_rate, service_rate, servers, window, *, service_cv=None, seed=0,
                service_samples=None, arrival_counts=None) -> Evidence:
    """queueing.mmc_metrics. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "queueing.mmc_metrics"
    phash = params_hash(method, 1, {**_window_params(window), "arrival_rate": arrival_rate,
                                    "service_rate": service_rate, "servers": servers,
                                    "service_cv": service_cv, "seed": seed})
    as_of = _as_of(window)
    n = len(service_samples) if service_samples else 0
    empty = {"utilisation": None, "p_wait": None, "lq": None, "wq_days": None,
             "w_days": None, "l": None}
    if service_samples is not None and n < MIN_CLOSED_SPELLS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("needs " + str(MIN_CLOSED_SPELLS) + " closed spells to estimate the "
                     "service rate, has " + str(n),),
        )
    whole_servers = int(math.floor(servers))
    if whole_servers < 1:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("fewer than one full-time-equivalent server is active, so there is no "
                     "queue discipline to model",),
        )

    checks = [
        _stability_check(arrival_rate, service_rate, whole_servers),
        _arrival_check(arrival_counts),
        _service_shape_check(
            service_cv if service_cv is not None
            else (math.sqrt(variance(service_samples)) / mean(service_samples)
                  if service_samples and len(service_samples) > 2 and mean(service_samples) > 0
                  else None)
        ),
        _censoring_check(),
    ]
    offered = arrival_rate / service_rate
    if _blocked(checks):
        blocking = next(c for c in checks if c.status == "FAIL" and c.blocking)
        return Evidence(
            value=empty, n=n, method=method, as_of=as_of, interval=None, interval_kind="none",
            assumptions=("Utilisation below 1, or no finite wait exists.",),
            checks=tuple(checks), caveats=(blocking.detail,),
            unit="days", params_hash=phash,
        )

    p_wait = erlang_c(whole_servers, offered)
    wq = mmc_wait_in_queue(arrival_rate, service_rate, whole_servers)
    w = wq + 1.0 / service_rate
    value = {
        "utilisation": offered / whole_servers,
        "p_wait": p_wait,
        "lq": arrival_rate * wq,          # Little's Law applied to the queue alone
        "wq_days": wq,
        "w_days": w,
        "l": arrival_rate * w,
        "servers": whole_servers,
        "offered_load": offered,
    }
    interval = None
    if service_samples and len(service_samples) >= MIN_CLOSED_SPELLS:
        def statistic(sample) -> float:
            m = mean(sample)
            if m <= 0.0:
                raise ValueError("degenerate resample")
            rate = 1.0 / m
            if whole_servers * rate <= arrival_rate:
                raise ValueError("unstable resample")
            return mmc_wait_in_queue(arrival_rate, rate, whole_servers)

        interval = bootstrap_bca(list(service_samples), statistic, seed=seed, n_boot=400)
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=interval,
        interval_kind="bootstrap-bca-95" if interval else "none",
        assumptions=(
            "Poisson arrivals, exponential service, c identical servers.",
            "No priority ordering, no abandonment, unlimited queue capacity.",
            "Utilisation below 1, or no finite wait exists.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        unit="days",
        params_hash=phash,
    )


def erlang_c_staffing(arrival_rate, mean_service_time, window, *, current_servers,
                      target_fraction=0.9, target_within_days=5.0, max_servers=200,
                      seed=0, service_samples=None, arrival_counts=None,
                      category_mix=None) -> Evidence:
    """queueing.erlang_c_staffing. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "queueing.erlang_c_staffing"
    phash = params_hash(method, 1, {**_window_params(window), "arrival_rate": arrival_rate,
                                    "mean_service_time": mean_service_time,
                                    "target_fraction": target_fraction,
                                    "target_within_days": target_within_days,
                                    "max_servers": max_servers, "seed": seed})
    as_of = _as_of(window)
    n = len(service_samples) if service_samples else 0
    empty = {"required_servers": None, "current_servers": current_servers, "gap": None,
             "attained_at_current": None, "attained_at_required": None, "curve": []}
    if service_samples is not None and n < MIN_CLOSED_SPELLS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("needs " + str(MIN_CLOSED_SPELLS) + " closed spells for the service time, "
                     "has " + str(n),),
        )
    if mean_service_time <= 0.0 or arrival_rate <= 0.0:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("a positive arrival rate and mean service time are required",),
        )

    offered = arrival_rate * mean_service_time
    ratio = target_within_days / mean_service_time
    service_rate = 1.0 / mean_service_time
    checks = [
        _stability_check(arrival_rate, service_rate, max(1.0, math.floor(current_servers))),
        _arrival_check(arrival_counts),
        _service_shape_check(
            math.sqrt(variance(service_samples)) / mean(service_samples)
            if service_samples and len(service_samples) > 2 and mean(service_samples) > 0
            else None
        ),
        _censoring_check(),
    ]
    if category_mix:
        # servers-are-fungible: how concentrated each resolver's category mix is.
        # If resolvers specialise, the pooled Erlang-C number understates the
        # requirement, because a plumbing request cannot be taken by the
        # electrical volunteer.
        concentrations = []
        for _, mix in category_mix.items():
            total = math.fsum(mix.values())
            if total <= 0:
                continue
            concentrations.append(math.fsum((v / total) ** 2 for v in mix.values()))
        worst = max(concentrations) if concentrations else 0.0
        checks.append(Check(
            id="servers-are-fungible",
            label="Any resolver can take any request",
            status="WARN" if worst > 0.6 else "PASS",
            statistic=worst,
            detail=(
                "resolvers specialise: the most concentrated one takes "
                + format(worst * 100.0, ".0f") + "% of their work from a single category by the "
                "Herfindahl measure. A pooled Erlang-C number understates the requirement when "
                "a plumbing request cannot be taken by the electrical volunteer; ask for the "
                "per-category breakdown instead."
            ) if worst > 0.6 else "",
        ))
    else:
        checks.append(Check(
            id="servers-are-fungible", label="Any resolver can take any request",
            status="SKIPPED",
            detail="no per-resolver category mix was supplied, so specialisation is untested",
        ))

    curve = []
    required = None
    # The sensitivity curve is the output that matters: seeing that 4 servers
    # gives 91% and 3 gives 74% is what a committee can actually act on.
    lowest = max(1, int(math.floor(offered)))
    for c in range(lowest, int(max_servers) + 1):
        attained = erlang_c_service_level(c, offered, ratio)
        curve.append({"c": c, "p_within_target": attained})
        if required is None and attained >= target_fraction:
            required = c
        if required is not None and c >= required + 2:
            break

    whole_current = int(math.floor(current_servers))
    attained_now = erlang_c_service_level(whole_current, offered, ratio) if whole_current > 0 else 0.0
    value = {
        "required_servers": required,
        "current_servers": current_servers,
        "gap": (required - current_servers) if required is not None else None,
        "attained_at_current": attained_now,
        "attained_at_required": (
            erlang_c_service_level(required, offered, ratio) if required is not None else None
        ),
        "offered_load_erlangs": offered,
        "target_fraction": target_fraction,
        "target_within_days": target_within_days,
        "curve": curve,
    }
    caveats = [c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail]
    if required is None:
        caveats.append(
            "no team size up to " + str(max_servers) + " reaches the target; either the target "
            "or the arrival rate is unrealistic"
        )
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="none",
        assumptions=(
            "Erlang-C, so M/M/c with no abandonment and infinite patience. Real people abandon, "
            "which makes this conservative in one direction and optimistic in another.",
            "The availability convention behind current_servers is declared by the capacity "
            "reducer, not guessed here.",
            "The sensitivity curve is the honest output; an integer server count with a "
            "confidence interval would be theatre.",
        ),
        checks=tuple(checks),
        caveats=tuple(caveats),
        unit="servers",
        params_hash=phash,
    )


def mg1_wait(arrival_rate, service_mean, service_var, window, *, seed=0, active_servers=1.0,
             service_samples=None) -> Evidence:
    """queueing.mg1_wait. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "queueing.mg1_wait"
    phash = params_hash(method, 1, {**_window_params(window), "arrival_rate": arrival_rate,
                                    "service_mean": service_mean, "service_var": service_var,
                                    "active_servers": active_servers, "seed": seed})
    as_of = _as_of(window)
    n = len(service_samples) if service_samples else 0
    if service_samples is not None and n < MIN_CLOSED_SPELLS:
        return insufficient(
            method, n=n, as_of=as_of, unit="days", params_hash=phash,
            caveats=("needs " + str(MIN_CLOSED_SPELLS) + " closed spells, because the variance "
                     "of the service time needs more data than the mean; has " + str(n),),
        )
    service_rate = 1.0 / service_mean if service_mean > 0 else 0.0
    checks = [
        _stability_check(arrival_rate, service_rate, 1.0),
        Check(
            id="single-server-appropriate",
            label="Exactly one person works this queue",
            status="PASS" if active_servers <= 1.0 else "FAIL",
            statistic=float(active_servers),
            blocking=active_servers > 1.0,
            detail=(
                format(active_servers, ".1f") + " servers are active, so M/G/1 is the wrong "
                "model and would overstate the wait substantially. Use queueing.mmc_metrics."
            ) if active_servers > 1.0 else "",
        ),
        _censoring_check(),
    ]
    wq = pollaczek_khinchine_wait(arrival_rate, service_mean, service_var)
    interval = None
    if service_samples and len(service_samples) >= MIN_CLOSED_SPELLS:
        def statistic(sample) -> float:
            m = mean(sample)
            v = variance(sample)
            if m <= 0.0 or arrival_rate * m >= 1.0:
                raise ValueError("unstable resample")
            return pollaczek_khinchine_wait(arrival_rate, m, v)

        interval = bootstrap_bca(list(service_samples), statistic, seed=seed, n_boot=400)
    blocked = _blocked(checks)
    return Evidence(
        value=None if blocked or not math.isfinite(wq) else wq,
        n=n,
        method=method,
        as_of=as_of,
        interval=None if blocked else interval,
        interval_kind="bootstrap-bca-95" if (interval and not blocked) else "none",
        assumptions=(
            "One server, Poisson arrivals, any service distribution with a finite variance, "
            "first-come first-served.",
            "The variance of the service time is stable, which a single two-year-old request "
            "can break.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        unit="days",
        params_hash=phash,
    )


def backlog_projection(periods, arrival_forecast, window, *, current_servers, horizon,
                       service_rate=None) -> Evidence:
    """
    queueing.backlog_projection.

    A composition, not a new estimator: it takes an arrival forecast from Pack 3
    and the current capacity and rolls the backlog forward. It inherits the
    forecast's interval and its failures, and says so rather than drawing a
    confident line over a forecast that lost to seasonal-naive.
    """
    method = "queueing.backlog_projection"
    phash = params_hash(method, 1, {**_window_params(window), "current_servers": current_servers,
                                    "horizon": horizon, "service_rate": service_rate})
    as_of = _as_of(window)
    usable = [p for p in periods if getattr(p, "complete", True)]
    n = len(usable)
    empty = {"t": [], "backlog": [], "lo": [], "hi": [], "capacity_per_period": None}
    if n < MIN_PERIODS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("needs " + str(MIN_PERIODS) + " complete periods, has " + str(n),),
        )

    point, lo_path, hi_path, forecast_checks = _read_forecast(arrival_forecast, horizon)
    if not point:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=empty, params_hash=phash,
            caveats=("the arrival forecast carried no values to project from",),
        )

    if service_rate is None:
        served = math.fsum(float(p.resolutions) for p in usable)
        server_periods = math.fsum(float(p.active_servers) for p in usable)
        service_rate = served / server_periods if server_periods > 0 else 0.0
    capacity = current_servers * service_rate

    def roll(arrivals):
        backlog = float(usable[-1].backlog_end)
        path = []
        for a in arrivals:
            backlog = max(0.0, backlog + a - capacity)
            path.append(backlog)
        return path

    projection = roll(point)
    lower = roll(lo_path) if lo_path else []
    upper = roll(hi_path) if hi_path else []

    checks = list(forecast_checks)
    checks.append(Check(
        id="capacity-declared",
        label="Capacity is held at its current level over the horizon",
        status="PASS",
        statistic=capacity,
        detail=(
            "the projection holds capacity at " + format(capacity, ".1f") + " requests per "
            "period. A planned staffing change inside the horizon has to be entered; it is not "
            "inferred."
        ),
    ))
    return Evidence(
        value={
            "t": list(range(1, len(projection) + 1)),
            "backlog": projection,
            "lo": lower,
            "hi": upper,
            "capacity_per_period": capacity,
            "starting_backlog": float(usable[-1].backlog_end),
        },
        n=n,
        method=method,
        as_of=as_of,
        interval=None,
        interval_kind="predictive-80" if lower and upper else "none",
        assumptions=(
            "The arrival forecast it is given passed its own MASE gate.",
            "Capacity stays as declared over the horizon.",
            "A backlog cannot go below zero, so the projection floors at zero rather than "
            "reporting negative work.",
        ),
        checks=tuple(checks),
        caveats=tuple(c.detail for c in checks if c.status in ("WARN", "FAIL") and c.detail),
        unit="open requests",
        params_hash=phash,
    )


def _read_forecast(forecast: Any, horizon: int):
    """
    Accepts a bare sequence of numbers, a series dict, or an Evidence envelope
    from Pack 3. An envelope brings its failing checks with it, which is the
    point: a projection built on a forecast that lost to seasonal-naive inherits
    that failure rather than hiding it.
    """
    checks: list[Check] = []
    value = forecast
    if hasattr(forecast, "value"):
        checks = [c for c in getattr(forecast, "checks", ()) if c.status in ("WARN", "FAIL")]
        value = forecast.value
    if isinstance(value, dict):
        point = [float(v) for v in (value.get("y") or value.get("forecast") or [])][:horizon]
        lo = [float(v) for v in (value.get("lo") or [])][:horizon]
        hi = [float(v) for v in (value.get("hi") or [])][:horizon]
        return point, lo, hi, checks
    if value is None:
        return [], [], [], checks
    return [float(v) for v in value][:horizon], [], [], checks


__all__ = [
    "backlog_projection",
    "erlang_b",
    "erlang_c",
    "erlang_c_service_level",
    "erlang_c_staffing",
    "little_law_wait",
    "mg1_wait",
    "mmc_metrics",
    "mmc_wait_in_queue",
    "pollaczek_khinchine_wait",
]
