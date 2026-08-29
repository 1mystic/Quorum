"""
Text statistics over TextDoc.

TextDoc has no identity field, so nothing here can leak an author: it was never handed
one. Embeddings arrive precomputed; this module never calls a model.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def tfidf_similarity(docs, as_of, *, top_k=10, sublinear=True, smooth_idf=True) -> Evidence:
    """text.tfidf_similarity. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "text.tfidf_similarity is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def near_duplicate_candidates(docs, query_doc, as_of, *, seed, threshold=0.7, method="both", n_permutations=128, window_days=30) -> Evidence:
    """text.near_duplicate_candidates. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "text.near_duplicate_candidates is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def nmf_topics(docs, as_of, *, seed, n_topics="auto", max_features=5000, init="nndsvd", k_anonymity=5) -> Evidence:
    """text.nmf_topics. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "text.nmf_topics is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "tfidf_similarity",
    "near_duplicate_candidates",
    "nmf_topics",
]
