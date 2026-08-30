"""
The adapter contract. docs/DATA_SPINE.md section 9.

A vertical adapter is the only code that knows domain words. It turns ORM rows
into canonical stream atoms and it is the boundary between "complaint" and
`RequestEvent`. Nothing downstream of it knows which vertical it came from.

Purity note: an adapter is impure at the repository EDGE, meaning the caller
does the fetching. The adapter itself takes rows it was handed and returns
frozen dataclasses, so it stays testable offline. It never opens a session and
never issues a query, and it never appears in an import from `app/stats/`.

Adapter obligations, checked by the shared conformance suite every vertical must
pass before it is selectable:

1. Every emitted category, priority, reason and stratum value is in the declared
   vocabulary. An unmapped domain value becomes "other" and increments a counter
   that surfaces as a caveat, never a silent drop.
2. Every stratum is low-cardinality: at most min(20, roster_size // k).
3. Timestamps are UTC and monotonic per entity: no resolved before opened.
4. amount_minor is int; currency is uniform per tenant unless declared otherwise.
5. Terminal events are unique per request_ref under the declared reopen policy.
6. `TextDoc` construction strips member_ref. The adapter cannot produce a
   TextDoc with identity because the type has no field for it.
7. **The adapter never filters on outcome.** Filtering to closed requests at the
   adapter is exactly the defect rule C1 exists to prevent, and the conformance
   suite includes a fixture with open requests that must survive untouched.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping, Protocol, runtime_checkable

from app.stats.streams import (
    DecisionSpec,
    LedgerEntry,
    MemberEvent,
    ParticipationEvent,
    RequestEvent,
    SignalRecord,
    TextDoc,
)

OTHER = "other"


@runtime_checkable
class VerticalAdapter(Protocol):
    """The shape every vertical adapter satisfies."""

    vertical_id: str
    strata_schema: Mapping[str, tuple[str, ...]]
    request_categories: tuple[str, ...]
    request_priorities: tuple[str, ...]
    exit_reasons: tuple[str, ...]
    ledger_categories: tuple[str, ...]
    k_anonymity_threshold: int
    reopen_policy: Literal["new_spell", "extend"]
    sla_clock: Literal["wall", "active"]

    def member_events(self, rows) -> tuple[MemberEvent, ...]: ...

    def request_events(self, rows) -> tuple[RequestEvent, ...]: ...

    def ledger_entries(self, rows) -> tuple[LedgerEntry, ...]: ...

    def participation_events(self, rows) -> tuple[ParticipationEvent, ...]: ...

    def signals(self, rows) -> tuple[SignalRecord, ...]: ...

    def decisions(self, rows) -> tuple[DecisionSpec, ...]: ...


def utc(value: datetime | None) -> datetime | None:
    """
    Every timestamp crossing into a stream is timezone-aware UTC (spine rule S1).

    A naive datetime is a bug at the model layer, not something to guess about,
    so it is treated as UTC and counted rather than silently localised to the
    server's zone, which would move every duration by hours.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def member_ref(member_id: int | None) -> str | None:
    """
    An opaque, per-tenant stable pseudonym (spine rule S3).

    The surrogate key is already opaque: it is not an email, a phone number or a
    name, and it is stable across runs so a member_ref means the same person in
    August and September. The doc_ref to member_ref map stays in the service
    layer; nothing in app/stats/ can reverse this.
    """
    if member_id is None:
        return None
    return "m_" + str(member_id)


def request_ref(request_id: int) -> str:
    return "r_" + str(request_id)


def group_ref(group_id: int | None) -> str | None:
    return None if group_id is None else "g_" + str(group_id)


def object_ref(prefix: str, object_id: int | None) -> str | None:
    return None if object_id is None else prefix + "_" + str(object_id)


