"""
Calibrated per-member risk.

The calibration gate governs this module: no risk score is served unless, after
calibration on a held-out split, its Brier skill score against climatology is positive
and its expected calibration error is under the pack threshold. AUC is reported but
gates nothing: it measures ranking, and a model that ranks perfectly while claiming
90% for events that happen 40% of the time will get a committee to act on a number
that is not true.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

Status: specified and registered, not yet implemented.
"""
from app.stats.contracts import Evidence


def late_payment_risk(dues, features, window, *, seed, horizon_days=30, model="logistic_l2", calibrator="auto", folds=5) -> Evidence:
    """risk.late_payment_risk. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "risk.late_payment_risk is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


def member_disengagement_risk(spells, features, window, *, seed, horizon_days=90, model="logistic_l2", calibrator="auto", folds=5) -> Evidence:
    """risk.member_disengagement_risk. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    raise NotImplementedError(
        "risk.member_disengagement_risk is specified in docs/STATS_CATALOG.md and registered in "
        "app/stats/registry.py, but its mathematics is not implemented yet"
    )


__all__ = [
    "late_payment_risk",
    "member_disengagement_risk",
]
