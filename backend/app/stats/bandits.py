"""
Adaptive allocation over the exposure log.

A policy decision a committee cannot reproduce months later is not a policy decision,
which is why the seed is a blocking check and why freeze_and_report exists.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def thompson_sampling_policy(arm_posteriors, *, seed, n_draws=10000, floor=0.05) -> Evidence:
    """bandits.thompson_sampling_policy. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bandits.thompson_sampling_policy is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def freeze_and_report(policy_state, *, as_of) -> Evidence:
    """bandits.freeze_and_report. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bandits.freeze_and_report is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "thompson_sampling_policy",
    "freeze_and_report",
]
