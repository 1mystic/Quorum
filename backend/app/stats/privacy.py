"""
Disclosure control. The last thing every Pack 4 service calls.

Small communities are small. A per-block statistic over three households is a
disclosure, and there is no admin override, because the admin asking for it is
precisely the risk.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def k_anonymity_suppress(table_evidence, *, k, cell_counts, secondary=True) -> Evidence:
    """privacy.k_anonymity_suppress. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "privacy.k_anonymity_suppress is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def laplace_noise(value, as_of, *, sensitivity, epsilon, seed, clamp=None) -> Evidence:
    """privacy.laplace_noise. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "privacy.laplace_noise is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "k_anonymity_suppress",
    "laplace_noise",
]
