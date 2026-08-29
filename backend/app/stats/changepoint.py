"""
Level-shift detection over any periodised series.

The interval is on the DATE of the shift, not on its size. A changepoint two periods
from the end of a series is unidentifiable from noise and is not reported.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def detect_level_shifts(series, window, *, penalty="mbic", min_segment=4, model="normal_mean", seed=0) -> Evidence:
    """changepoint.detect_level_shifts. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "changepoint.detect_level_shifts is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "detect_level_shifts",
]
