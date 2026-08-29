"""
Social choice over the decision stream.

Disclosure over tidiness. A Condorcet cycle is the finding, not an inconvenience.
Hiding one behind whichever tie-break happens to fire is the governance equivalent of
dropping open tickets.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def pairwise_matrix(ballots, options, spec, *, unranked="last") -> Evidence:
    """voting.pairwise_matrix. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.pairwise_matrix is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def condorcet_winner(ballots, options, spec, *, unranked="last") -> Evidence:
    """voting.condorcet_winner. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.condorcet_winner is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def schulze(ballots, options, spec, *, unranked="last", tie_break_seed=0) -> Evidence:
    """voting.schulze. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.schulze is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def borda(ballots, options, spec, *, unranked="last") -> Evidence:
    """voting.borda. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.borda is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def approval(ballots, options, spec) -> Evidence:
    """voting.approval. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.approval is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def score(ballots, options, spec) -> Evidence:
    """voting.score. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.score is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def stv(ballots, options, spec, *, seats, tie_break_seed, quota="droop", transfer="gregory") -> Evidence:
    """voting.stv. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.stv is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def turnout_representativeness(ballots, spec, roster, *, k_anonymity=5) -> Evidence:
    """voting.turnout_representativeness. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "voting.turnout_representativeness is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "pairwise_matrix",
    "condorcet_winner",
    "schulze",
    "borda",
    "approval",
    "score",
    "stv",
    "turnout_representativeness",
]
