"""
Empirical Bayes shrinkage and ranking.

3 out of 3 is not better than 47 out of 52. Every community leaderboard ranks by raw
rate and so puts the vendor with three lucky jobs above the vendor with a year of
evidence. Shrink toward a prior estimated from the data, and rank by the posterior
lower bound, not the posterior mean: ranking by the mean still favours small samples
whenever the prior is weak.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def fit_beta_prior(observations, *, method="mle", min_groups=5) -> Evidence:
    """bayes.fit_beta_prior. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bayes.fit_beta_prior is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def beta_binomial_shrink(observations, prior, *, credible=0.95, k_anonymity=5) -> Evidence:
    """bayes.beta_binomial_shrink. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bayes.beta_binomial_shrink is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def gamma_poisson_shrink(observations, prior, *, credible=0.95, k_anonymity=5) -> Evidence:
    """bayes.gamma_poisson_shrink. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bayes.gamma_poisson_shrink is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def rank_by_posterior_lower_bound(posteriors, *, quantile=0.05, tie_break="posterior_mean", seed=0) -> Evidence:
    """bayes.rank_by_posterior_lower_bound. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bayes.rank_by_posterior_lower_bound is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def hierarchical_pool(observations, *, levels, seed, draws=4000, min_units_per_level=5, epsilon=1.0, refresh_cadence="weekly") -> Evidence:
    """bayes.hierarchical_pool. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "bayes.hierarchical_pool is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "fit_beta_prior",
    "beta_binomial_shrink",
    "gamma_poisson_shrink",
    "rank_by_posterior_lower_bound",
    "hierarchical_pool",
]