class BaseAdapter:
    """
    Shared machinery. Subclasses declare vocabulary and do the mapping.

    Unmapped values are counted rather than dropped: `unmapped_report()` is what
    a caller turns into an `Evidence` caveat, so a vertical that is quietly
    losing a fifth of its categories to "other" is visible rather than merely
    tidy.
    """

    vertical_id: str = ""
    strata_schema: Mapping[str, tuple[str, ...]] = {}
    request_categories: tuple[str, ...] = ()
    request_priorities: tuple[str, ...] = ()
    exit_reasons: tuple[str, ...] = ()
    ledger_categories: tuple[str, ...] = ()
    participation_kinds: tuple[str, ...] = ()
    k_anonymity_threshold: int = 5
    reopen_policy: Literal["new_spell", "extend"] = "new_spell"
    sla_clock: Literal["wall", "active"] = "wall"
    currency: str = "INR"

    def __init__(self) -> None:
        self._unmapped: Counter[str] = Counter()

    # ---- vocabulary -----------------------------------------------------

    def _vocab(self, field: str, value: Any, allowed: tuple[str, ...]) -> str:
        """Map a domain value into the declared vocabulary, or into 'other', counted."""
        if value is None:
            self._unmapped[field + ":<null>"] += 1
            return OTHER
        text = value.value if hasattr(value, "value") else str(value)
        candidate = text.strip().lower()
        if candidate in allowed:
            return candidate
        self._unmapped[field + ":" + candidate] += 1
        return OTHER

    def category(self, value: Any) -> str:
        return self._vocab("category", value, self.request_categories)

    def priority(self, value: Any) -> str:
        return self._vocab("priority", value, self.request_priorities)

    def exit_reason(self, value: Any) -> str:
        return self._vocab("exit_reason", value, self.exit_reasons)

    def ledger_category(self, value: Any) -> str:
        return self._vocab("ledger_category", value, self.ledger_categories)

    def strata(self, values: Mapping[str, Any]) -> dict[str, str]:
        """Only declared strata with declared values survive. An undeclared stratum is dropped."""
        out: dict[str, str] = {}
        for name, allowed in self.strata_schema.items():
            if name not in values:
                continue
            out[name] = self._vocab("stratum:" + name, values[name], allowed)
        return out

    def unmapped_report(self) -> dict[str, int]:
        """What the caller turns into a caveat. Empty is the healthy case."""
        return dict(self._unmapped)

    def reset_counters(self) -> None:
        self._unmapped = Counter()

    # ---- text -----------------------------------------------------------

    def text_docs(self, signals: Iterable[SignalRecord]) -> tuple[TextDoc, ...]:
        """
        SignalRecord to TextDoc, which is where identity is dropped.

        The drop is structural rather than careful: `TextDoc` has no field a
        member_ref could go in, so this conversion cannot leak an author even if
        it wanted to.
        """
        return tuple(
            TextDoc(
                doc_ref=record.signal_ref,
                at=record.at,
                text=record.text,
                tokens=tuple(record.text.lower().split()),
                embedding=None,
                category_hint=record.category_hint,
            )
            for record in signals
        )

    # ---- default streams ------------------------------------------------
    #
    # A vertical that does not support a stream declares it empty. A service
    # whose required stream is empty returns InsufficientData, which the pack
    # registry turns into "this pack needs the ledger switched on", not an error.

    def member_events(self, rows) -> tuple[MemberEvent, ...]:
        return ()

    def request_events(self, rows) -> tuple[RequestEvent, ...]:
        return ()

    def ledger_entries(self, rows) -> tuple[LedgerEntry, ...]:
        return ()

    def participation_events(self, rows) -> tuple[ParticipationEvent, ...]:
        return ()

    def signals(self, rows) -> tuple[SignalRecord, ...]:
        return ()

    def decisions(self, rows) -> tuple[DecisionSpec, ...]:
        return ()


