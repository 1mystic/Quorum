"""
Simulation over ledger periods and forecast envelopes. Seeded, always.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def runway_shortfall(opening_balance_minor, inflow_forecast, outflow_forecast, ledger_periods, *, horizon, seed, floor_minor=0, draws=20000) -> Evidence:
    """montecarlo.runway_shortfall. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "montecarlo.runway_shortfall is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "runway_shortfall",
]
