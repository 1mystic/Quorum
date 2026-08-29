"""
Atoms to units. The pure half of the spine, and where the correctness lives.

Censoring is decided here, in a reducer, and nowhere else. A
`WHERE resolved_at IS NOT NULL` in a repository is invisible to the test suite,
whereas a reducer that mis-censors fails a known-answer test. That is the whole
reason this boundary exists.

Every function here takes atoms plus a `StreamWindow` and returns units. None of
them reads a clock: "now" is `window.end` (spine rule S6).

Status: signatures declared, implementations land with card C.8.
"""
from __future__ import annotations

from app.stats.streams.decision import Ballot, DecisionSpec
from app.stats.streams.derived import CountObservation, PairwiseResult, RateObservation
from app.stats.streams.ledger import DueSpell, LedgerEntry, LedgerPeriod
from app.stats.streams.member import MemberEvent, MemberSpell, RosterSnapshot
from app.stats.streams.participation import (
    EngagementFeatures,
    InteractionEdge,
    ParticipationEvent,
    ParticipationPeriod,
)
from app.stats.streams.request import FlowPeriod, RequestEvent, RequestSpell
from app.stats.streams.window import StreamWindow


def request_spells(
    events: tuple[RequestEvent, ...],
    window: StreamWindow,
    *,
    reopen_policy: str = "new_spell",
) -> tuple[RequestSpell, ...]:
    """
    The most important function in this package.

    Every request opened before `window.end` comes out of here, censored if it
    has no terminal event (rule C1). There is no argument that filters by
    outcome and there will not be one: the honest signature is the enforcement.
    """
    raise NotImplementedError("streams.reduce.request_spells lands with card C.8")


def flow_periods(
    events: tuple[RequestEvent, ...],
    window: StreamWindow,
    *,
    period: str = "week",
    active_servers_by_period=None,
) -> tuple[FlowPeriod, ...]:
    """
    Periodised counts. Periods after `window.complete_through` are emitted with
    `complete=False` rather than dropped, so a forecaster can exclude them and
    say it did rather than reading a partial bucket as a collapse.
    """
    raise NotImplementedError("streams.reduce.flow_periods lands with card C.8")


def member_spells(
    events: tuple[MemberEvent, ...], window: StreamWindow
) -> tuple[MemberSpell, ...]:
    raise NotImplementedError("streams.reduce.member_spells lands with card C.8")


def roster_snapshot(
    events: tuple[MemberEvent, ...], window: StreamWindow, *, strata_keys: tuple[str, ...] = ()
) -> RosterSnapshot:
    """The population frame, at `window.end`, which is every denominator in Pack 4."""
    raise NotImplementedError("streams.reduce.roster_snapshot lands with card C.8")


def due_spells(entries: tuple[LedgerEntry, ...], window: StreamWindow) -> tuple[DueSpell, ...]:
    """An unpaid due is right-censored, exactly like an open request (rule L1)."""
    raise NotImplementedError("streams.reduce.due_spells lands with card C.8")


def ledger_periods(
    entries: tuple[LedgerEntry, ...], window: StreamWindow, *, period: str = "month"
) -> tuple[LedgerPeriod, ...]:
    raise NotImplementedError("streams.reduce.ledger_periods lands with card C.8")


def participation_periods(
    events: tuple[ParticipationEvent, ...], window: StreamWindow, *, period: str = "week"
) -> tuple[ParticipationPeriod, ...]:
    raise NotImplementedError("streams.reduce.participation_periods lands with card C.8")


def engagement_features(
    events: tuple[ParticipationEvent, ...],
    entries: tuple[LedgerEntry, ...],
    spells: tuple[MemberSpell, ...],
    window: StreamWindow,
) -> tuple[EngagementFeatures, ...]:
    raise NotImplementedError("streams.reduce.engagement_features lands with card C.8")


def interaction_edges(
    events: tuple[ParticipationEvent, ...],
    window: StreamWindow,
    *,
    basis: str = "co_attendance",
    normalisation: str = "one_over_m_minus_one",
) -> tuple[InteractionEdge, ...]:
    """
    Bipartite projection with the declared normalisation. An event with m
    attendees contributes 1/(m-1) to each pair, not 1: without it a 200-person
    annual general meeting makes every member a connector. The normalisation
    constant enters `params_hash`.
    """
    raise NotImplementedError("streams.reduce.interaction_edges lands with card C.8")


def rate_observations(
    spells: tuple[RequestSpell, ...],
    window: StreamWindow,
    *,
    by: str = "assignee_ref",
    success,
) -> tuple[RateObservation, ...]:
    """(group, successes, trials), so one shrinkage implementation serves every source."""
    raise NotImplementedError("streams.reduce.rate_observations lands with card C.8")


def count_observations(
    spells: tuple[RequestSpell, ...], window: StreamWindow, *, by: str = "category"
) -> tuple[CountObservation, ...]:
    raise NotImplementedError("streams.reduce.count_observations lands with card C.8")


def pairwise_results(
    ballots: tuple[Ballot, ...], spec: DecisionSpec
) -> tuple[PairwiseResult, ...]:
    raise NotImplementedError("streams.reduce.pairwise_results lands with card C.8")


__all__ = [
    "count_observations",
    "due_spells",
    "engagement_features",
    "flow_periods",
    "interaction_edges",
    "ledger_periods",
    "member_spells",
    "pairwise_results",
    "participation_periods",
    "rate_observations",
    "request_spells",
    "roster_snapshot",
]
