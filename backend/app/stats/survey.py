"""
Survey analysis over ordinal responses.

There is nowhere in this module to put the mean of a 1 to 5 Likert item, and that is
deliberate: survey.likert_distribution returns a structure with no mean key.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def likert_distribution(responses, as_of, *, item_id, group_by=None, k_anonymity=5, seed=0) -> Evidence:
    """survey.likert_distribution. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survey.likert_distribution is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def ordinal_logistic(responses, as_of, *, item_id, covariates, link="logit", alpha=0.05, k_anonymity=5) -> Evidence:
    """survey.ordinal_logistic. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survey.ordinal_logistic is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def raking_weights(respondent_strata, population_margins, as_of, *, max_iter=100, tol=1e-6, trim=(0.2, 5.0)) -> Evidence:
    """survey.raking_weights. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survey.raking_weights is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def design_effect(weights, as_of) -> Evidence:
    """survey.design_effect. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survey.design_effect is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "likert_distribution",
    "ordinal_logistic",
    "raking_weights",
    "design_effect",
]