class PortedSchemaAdapter(BaseAdapter):
    """
    The half of an adapter that both shipped verticals share: mapping the
    CURRENT ported schema (`Request`, `Member`, `EventRegistration`,
    `Announcement`) onto stream atoms.

    It exists because `rwa_society` and `campus_club` differ in vocabulary and in
    strata, not in where the rows come from. When the missing models arrive this
    class is where they get read, once, rather than twice.

    Rows are dispatched by the attributes they carry rather than by isinstance,
    so this module does not import the ORM and every method is testable against
    plain fixtures with no database.

    **What the ported schema cannot supply.** Four of the six streams have no
    table behind them yet. Each gap is marked TODO on the method that would fill
    it and names the missing model. None is invented: an adapter that fabricates
    a stream is worse than one that declares it empty, and a service whose stream
    is empty returns `InsufficientData`, which the pack registry turns into "this
    pack needs the ledger switched on" rather than an error.
    """

    # Subclasses map the ported Campus Connect `RequestCategory` enum into their
    # own declared vocabulary. Anything absent from the map becomes "other" and
    # is counted by `unmapped_report()`.
    legacy_request_categories: Mapping[str, str] = {}

    def member_strata(self, row: Any) -> dict[str, str]:
        """Vertical-specific: pull declared strata off a member row. Default: none."""
        return {}

    # ---- request_flow ---------------------------------------------------

    def request_events(self, rows: Iterable[Any]) -> tuple[RequestEvent, ...]:
        """
        `Request` rows to atoms. Every row that exists produces an "opened"
        event, whatever its status.

        There is deliberately no `status` filter and no `resolved_at IS NOT NULL`
        anywhere in this method, and there will not be one. Filtering to closed
        requests at the adapter is exactly the defect spine rule C1 exists to
        prevent, and the conformance suite has a fixture of open requests that
        must come through untouched.

        Card C.8 closed two of this method's gaps: `Request` now carries
        `priority`, `channel`, `location_ref` and `subcategory` columns, read
        directly below, and there is now a `RequestEventLog` table
        (`app/models/request_event.py`) recording "assigned", "reassigned",
        "paused", "resumed", "escalated", "withdrawn", "merged" and "reopened".
        This method still only synthesises the three lifecycle events a bare
        `Request` row can prove by itself (opened / acknowledged / resolved);
        reading the richer event log and folding its rows in here - so
        survival.competing_risks_cif and duration_active_hours actually have
        something to estimate - is a stream-reducer integration, left to
        whoever wires `streams/reduce.py` against `RequestRepository.stream_events`.
        """
        events: list[RequestEvent] = []
        for row in rows:
            ref = request_ref(row.id)
            raw_category = getattr(row.category, "value", row.category)
            raw_priority = getattr(row, "priority", None)
            common = {
                "request_ref": ref,
                "category": self.category(
                    self.legacy_request_categories.get(str(raw_category), raw_category)
                ),
                "subcategory": getattr(row, "subcategory", None),
                "priority": self.priority(raw_priority) if raw_priority is not None else None,
                "channel": getattr(row, "channel", None),
                "location_ref": getattr(row, "location_ref", None),
                "group_ref": group_ref(getattr(row, "group_id", None)),
            }
            events.append(
                RequestEvent(
                    at=utc(row.created_at),
                    kind="opened",
                    actor_ref=member_ref(row.member_id),
                    **common,
                )
            )
            responder = member_ref(getattr(row, "responded_by", None))
            responded_at = utc(getattr(row, "responded_at", None))
            if responded_at is not None:
                events.append(
                    RequestEvent(
                        at=responded_at,
                        kind="acknowledged",
                        actor_ref=responder,
                        assignee_ref=responder,
                        **common,
                    )
                )
            resolved_at = utc(getattr(row, "resolved_at", None))
            if resolved_at is not None:
                events.append(
                    RequestEvent(
                        at=resolved_at,
                        kind="resolved",
                        actor_ref=responder,
                        assignee_ref=responder,
                        **common,
                    )
                )
        events.sort(key=lambda e: (e.request_ref, e.at))
        return tuple(events)

    # ---- member_lifecycle -----------------------------------------------

    def member_events(self, rows: Iterable[Any]) -> tuple[MemberEvent, ...]:
        """
        `Member` rows to join events.

        TODO(missing model): no lapse, reinstate or exit record exists, so
        survival.churn_curve sees a population where nobody has ever left and
        would report a flat curve at 1.0. Its floor of 30 observed exits stops
        that from being published, which is the floor doing its job, but the
        stream is genuinely incomplete until a member lifecycle event table
        exists.
        """
        events = [
            MemberEvent(
                member_ref=member_ref(row.id),
                at=utc(row.created_at),
                kind="join",
                strata=self.member_strata(row),
                source="app",
            )
            for row in rows
        ]
        events.sort(key=lambda e: (e.member_ref, e.at))
        return tuple(events)

    # ---- participation ----------------------------------------------------

    def participation_events(self, rows: Iterable[Any]) -> tuple[ParticipationEvent, ...]:
        """
        `EventRegistration` and `Announcement` rows to participation atoms.

        TODO(missing model): the exposure log has no table. There is nowhere to
        record nudge_sent, nudge_delivered, nudge_opened or nudge_acted, and no
        arm_ref. Pack 2's experiments and bandits therefore have no input at all:
        without knowing who was OFFERED a nudge, an A/B test measures
        self-selection. This is the missing model that blocks a whole pack rather
        than degrading one service.
        """
        events: list[ParticipationEvent] = []
        for row in rows:
            if hasattr(row, "checked_in"):
                events.extend(self._registration_events(row))
            elif hasattr(row, "body") and hasattr(row, "author_id"):
                events.append(
                    ParticipationEvent(
                        member_ref=member_ref(row.author_id),
                        at=utc(row.created_at),
                        kind="post",
                        object_ref=object_ref("a", row.id),
                        object_kind="announcement",
                        group_ref=group_ref(getattr(row, "group_id", None)),
                    )
                )
        events.sort(key=lambda e: (e.at, e.member_ref, e.kind))
        return tuple(events)

    def _registration_events(self, row: Any) -> list[ParticipationEvent]:
        ref = member_ref(row.member_id)
        out = [
            ParticipationEvent(
                member_ref=ref,
                at=utc(row.created_at),
                kind="rsvp",
                object_ref=object_ref("e", row.event_id),
                object_kind="event",
            )
        ]
        if getattr(row, "checked_in", False):
            out.append(
                ParticipationEvent(
                    member_ref=ref,
                    at=utc(getattr(row, "checked_in_at", None)) or utc(row.created_at),
                    kind="attend",
                    object_ref=object_ref("e", row.event_id),
                    object_kind="event",
                )
            )
        else:
            # A no-show is only knowable once the event has ended. Before that,
            # the absence of a check-in means nothing, and recording it as a
            # no-show would invent an outcome, which is rule C10's principle
            # applied outside request_flow.
            event = getattr(row, "event", None)
            ends_at = utc(getattr(event, "ends_at", None)) if event is not None else None
            if ends_at is not None:
                out.append(
                    ParticipationEvent(
                        member_ref=ref,
                        at=ends_at,
                        kind="no_show",
                        object_ref=object_ref("e", row.event_id),
                        object_kind="event",
                    )
                )
        return out

    # ---- signal ------------------------------------------------------------

    def signals(self, rows: Iterable[Any]) -> tuple[SignalRecord, ...]:
        """
        Request text. `member_ref` is carried here and stripped by `text_docs()`,
        which is the only path into a text service.

        TODO(missing model): no survey or ordinal response table exists, so
        `OrdinalResponse` cannot be produced and survey.likert_distribution and
        survey.ordinal_logistic have no input.
        """
        records: list[SignalRecord] = []
        for row in rows:
            title = getattr(row, "title", "") or ""
            description = getattr(row, "description", "") or ""
            body = (title + " " + description).strip()
            if not body:
                continue
            records.append(
                SignalRecord(
                    signal_ref="s_r_" + str(row.id),
                    at=utc(row.created_at),
                    source="request_body",
                    text=body,
                    object_ref=request_ref(row.id),
                    member_ref=member_ref(row.member_id),
                    redaction="raw",
                    category_hint=None,
                )
            )
        return tuple(records)

    # ---- ledger and decision ------------------------------------------------

    def ledger_entries(self, rows: Iterable[Any]) -> tuple[LedgerEntry, ...]:
        """
        Empty, deliberately.

        TODO(missing model): there is no ledger model. Nothing in the ported
        schema records money: no entry, no receivable, no verification and no
        receipt. Declaring the stream empty is the honest state until the model
        exists; approximating it from anything present would be fiction with a
        currency symbol.
        """
        return ()

    def decisions(self, rows: Iterable[Any]) -> tuple[DecisionSpec, ...]:
        """
        Empty, deliberately.

        TODO(missing model): there is no decision, option or ballot model. Note
        for whoever adds one: `DecisionSpec.declared_rule` must be recorded when
        the decision OPENS (spine rule D1) and therefore has to be non-nullable
        from the first migration. Adding it later leaves a history of decisions
        whose rule cannot be trusted, which is the one governance failure a
        voting module can actually cause.
        """
        return ()


__all__ = [
    "OTHER",
    "BaseAdapter",
    "PortedSchemaAdapter",
    "VerticalAdapter",
    "group_ref",
    "member_ref",
    "object_ref",
    "request_ref",
    "utc",
]
