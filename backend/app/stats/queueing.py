"""
Queueing models over request_flow.

Every service here needs active_servers, which comes from the declared cross-stream
reducer app/stats/streams/capacity.py rather than being inferred inside this module.
"How many resolvers do you actually have" is the least well-defined input in Pack 1,
so its definition is part of each Method Card.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def little_law_wait(periods, window, *, seed=0) -> Evidence:
    """queueing.little_law_wait. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "queueing.little_law_wait is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def mmc_metrics(arrival_rate, service_rate, servers, window, *, service_cv=None, seed=0) -> Evidence:
    """queueing.mmc_metrics. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "queueing.mmc_metrics is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def erlang_c_staffing(arrival_rate, mean_service_time, window, *, current_servers, target_fraction=0.9, target_within_days=5.0, max_servers=200, seed=0) -> Evidence:
    """queueing.erlang_c_staffing. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "queueing.erlang_c_staffing is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def mg1_wait(arrival_rate, service_mean, service_var, window, *, seed=0) -> Evidence:
    """queueing.mg1_wait. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "queueing.mg1_wait is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def backlog_projection(periods, arrival_forecast, window, *, current_servers, horizon) -> Evidence:
    """queueing.backlog_projection. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "queueing.backlog_projection is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "little_law_wait",
    "mmc_metrics",
    "erlang_c_staffing",
    "mg1_wait",
    "backlog_projection",
]
