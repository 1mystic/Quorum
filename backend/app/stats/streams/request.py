"""
Stream 2: `request_flow`. docs/DATA_SPINE.md section 2.

The stream the product's correctness claim rests on. Everything with an
open -> assign -> progress -> resolve/close lifecycle: a housing society's
plumbing complaint, a campus club's issue ticket, an NGO's case file. All the
same object to app/stats/survival.py.

The ten censoring rules C1 to C10 are normative and are reproduced in
CENSORING_RULES below so a service can cite the one it depends on in a caveat
rather than paraphrasing it. Each rule names the field that carries it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Literal, Mapping

RequestEventKind = Literal[
    "opened", "acknowledged", "assigned", "reassigned", "status_change",
    "comment", "paused", "resumed",
    "resolved", "escalated", "withdrawn", "merged",   # terminal
    "reopened", "closed",
]

TERMINAL_KINDS: frozenset[str] = frozenset({"resolved", "escalated", "withdrawn", "merged"})

CensoringKind = Literal[
    "none",            # a terminal event was observed inside the window
    "administrative",  # still open at window.end
    "interval",        # terminal known only to fall in [interval_lo, interval_hi]
    "competing",       # exited by a cause other than the one under analysis
    "lost",            # request abandoned by the system, last seen at last_seen_at
]

RequestOutcome = Literal["resolved", "escalated", "withdrawn", "merged"]

ReopenPolicy = Literal["new_spell", "extend"]

SlaClock = Literal["wall", "active"]

# The normative censoring rules, keyed by id, each naming the RequestSpell field
# that carries it. A service quoting one of these in a caveat quotes it verbatim.
CENSORING_RULES: Mapping[str, str] = MappingProxyType({
    "C1": (
        "Every request opened before window.end enters the risk set. No reducer, repository "
        "or query may filter on terminal_at IS NOT NULL. Open requests are censored, never "
        "absent. Carried by: event_observed."
    ),
    "C2": (
        "A request with no terminal event by window.end gets event_observed=False, "
        "censoring='administrative', duration_hours = window.end - at_risk_from. It counts in "
        "Evidence.n and in Evidence.n_censored. Carried by: censoring, duration_hours."
    ),
    "C3": (
        "A request opened before window.start is left-truncated, not shifted. at_risk_from = "
        "window.start, left_truncated=True, and the estimator must use the delayed-entry "
        "(entry, exit] risk set. Carried by: at_risk_from, left_truncated."
    ),
    "C4": (
        "A bracketed terminal timestamp is interval-censored: censoring='interval' with "
        "interval_lo_hours and interval_hi_hours set. Never impute a midpoint. Carried by: "
        "interval_lo_hours, interval_hi_hours."
    ),
    "C5": (
        "Competing risks. escalated and withdrawn are not neutral censoring; a withdrawn "
        "request will never resolve. Above 5% of terminals the competing-risks-material check "
        "is WARN and the Aalen-Johansen CIF is reported alongside; above 15% it is a blocking "
        "FAIL for any 'percent resolved by day t' claim. Carried by: outcome."
    ),
    "C6": (
        "Reopen policy is a declared parameter, not a convention. 'new_spell' closes the first "
        "spell and starts a child; 'extend' keeps the spell open and increments the counter. "
        "The choice enters params_hash. Carried by: reopened_count, parent_ref."
    ),
    "C7": (
        "A request merged into another is excluded, n_excluded incremented and "
        "exclusion_reason='merged_duplicate'. The survivor's counter increments. Carried by: "
        "duplicate_count."
    ),
    "C8": (
        "duration_hours is wall clock and is the default for every survival statistic, because "
        "the resident experiences wall clock. duration_active_hours exists only where the "
        "vertical declares that on-hold time stops the clock. Which one was used is in "
        "params_hash and in the Method Card. Carried by: duration_hours, duration_active_hours, "
        "paused_hours."
    ),
    "C9": (
        "Censoring must be independent of the outcome for Kaplan-Meier to be unbiased, and it "
        "is not automatically true: an admin bulk-closing stale tickets is informative "
        "censoring. Every survival service runs the censoring-informative check comparing the "
        "covariate distribution of censored against observed spells. Carried by: covariates."
    ),
    "C10": (
        "Never impute, never interpolate, never carry forward a terminal timestamp. If it is "
        "unknown it is censored. Carried by: terminal_at being None."
    ),
})


@dataclass(frozen=True)
class RequestEvent:
    """Atom. Append-only. A category change is an event, not an edit."""

    request_ref: str
    at: datetime
    kind: RequestEventKind
    actor_ref: str | None = None        # who did it
    assignee_ref: str | None = None     # who it is on, after this event
    category: str | None = None         # set at opened, may change; changes are events
    subcategory: str | None = None
    priority: str | None = None         # controlled per vertical
    channel: str | None = None          # "app" | "whatsapp" | "walk_in" | "phone" | "email"
    group_ref: str | None = None        # committee, sub-team
    location_ref: str | None = None     # block / tower / floor / site. A stratum, and a small cell.
    parent_ref: str | None = None       # for merged: the surviving request
    at_precision: Literal["exact", "day", "bracketed"] = "exact"
    at_upper: datetime | None = None    # when at_precision == "bracketed"
    attributes: Mapping[str, float | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.at_precision == "bracketed" and self.at_upper is None:
            raise ValueError(
                "a bracketed timestamp needs at_upper; rule C4 forbids imputing a midpoint, so "
                "the bracket must be carried explicitly (request " + self.request_ref + ")"
            )


@dataclass(frozen=True)
class RequestSpell:
    """
    Unit. One request as a time-to-event record, with its censoring carried
    explicitly rather than implied by a missing timestamp.

    Field by field against the normative rules:

    - `at_risk_from`, `left_truncated`  -> C3, delayed entry
    - `duration_hours`                  -> C2 and C8, wall clock to min(terminal, window.end)
    - `duration_active_hours`           -> C8, only where the vertical declares sla_clock="active"
    - `event_observed`                  -> C1, an open request is False, never dropped
    - `outcome`                         -> C5, the competing cause when it is not "resolved"
    - `terminal_at`                     -> C10, None when unknown; never carried forward
    - `censoring`                       -> C2 and C4, which kind of censoring applies
    - `interval_lo_hours` / `interval_hi_hours` -> C4, the bracket, never a midpoint
    - `paused_hours`                    -> C8, the difference between the two clocks
    - `reopened_count`                  -> C6, under reopen_policy="extend"
    - `duplicate_count`                 -> C7, requests merged INTO this one
    - `covariates`                      -> C9, what the censoring-informative check compares
    """

    request_ref: str
    opened_at: datetime
    at_risk_from: datetime
    left_truncated: bool
    duration_hours: float
    duration_active_hours: float | None
    event_observed: bool
    outcome: RequestOutcome | None
    terminal_at: datetime | None
    censoring: CensoringKind
    interval_lo_hours: float | None
    interval_hi_hours: float | None
    first_response_hours: float | None    # opened -> first acknowledged/comment by a non-author
    paused_hours: float
    reopened_count: int
    duplicate_count: int
    category: str
    subcategory: str | None = None
    priority: str | None = None
    channel: str | None = None
    location_ref: str | None = None
    group_ref: str | None = None
    assignee_ref: str | None = None       # the assignee at terminal, or the current one
    parent_ref: str | None = None         # the parent spell under reopen_policy="new_spell"
    n_reassignments: int = 0
    covariates: Mapping[str, float | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # C1 and C10 as type-level guards: an unobserved event cannot carry a
        # terminal timestamp, and an observed one cannot lack a cause.
        if self.event_observed and self.terminal_at is None and self.censoring != "interval":
            raise ValueError(
                "spell " + self.request_ref + " claims an observed event with no terminal_at; "
                "rule C10 forbids inferring one"
            )
        if not self.event_observed and self.censoring == "none":
            raise ValueError(
                "spell " + self.request_ref + " has no observed event, so it is censored; "
                "censoring='none' is reserved for observed terminals (rules C1, C2)"
            )
        if self.censoring == "interval" and (self.interval_lo_hours is None or self.interval_hi_hours is None):
            raise ValueError(
                "spell " + self.request_ref + " is interval-censored but carries no bracket; "
                "rule C4 forbids imputing a midpoint"
            )
        if self.duration_hours < 0:
            raise ValueError("spell " + self.request_ref + " has a negative duration")

    @property
    def clock_hours(self) -> float:
        """
        The wall clock, always available. A service wanting the active clock
        must ask for `duration_active_hours` explicitly and handle its absence,
        because rule C8 makes the choice a declared parameter, not a default.
        """
        return self.duration_hours


@dataclass(frozen=True)
class FlowPeriod:
    """
    Unit. Periodised counts for SPC, queueing and forecasting.

    `active_servers` is the one input Pack 1 needs that no single stream
    produces: a member_lifecycle role fact crossed with request_flow assignment
    activity. It is filled by the declared cross-stream reducer
    `streams.capacity.active_servers`, never inferred inside the queueing module.
    """

    period_start: datetime
    period_end: datetime
    arrivals: int                    # opened_at in period
    terminals: int                   # any terminal in period
    resolutions: int                 # outcome == "resolved"
    backlog_end: int                 # open at period_end. Little's Law L.
    backlog_start: int
    active_servers: float
    arrival_rate_per_day: float
    exposure_days: float             # period length, for Poisson rate charts with unequal periods
    complete: bool                   # period_end <= window.complete_through


__all__ = [
    "CENSORING_RULES",
    "CensoringKind",
    "FlowPeriod",
    "ReopenPolicy",
    "RequestEvent",
    "RequestEventKind",
    "RequestOutcome",
    "RequestSpell",
    "SlaClock",
    "TERMINAL_KINDS",
]
