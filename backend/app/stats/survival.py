"""
Time-to-event over request_flow and member_lifecycle.

Every competing community dashboard computes average resolution time over closed
tickets only. That number is not slightly wrong, it is biased in a known direction,
and the size of the bias grows with the backlog. This module reports the correct
figure and shows the naive one next to it (survival.naive_vs_km_gap).

Spine rules C1 to C10 in app/stats/streams/request.py are normative here.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def km_resolution_curve(spells, window, *, stratify_by=None, clock="wall", alpha=0.05) -> Evidence:
    """survival.km_resolution_curve. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.km_resolution_curve is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def median_resolution_days(spells, window, *, quantile=0.5, clock="wall", alpha=0.05) -> Evidence:
    """survival.median_resolution_days. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.median_resolution_days is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def sla_attainment(spells, window, *, horizon_days, clock="wall", alpha=0.05) -> Evidence:
    """survival.sla_attainment. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.sla_attainment is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def first_response_curve(spells, window, *, stratify_by=None, alpha=0.05) -> Evidence:
    """survival.first_response_curve. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.first_response_curve is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def churn_curve(spells, window, *, stratify_by=None, alpha=0.05) -> Evidence:
    """survival.churn_curve. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.churn_curve is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def logrank_compare(spells, window, *, group_by, weights="logrank") -> Evidence:
    """survival.logrank_compare. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.logrank_compare is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def cox_hazard_ratios(spells, window, *, covariates, time_varying=(), penalizer=0.0, alpha=0.05, ties="efron") -> Evidence:
    """survival.cox_hazard_ratios. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.cox_hazard_ratios is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def competing_risks_cif(spells, window, *, causes=("resolved", "escalated", "withdrawn"), alpha=0.05) -> Evidence:
    """survival.competing_risks_cif. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.competing_risks_cif is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def naive_vs_km_gap(spells, window, *, clock="wall", alpha=0.05) -> Evidence:
    """survival.naive_vs_km_gap. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "survival.naive_vs_km_gap is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "km_resolution_curve",
    "median_resolution_days",
    "sla_attainment",
    "first_response_curve",
    "churn_curve",
    "logrank_compare",
    "cox_hazard_ratios",
    "competing_risks_cif",
    "naive_vs_km_gap",
]
