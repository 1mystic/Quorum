"""
Participatory budgeting over the decision stream.

The Method of Equal Shares ships with the utilitarian greedy baseline alongside it,
never instead of it, so a committee sees the trade-off between total satisfaction and
proportional fairness explicitly.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def method_of_equal_shares(ballots, options, spec, *, completion="add1") -> Evidence:
    """budgeting.method_of_equal_shares. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "budgeting.method_of_equal_shares is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def greedy_knapsack(ballots, options, spec) -> Evidence:
    """budgeting.greedy_knapsack. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "budgeting.greedy_knapsack is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def fairness_report(ballots, options, funded, roster, *, k_anonymity=5, seed=0) -> Evidence:
    """budgeting.fairness_report. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "budgeting.fairness_report is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "method_of_equal_shares",
    "greedy_knapsack",
    "fairness_report",
]
