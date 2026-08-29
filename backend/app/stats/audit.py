"""
Ledger audit statistics.

A Benford deviation is a prompt to look, not evidence of anything, and the caveat
saying so is not removable.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def benford_digits(entries, window, *, digit=1, category=None) -> Evidence:
    """audit.benford_digits. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "audit.benford_digits is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "benford_digits",
]
