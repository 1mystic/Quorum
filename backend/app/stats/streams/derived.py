"""
Thin derived units. docs/DATA_SPINE.md section 7.

These are not streams. They are the small shapes a reducer produces from a
stream unit so that one implementation serves several sources: one
Beta-Binomial shrinkage implementation serves vendor resolved-within-SLA rates
from `RequestSpell`, on-time payment rates from `DueSpell` and attendance rates
from `ParticipationEvent`, because all three reduce to a `RateObservation`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class RateObservation:
    """(group_ref, successes, trials) over a window. Feeds every Beta-Binomial service."""

    group_ref: str
    successes: int
    trials: int
    window_start: datetime
    window_end: datetime
    group_key: str | None = None      # anonymised key for cross-tenant pooling; never a tenant id
    strata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.trials < 0 or self.successes < 0:
            raise ValueError("RateObservation counts cannot be negative (group " + self.group_ref + ")")
        if self.successes > self.trials:
            raise ValueError(
                "RateObservation for " + self.group_ref + " has more successes than trials"
            )


@dataclass(frozen=True)
class CountObservation:
    """
    (group_ref, events, exposure) over a window. Feeds every Gamma-Poisson
    service. Exposure is explicit so a resolver active for two weeks is never
    compared against one active for a year.
    """

    group_ref: str
    events: int
    exposure: float
    window_start: datetime
    window_end: datetime
    group_key: str | None = None
    strata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.events < 0:
            raise ValueError("CountObservation events cannot be negative (group " + self.group_ref + ")")
        if self.exposure <= 0:
            raise ValueError(
                "CountObservation for " + self.group_ref + " has no exposure; a rate with a zero "
                "denominator is not a rate"
            )


@dataclass(frozen=True)
class PairwiseResult:
    """
    One head-to-head comparison, for Bradley-Terry and Elo. Derived from
    RequestSpell head-to-heads, match results, or Ballot pairs.
    """

    winner_ref: str
    loser_ref: str
    at: datetime
    drawn: bool = False
    first_position_ref: str | None = None   # for the home-advantage / order-effect check
    context_ref: str | None = None

    def __post_init__(self) -> None:
        if self.winner_ref == self.loser_ref:
            raise ValueError("a PairwiseResult cannot compare " + self.winner_ref + " with itself")


__all__ = ["CountObservation", "PairwiseResult", "RateObservation"]
