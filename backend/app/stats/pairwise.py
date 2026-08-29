"""
Paired-comparison models over head-to-heads, matches and ballots.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def bradley_terry(results, *, penalizer=0.0, reference=None, alpha=0.05) -> Evidence:
    """pairwise.bradley_terry. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "pairwise.bradley_terry is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def elo_update(results, *, k_factor=32.0, initial=1500.0) -> Evidence:
    """pairwise.elo_update. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "pairwise.elo_update is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "bradley_terry",
    "elo_update",
]
