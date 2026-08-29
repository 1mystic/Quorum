"""
The statistical engine.

Everything under this package is pure: no database, no network, no clock, no
module-level mutable state, and randomness only through an explicit seed
argument. Services fetch rows and hand them in; this package does mathematics
and hands back an `Evidence` envelope.

The purity rule is mechanical, not a convention. `tests/unit/stats/test_purity.py`
walks every module here and fails the build if one imports `app.repository`,
`app.services`, `sqlalchemy`, `httpx` or `requests`, or reads a clock.

Read `docs/EVIDENCE_CONTRACT.md` before adding anything.
"""
from app.stats.contracts import (
    Check,
    CheckStatus,
    Evidence,
    InsufficientData,
    IntervalKind,
    MethodCard,
    ValueShape,
    params_hash,
)

__all__ = [
    "Check",
    "CheckStatus",
    "Evidence",
    "InsufficientData",
    "IntervalKind",
    "MethodCard",
    "ValueShape",
    "params_hash",
]
