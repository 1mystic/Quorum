"""
Distribution-free predictive intervals.

conformal.survival_eta_bound is the resident-facing ETA and is the hardest thing in
Pack 3 to get right: split conformal calibrated on resolved requests is calibrated on
the fast ones, so exchangeability fails in the direction that makes the ETA look good,
which is the worst possible direction for the one number a resident will trust and quote.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def split_conformal_interval(calibration_residuals, point_prediction, as_of, *, alpha=0.1) -> Evidence:
    """conformal.split_conformal_interval. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "conformal.split_conformal_interval is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def survival_eta_bound(spells, window, *, covariates, seed, alpha=0.1) -> Evidence:
    """conformal.survival_eta_bound. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "conformal.survival_eta_bound is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def mondrian_eta(spells, window, *, seed, taxonomy="category", alpha=0.1) -> Evidence:
    """conformal.mondrian_eta. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "conformal.mondrian_eta is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "split_conformal_interval",
    "survival_eta_bound",
    "mondrian_eta",
]
