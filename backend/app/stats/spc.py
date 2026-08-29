"""
Statistical process control over periodised counts.

Control limits are a decision boundary, not an estimate: interval_kind is
"control-limits" and the Method Cards say what that means. The limit constant is
solved for a stated in-control average run length rather than defaulted to 3 sigma.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def ewma_chart(series, window, *, lam=0.2, target_arl0=500, baseline_periods=None) -> Evidence:
    """spc.ewma_chart. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "spc.ewma_chart is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def cusum_chart(series, window, *, k=0.5, h=5.0, baseline_periods=None) -> Evidence:
    """spc.cusum_chart. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "spc.cusum_chart is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def poisson_rate_chart(series, window, *, exposure_field="exposure_days", dispersion="auto") -> Evidence:
    """spc.poisson_rate_chart. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "spc.poisson_rate_chart is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "ewma_chart",
    "cusum_chart",
    "poisson_rate_chart",
]
