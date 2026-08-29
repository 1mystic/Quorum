"""
Stream 6: `decision`. docs/DATA_SPINE.md section 6.

Polls, elections, budget allocations, referenda.

Rule D1: `declared_rule` is recorded when the decision opens, before any ballot
is cast. The platform may compute and disclose other rules' winners, and must
disclose a Condorcet cycle, but the declared rule decides. This structurally
prevents rule-shopping after the fact, which is the one governance failure a
voting module can actually cause.

Rule D2: per-stratum ballot breakdowns are subject to the vertical's
k-anonymity floor with no override. "How Block C voted", where Block C is nine
households, is a disclosure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

DecisionKind = Literal["poll", "election", "budget_allocation", "referendum"]

BallotStyle = Literal["ranked", "approval", "score", "single", "allocation"]


@dataclass(frozen=True)
class DecisionSpec:
    """
    Atom. The declaration, frozen at open time.

    `eligible_strata` is a member_lifecycle RosterSnapshot frozen at `opened_at`,
    not a decision fact. Frozen so a later move-in cannot change a past turnout
    figure.
    """

    decision_ref: str
    kind: DecisionKind
    opened_at: datetime
    closed_at: datetime | None
    declared_rule: str             # "schulze" | "stv" | "approval" | "borda" | "mes" | "greedy"
    seats: int = 1
    quorum_rule: str | None = None  # "none" | "fraction:0.25" | "count:50"
    budget_minor: int | None = None
    eligible_strata: Mapping[tuple[str, ...], int] = field(default_factory=dict)
    ballot_style: BallotStyle = "ranked"

    def __post_init__(self) -> None:
        if not self.declared_rule:
            raise ValueError(
                "decision " + self.decision_ref + " has no declared_rule; rule D1 requires it to "
                "be recorded before any ballot is cast, so that the rule cannot be chosen after "
                "the result is known"
            )
        if self.seats < 1:
            raise ValueError("decision " + self.decision_ref + " must have at least one seat")


@dataclass(frozen=True)
class DecisionOption:
    """Atom. One thing that can be voted for or funded."""

    option_ref: str
    decision_ref: str
    label: str
    cost_minor: int | None = None  # budget_allocation only
    tags: tuple[str, ...] = ()
    proposer_ref: str | None = None


@dataclass(frozen=True)
class Ballot:
    """
    Atom. One cast ballot.

    `ranking` is a tuple of TIERS, not a flat list, because real ballots have
    ties and truncation. The inner tuple holds options ranked equally. An option
    absent from every tier is unranked, which Borda, Schulze and STV each treat
    differently; the treatment is a declared parameter of each service, never an
    implicit default.

    `voter_ref` is pseudonymous and is not joinable to `member_ref` outside the
    service layer's sealed map. Secret-ballot verticals drop it entirely.
    """

    ballot_ref: str
    decision_ref: str
    voter_ref: str
    cast_at: datetime
    ranking: tuple[tuple[str, ...], ...] = ()      # tuple of tiers; inner tuple = tied options
    approvals: frozenset[str] = frozenset()
    scores: Mapping[str, int] = field(default_factory=dict)
    allocation: Mapping[str, int] = field(default_factory=dict)   # option_ref -> minor units
    strata: Mapping[str, str] = field(default_factory=dict)       # representativeness only
    channel: str | None = None

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for tier in self.ranking:
            for option_ref in tier:
                if option_ref in seen:
                    raise ValueError(
                        "ballot " + self.ballot_ref + " ranks " + option_ref + " more than once; "
                        "an invalid ballot is excluded and counted, never silently repaired"
                    )
                seen.add(option_ref)


__all__ = ["Ballot", "BallotStyle", "DecisionKind", "DecisionOption", "DecisionSpec"]
