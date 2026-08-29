"""
A/B tests over the exposure log.

Every service here consumes ParticipationEvent rows with arm_ref and the nudge_*
kinds. Without the exposure log they would measure self-selection.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def beta_ab_test(arm_a, arm_b, *, prior=(1.0, 1.0), credible=0.95) -> Evidence:
    """experiments.beta_ab_test. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "experiments.beta_ab_test is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def expected_loss(arm_a, arm_b, *, prior=(1.0, 1.0)) -> Evidence:
    """experiments.expected_loss. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "experiments.expected_loss is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def sequential_stopping_rule(event_stream_ordered, *, alpha=0.05, method="evalue") -> Evidence:
    """experiments.sequential_stopping_rule. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "experiments.sequential_stopping_rule is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "beta_ab_test",
    "expected_loss",
    "sequential_stopping_rule",
]
