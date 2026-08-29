"""
Calibration mappings and proper scoring rules.

These take score and label arrays produced by a risk service, not stream units.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def isotonic_calibrate(scores, labels, as_of, *, out_of_fold=True) -> Evidence:
    """calibration.isotonic_calibrate. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "calibration.isotonic_calibrate is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def platt_calibrate(scores, labels, as_of, *, out_of_fold=True) -> Evidence:
    """calibration.platt_calibrate. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "calibration.platt_calibrate is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def brier_decomposition(probabilities, labels, as_of, *, bins=10, binning="equal_count", seed=0) -> Evidence:
    """calibration.brier_decomposition. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "calibration.brier_decomposition is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def reliability_diagram(probabilities, labels, as_of, *, bins=10, binning="equal_count", k_anonymity=5) -> Evidence:
    """calibration.reliability_diagram. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "calibration.reliability_diagram is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "isotonic_calibrate",
    "platt_calibrate",
    "brier_decomposition",
    "reliability_diagram",
]
