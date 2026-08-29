"""
The six canonical streams, as typed frozen dataclasses. docs/DATA_SPINE.md.

A stream is not a table. It is a shape that pure statistical code consumes. The
database may store it in five tables or one; the vertical adapter's job is to
produce the shape, and the adapter is the only place a domain word like
"complaint" or "case" appears.

```
  Postgres rows                            (services / repository, impure)
        |  adapter: vertical -> canonical  (app/verticals/adapters/*.py)
        v
  Stream ATOMS: append-only events         (frozen dataclasses, here)
        |  reducer: atoms -> analysis units (PURE, here)
        v
  Stream UNITS: spells, periods, features  (frozen dataclasses, here)
        |  service function                (PURE, app/stats/*.py)
        v
  Evidence
```

The reducers are pure and are where the correctness lives. Censoring is decided
in a reducer, not in a SQL WHERE clause: a `WHERE resolved_at IS NOT NULL` in a
repository is invisible to the test suite, whereas a reducer that mis-censors
fails a known-answer test.
"""
from app.stats.streams.decision import (
    Ballot,
    BallotStyle,
    DecisionKind,
    DecisionOption,
    DecisionSpec,
)
from app.stats.streams.derived import CountObservation, PairwiseResult, RateObservation
from app.stats.streams.ledger import (
    DueSpell,
    LedgerEntry,
    LedgerInstrument,
    LedgerPeriod,
    LedgerStatus,
)
from app.stats.streams.member import (
    MemberEvent,
    MemberEventKind,
    MemberSpell,
    RosterSnapshot,
)
from app.stats.streams.participation import (
    EXPOSURE_KINDS,
    EngagementFeatures,
    InteractionEdge,
    ParticipationEvent,
    ParticipationKind,
    ParticipationPeriod,
)
from app.stats.streams.request import (
    CENSORING_RULES,
    TERMINAL_KINDS,
    CensoringKind,
    FlowPeriod,
    ReopenPolicy,
    RequestEvent,
    RequestEventKind,
    RequestOutcome,
    RequestSpell,
    SlaClock,
)
from app.stats.streams.signal import OrdinalResponse, SignalRecord, SignalSource, TextDoc
from app.stats.streams.window import CalendarMark, StreamWindow

# The six canonical stream ids. A pack declares which it requires; a vertical
# declares which it supports. A service whose stream is unsupported raises
# InsufficientData, which the registry turns into "this pack needs the ledger
# switched on" rather than an error.
STREAM_IDS: frozenset[str] = frozenset(
    {
        "member_lifecycle",
        "request_flow",
        "ledger",
        "participation",
        "signal",
        "decision",
    }
)

# Unit names, as used by ServiceSpec.required_units.
UNIT_NAMES: frozenset[str] = frozenset(
    {
        "MemberSpell",
        "RosterSnapshot",
        "RequestSpell",
        "FlowPeriod",
        "DueSpell",
        "LedgerEntry",
        "LedgerPeriod",
        "EngagementFeatures",
        "InteractionEdge",
        "ParticipationEvent",
        "ParticipationPeriod",
        "TextDoc",
        "OrdinalResponse",
        "Ballot",
        "DecisionOption",
        "DecisionSpec",
        "RateObservation",
        "CountObservation",
        "PairwiseResult",
        # Not stream data: arrays supplied by the caller or an earlier envelope.
        "ScoreArray",
        "ProbabilityArray",
        "ResidualArray",
        "FeatureArray",
        "Posterior",
        "Forecast",
        "TableEvidence",
    }
)

__all__ = [
    "CENSORING_RULES",
    "EXPOSURE_KINDS",
    "STREAM_IDS",
    "TERMINAL_KINDS",
    "UNIT_NAMES",
    "Ballot",
    "BallotStyle",
    "CalendarMark",
    "CensoringKind",
    "CountObservation",
    "DecisionKind",
    "DecisionOption",
    "DecisionSpec",
    "DueSpell",
    "EngagementFeatures",
    "FlowPeriod",
    "InteractionEdge",
    "LedgerEntry",
    "LedgerInstrument",
    "LedgerPeriod",
    "LedgerStatus",
    "MemberEvent",
    "MemberEventKind",
    "MemberSpell",
    "OrdinalResponse",
    "PairwiseResult",
    "ParticipationEvent",
    "ParticipationKind",
    "ParticipationPeriod",
    "RateObservation",
    "ReopenPolicy",
    "RequestEvent",
    "RequestEventKind",
    "RequestOutcome",
    "RequestSpell",
    "RosterSnapshot",
    "SignalRecord",
    "SignalSource",
    "SlaClock",
    "StreamWindow",
    "TextDoc",
]
