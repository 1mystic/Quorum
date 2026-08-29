"""
Stream 4: `participation`. docs/DATA_SPINE.md section 4.

Anything a member does that is not a request and not money, plus the exposure
log.

The `nudge_sent` / `nudge_delivered` / `nudge_opened` / `nudge_acted` kinds with
`arm_ref` are the **exposure log**, and they are the addition the six-stream
sketch did not have (spine section 8). Pack 2's A/B tests and bandits need to
know who was OFFERED a nudge, not only who acted. Without it every nudge
experiment measures self-selection, confidently and wrongly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

ParticipationKind = Literal[
    "rsvp", "rsvp_cancel", "attend", "no_show",
    "login", "post", "comment", "upvote", "read_receipt",
    "volunteer_hours", "training_complete", "in_kind_contribution",
    "nudge_sent", "nudge_delivered", "nudge_opened", "nudge_acted",   # the exposure log
]

EXPOSURE_KINDS: frozenset[str] = frozenset(
    {"nudge_sent", "nudge_delivered", "nudge_opened", "nudge_acted"}
)


@dataclass(frozen=True)
class ParticipationEvent:
    """
    Atom. Append-only.

    A `nudge_*` row is a system action against a member, not a member action,
    which is why `arm_ref` exists and is required for those kinds: an experiment
    with an unlabelled exposure is not an experiment.
    """

    member_ref: str
    at: datetime
    kind: ParticipationKind
    object_ref: str | None = None      # event, announcement, request, poll, campaign
    object_kind: str | None = None
    group_ref: str | None = None
    weight: float = 1.0                # hours for volunteer_hours, 1.0 otherwise
    channel: str | None = None         # "app" | "whatsapp" | "email" | "sms" | "notice_board"
    arm_ref: str | None = None         # experiment / bandit arm, for nudge_* kinds only
    strata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind in EXPOSURE_KINDS and not self.arm_ref:
            raise ValueError(
                "exposure-log event " + self.kind + " for " + self.member_ref + " has no arm_ref; "
                "without it experiments.* would measure self-selection rather than the nudge"
            )
        if self.arm_ref and self.kind not in EXPOSURE_KINDS:
            raise ValueError(
                "arm_ref is only meaningful on exposure-log kinds, not on " + self.kind
            )


@dataclass(frozen=True)
class EngagementFeatures:
    """
    Unit. RFM, generalised.

    `contribution_minor` is the one deliberate cross-stream feature, pulled from
    `ledger`. It is named here rather than smuggled into a risk model so that a
    reader of the spine can see the join.
    """

    member_ref: str
    recency_days: float                # since last participation of any kind
    frequency_90d: int
    breadth: int                       # distinct participation kinds used
    volunteer_hours_365d: float
    tenure_days: float
    contribution_minor: int
    channels: frozenset[str] = frozenset()
    strata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InteractionEdge:
    """
    Unit. One undirected edge of the derived interaction graph.

    Edge construction rule: co-attendance is a bipartite projection and must be
    normalised. An event with `m` attendees contributes 1/(m-1) to each pair, not
    1. Without it a 200-person annual general meeting makes every member a
    connector and betweenness centrality becomes noise. The normalisation
    constant is a declared parameter and enters params_hash.
    """

    a_ref: str
    b_ref: str                         # canonically ordered a_ref < b_ref
    weight: float
    basis: Literal["co_attendance", "co_request", "reply", "co_vote", "co_group"]

    def __post_init__(self) -> None:
        if self.a_ref >= self.b_ref:
            raise ValueError(
                "InteractionEdge is undirected and canonically ordered a_ref < b_ref; got "
                + self.a_ref + " and " + self.b_ref
            )


@dataclass(frozen=True)
class ParticipationPeriod:
    """Unit. Periodised participation, for forecasting attendance and SPC."""

    period_start: datetime
    period_end: datetime
    active_members: int
    events_by_kind: Mapping[str, int] = field(default_factory=dict)
    total_weight: float = 0.0
    complete: bool = True


__all__ = [
    "EXPOSURE_KINDS",
    "EngagementFeatures",
    "InteractionEdge",
    "ParticipationEvent",
    "ParticipationKind",
    "ParticipationPeriod",
]
