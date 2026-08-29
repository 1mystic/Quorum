"""
Feature building and clustering over engagement.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def rfm_features(participation, ledger_entries, window) -> Evidence:
    """segmentation.rfm_features. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "segmentation.rfm_features is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def gmm_select_k(features, window, *, seed, k_range=(2, 9), covariance="diag", n_init=10, scale="robust", k_anonymity=5) -> Evidence:
    """segmentation.gmm_select_k. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "segmentation.gmm_select_k is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def stable_labels(current_labels, current_centroids, reference_labels, reference_centroids, as_of, *, drift_threshold=0.5) -> Evidence:
    """segmentation.stable_labels. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "segmentation.stable_labels is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "rfm_features",
    "gmm_select_k",
    "stable_labels",
]
