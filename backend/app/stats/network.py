"""
Community structure over the derived interaction graph.

network.isolation_report returns shares by stratum and can never return individuals.
A list of socially isolated neighbours is the most sensitive output this platform
could produce, so the service is shaped so the list cannot be constructed.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def louvain_communities(edges, window, *, seed, resolution=1.0, min_component_size=3, k_anonymity=5) -> Evidence:
    """network.louvain_communities. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "network.louvain_communities is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def betweenness_centrality(edges, window, *, top_m=10, k_anonymity=5) -> Evidence:
    """network.betweenness_centrality. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "network.betweenness_centrality is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def isolation_report(edges, roster, window, *, k_anonymity=5) -> Evidence:
    """network.isolation_report. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "network.isolation_report is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "louvain_communities",
    "betweenness_centrality",
    "isolation_report",
]
