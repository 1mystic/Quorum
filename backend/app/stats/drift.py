"""
Distribution drift against a stored reference.

The reference distribution is not stream data. It is an artifact of a previous fit,
supplied by the caller. app/stats/ does not fetch it.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def psi(reference, current, as_of, *, bins=10, binning="quantile") -> Evidence:
    """drift.psi. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "drift.psi is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def ks_test(reference, current, as_of, *, alpha=0.05) -> Evidence:
    """drift.ks_test. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "drift.ks_test is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def label_shift(reference_labels, current_labels, as_of, *, alpha=0.05) -> Evidence:
    """drift.label_shift. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "drift.label_shift is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "psi",
    "ks_test",
    "label_shift",
]
