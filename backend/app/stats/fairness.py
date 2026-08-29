"""
Workload distribution and assignment over request_flow.

Per-person rows pass the tenant k-anonymity floor before they can leave.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def workload_gini(spells, window, *, by="assignee_ref", weight="count", include_zero_workers=False, k_anonymity=5, seed=0) -> Evidence:
    """fairness.workload_gini. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "fairness.workload_gini is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def balanced_assignment(open_requests, resolvers, *, capacity, cost="load_and_skill", seed=0) -> Evidence:
    """fairness.balanced_assignment. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "fairness.balanced_assignment is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "workload_gini",
    "balanced_assignment",
]
