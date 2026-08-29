"""
The window context, passed with every stream. docs/DATA_SPINE.md section 0.

`complete_through` is a first-class field, separate from `end`, because
reporting lag is a property of the pipeline rather than of any event. The last
week of a ledger series is partial until the treasurer finishes reconciling,
and a forecaster fitted through `end` reads that partial bucket as a collapse
in collections. Every periodised service truncates at `complete_through` and
records the gap as a caveat. Nothing else in the spine protects against this.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CalendarMark:
    """A holiday, festival, term break or season boundary the vertical declares."""

    at: date
    kind: str          # "holiday" | "festival" | "term_break" | "season_start"
    label: str


@dataclass(frozen=True)
class StreamWindow:
    start: datetime               # inclusive, UTC. The analysis window opens here.
    end: datetime                 # exclusive, UTC. THE observation boundary and censoring time.
    timezone: str                 # IANA name, e.g. "Asia/Kolkata". Calendar bucketing only.
    complete_through: datetime    # data believed complete up to here; <= end
    calendar: tuple[CalendarMark, ...] = ()

    def __post_init__(self) -> None:
        for name in ("start", "end", "complete_through"):
            value = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError("StreamWindow." + name + " must be timezone-aware UTC (spine rule S1)")
        if self.end <= self.start:
            raise ValueError("StreamWindow.end must be after start")
        if self.complete_through > self.end:
            raise ValueError(
                "StreamWindow.complete_through cannot exceed end; data cannot be complete "
                "past the observation boundary"
            )

    @property
    def reporting_lag_days(self) -> float:
        """The gap a periodised service must disclose as a caveat."""
        return (self.end - self.complete_through).total_seconds() / 86400.0


__all__ = ["CalendarMark", "StreamWindow"]
