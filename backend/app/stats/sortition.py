"""
Stratified lotteries for panel and sub-committee selection.

Sortition makes the panel representative of the POOL, not of the community. If the
pool is skewed the panel inherits the skew, and that is what pool-representativeness
discloses.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def stratified_panel(pool, quotas, panel_size, as_of, *, seed, objective="maximin") -> Evidence:
    """sortition.stratified_panel. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "sortition.stratified_panel is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "stratified_panel",
]
