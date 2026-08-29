"""
Stream 1: `member_lifecycle`. docs/DATA_SPINE.md section 1.

Who is in the community, since when, in what stratum, and how they left.

No dataclass here carries a tenant id (spine rule S2) and every person is an
opaque `member_ref` pseudonym, never an email, phone or name (rule S3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

MemberEventKind = Literal[
    "join",            # record created
    "activate",        # first meaningful action; separates registered from actually present
    "lapse",           # became inactive by the vertical's rule
    "reinstate",       # returned from lapse
    "exit",            # left for good: moved out, graduated, resigned, deceased, removed
    "role_change",
    "stratum_change",  # moved block, changed cohort, changed membership tier
]


@dataclass(frozen=True)
class MemberEvent:
    """Atom. Append-only."""

    member_ref: str
    at: datetime
    kind: MemberEventKind
    reason: str | None = None          # controlled vocabulary per vertical
    role: str | None = None            # for role_change: the role AFTER the change
    group_ref: str | None = None
    strata: Mapping[str, str] = field(default_factory=dict)
    source: str = "app"                # "app" | "import" | "admin" | "adapter_backfill"


@dataclass(frozen=True)
class MemberSpell:
    """
    Unit. The survival record for churn and retention.

    `at_risk_from` and `left_truncated` carry delayed entry: a member who joined
    before the window enters the risk set at `window.start`, and the estimator
    must use the (entry, exit] form. Spine rule C3, which applies here as it
    does to requests.
    """

    member_ref: str
    entered_at: datetime               # join or reinstate
    at_risk_from: datetime             # max(entered_at, window.start)
    left_truncated: bool
    exited_at: datetime | None
    exit_kind: str | None              # "lapse" | "exit" | None
    event_observed: bool               # a terminal exit fell inside the window
    duration_days: float               # (min(exited_at, window.end) - at_risk_from) in days
    strata_at_entry: Mapping[str, str] = field(default_factory=dict)
    covariates: Mapping[str, float | str] = field(default_factory=dict)


@dataclass(frozen=True)
class RosterSnapshot:
    """
    Unit. A population frame, not a sample.

    This is what turns "62 people voted" into "62 of 340 eligible, and Block C
    is under-represented by 11 points". It is also the denominator for every
    k-anonymity cell and the source of `roles` for the queueing server count.
    """

    as_of: datetime
    counts_by_stratum: Mapping[tuple[str, ...], int]   # stratum key tuple -> headcount
    total: int
    roles: Mapping[str, int] = field(default_factory=dict)   # role -> headcount


__all__ = ["MemberEvent", "MemberEventKind", "MemberSpell", "RosterSnapshot"]
