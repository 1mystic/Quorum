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
    Ballot,
    DecisionOption,
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


def decision_ref(decision_id: int) -> str:
    return "dec_" + str(decision_id)


def option_ref(option_id: int) -> str:
    return "opt_" + str(option_id)


# `ParticipationEventLog.object_type` is a free string (docs/DATA_SPINE.md's
# object_ref/object_kind pair). Known types get the short prefix the rest of
# this module already uses for the same entity elsewhere (event -> "e",
# announcement -> "a"); an unrecognised type is passed through unprefixed
# rather than silently dropped.
_OBJECT_TYPE_PREFIX: Mapping[str, str] = {
    "event": "e",
    "announcement": "a",
    "request": "r",
    "poll": "poll",
    "decision": "poll",
    "campaign": "campaign",
}


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

    **What the ported schema cannot supply.** Card C.10 closed the `ledger`
    gap: `app.models.ledger`'s five tables (Due, Payment, Receipt,
    Contribution, Expense) now back `ledger_entries` below, and
    `rwa_society`'s two most interview-grounded statistics (verification lag,
    receipt-collection gap) have rows to read. Three of the six streams still
    have no table behind them: the exposure log, decision/option/ballot, and
    member lifecycle events (lapse/reinstate/exit). Each remaining gap is
    marked TODO on the method that would fill it and names the missing model.
    None is invented: an adapter that fabricates a stream is worse than one
    that declares it empty, and a service whose stream is empty returns
    `InsufficientData`, which the pack registry turns into "this pack needs
    the decision stream switched on" rather than an error.
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

    # ---- ledger -----------------------------------------------------------

    def ledger_entries(self, rows: Iterable[Any]) -> tuple[LedgerEntry, ...]:
        """
        Card C.10. Closes the gap this class's own docstring named: there was
        no ledger model, so `forecast_risk`'s money half, `montecarlo.
        runway_shortfall`, `risk.late_payment_risk` and `audit.*` had nothing
        to read, and rwa_society's two most interview-grounded headline
        statistics (verification lag, receipt-collection gap) could not exist.

        `app.models.ledger` now has five tables (Due, Payment, Receipt,
        Contribution, Expense; see that module's docstring), and this method
        is where they get read, once, exactly like `request_events` reads
        `Request` for both verticals. Rows are dispatched by the attributes
        they carry, not by isinstance, so this stays testable against plain
        fixtures with no database (same discipline as `participation_events`
        below).

        One LedgerEntry per row:

        - `Due` -> the receivable itself: inflow, `due_at` set, status tracks
          whether it has been paid, `verified_at`/receipt fields folded in
          from whichever settling Payment has them, so `DueSpell` (rule L1)
          has a single row to reduce rather than a due and its payment both
          claiming the same money.
        - `Payment` not linked to a Due (`due_id is None`) -> a standalone
          inflow, e.g. a one-off festival-fund collection nobody billed.
        - `Contribution` -> inflow, `due_at` unset: never a receivable.
        - `Expense` -> outflow, amount sign-flipped per the atom's contract.
        """
        entries: list[LedgerEntry] = []
        for row in rows:
            if hasattr(row, "due_at") and hasattr(row, "issued_at") and not hasattr(row, "instrument"):
                entries.append(self._due_entry(row))
            elif hasattr(row, "due_id"):
                if row.due_id is None:
                    entries.append(self._payment_entry(row))
                # Payments settling a Due are folded into that Due's own
                # entry above, never emitted twice: the receivable and its
                # settlement are the same signed movement, not two.
            elif hasattr(row, "approved_by_id"):
                entries.append(self._expense_entry(row))
            elif hasattr(row, "kind") and hasattr(row, "campaign_ref"):
                entries.append(self._contribution_entry(row))
        entries.sort(key=lambda e: (e.entry_ref, e.at))
        return tuple(entries)

    def _due_entry(self, due: Any) -> LedgerEntry:
        settling = [p for p in (getattr(due, "payments", None) or []) if p.due_id == due.id]
        verified = next((p for p in settling if p.verified_at is not None), None)
        receipted = next((p for p in settling if getattr(p, "receipt", None) is not None), None)
        status = due.status.value if hasattr(due.status, "value") else str(due.status)
        ledger_status = {
            "open": "expected", "partial": "pending", "paid": "settled",
            "waived": "written_off", "written_off": "written_off",
        }.get(status.lower(), "expected")
        return LedgerEntry(
            entry_ref="due_" + str(due.id),
            at=utc(due.issued_at),
            booked_at=utc(due.issued_at),
            amount_minor=abs(int(due.amount_minor)),
            currency=due.currency,
            category=self.ledger_category(due.category),
            subcategory=getattr(due, "subcategory", None),
            direction="inflow",
            instrument="adjustment",
            status=ledger_status,
            member_ref=member_ref(due.member_id),
            group_ref=group_ref(getattr(due, "group_id", None)),
            due_at=utc(due.due_at),
            settled_at=utc(verified.settled_at) if verified else None,
            verified_at=utc(verified.verified_at) if verified else None,
            verified_by_ref=member_ref(verified.verified_by_id) if verified else None,
            receipt_issued_at=utc(receipted.receipt.issued_at) if receipted else None,
            receipt_collected_at=utc(receipted.receipt.collected_at) if receipted else None,
            reconciled=bool(verified.reconciled) if verified else False,
        )

    def _payment_entry(self, payment: Any) -> LedgerEntry:
        status = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
        instrument = payment.instrument.value if hasattr(payment.instrument, "value") else str(payment.instrument)
        receipt = getattr(payment, "receipt", None)
        return LedgerEntry(
            entry_ref="pay_" + str(payment.id),
            at=utc(payment.at),
            booked_at=utc(payment.booked_at),
            amount_minor=abs(int(payment.amount_minor)),
            currency=payment.currency,
            category=self.ledger_category(payment.category),
            subcategory=getattr(payment, "subcategory", None),
            direction="inflow",
            instrument=instrument,
            status=status,
            member_ref=member_ref(payment.member_id),
            group_ref=group_ref(getattr(payment, "group_id", None)),
            campaign_ref=getattr(payment, "campaign_ref", None),
            settled_at=utc(payment.settled_at),
            verified_at=utc(payment.verified_at),
            verified_by_ref=member_ref(payment.verified_by_id),
            receipt_issued_at=utc(receipt.issued_at) if receipt else None,
            receipt_collected_at=utc(receipt.collected_at) if receipt else None,
            reconciled=bool(payment.reconciled),
        )

    def _contribution_entry(self, contribution: Any) -> LedgerEntry:
        kind = contribution.kind.value if hasattr(contribution.kind, "value") else str(contribution.kind)
        return LedgerEntry(
            entry_ref="con_" + str(contribution.id),
            at=utc(contribution.at),
            booked_at=utc(contribution.at),
            amount_minor=abs(int(contribution.amount_minor)),
            currency=contribution.currency,
            category=self.ledger_category(contribution.category),
            direction="inflow",
            instrument="in_kind" if kind == "in_kind" else "adjustment",
            status="settled",
            member_ref=member_ref(contribution.member_id),
            group_ref=group_ref(getattr(contribution, "group_id", None)),
            campaign_ref=getattr(contribution, "campaign_ref", None),
            settled_at=utc(contribution.at),
            reconciled=True,
        )

    def _expense_entry(self, expense: Any) -> LedgerEntry:
        status = expense.status.value if hasattr(expense.status, "value") else str(expense.status)
        instrument = expense.instrument.value if hasattr(expense.instrument, "value") else str(expense.instrument)
        return LedgerEntry(
            entry_ref="exp_" + str(expense.id),
            at=utc(expense.at),
            booked_at=utc(expense.booked_at),
            amount_minor=-abs(int(expense.amount_minor)),
            currency=expense.currency,
            category=self.ledger_category(expense.category),
            subcategory=getattr(expense, "subcategory", None),
            direction="outflow",
            instrument=instrument,
            status=status,
            counterparty_ref=getattr(expense, "counterparty_ref", None),
            group_ref=group_ref(getattr(expense, "group_id", None)),
            campaign_ref=getattr(expense, "campaign_ref", None),
            settled_at=utc(expense.settled_at),
            reconciled=bool(expense.reconciled),
        )

    # ---- participation ----------------------------------------------------

    def participation_events(self, rows: Iterable[Any]) -> tuple[ParticipationEvent, ...]:
        """
        `EventRegistration`, `Announcement` and `ParticipationEventLog` rows to
        participation atoms.

        Card C.15 closes the gap this method's own TODO named: there was no
        exposure-log table, so `nudge_sent`/`nudge_delivered`/`nudge_opened`/
        `nudge_acted` and `arm_ref` had nowhere to be recorded and Pack 2's
        `experiments.*`/`bandits.*` had no input at all. `ParticipationEventLog`
        (`app/models/participation.py`) now carries every kind the spine
        declares, including the four exposure kinds with their `arm_ref`, and
        this is where those rows get read, once, dispatched by the attributes
        they carry rather than by isinstance, same discipline as
        `request_events` and `ledger_entries` above.
        """
        events: list[ParticipationEvent] = []
        for row in rows:
            if hasattr(row, "checked_in"):
                events.extend(self._registration_events(row))
            elif hasattr(row, "kind") and hasattr(row, "arm_ref"):
                events.append(self._participation_log_event(row))
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

    def _participation_log_event(self, row: Any) -> ParticipationEvent:
        kind = row.kind.value if hasattr(row.kind, "value") else str(row.kind)
        object_type = getattr(row, "object_type", None)
        object_id = getattr(row, "object_id", None)
        prefix = _OBJECT_TYPE_PREFIX.get(object_type, object_type) if object_type else None
        ref = object_ref(prefix, object_id) if prefix and object_id is not None else None
        weight = row.weight if getattr(row, "weight", None) is not None else 1.0
        return ParticipationEvent(
            member_ref=member_ref(row.member_id),
            at=utc(row.at),
            kind=kind,
            object_ref=ref,
            object_kind=object_type,
            group_ref=group_ref(getattr(row, "group_id", None)),
            weight=float(weight),
            channel=getattr(row, "channel", None),
            arm_ref=getattr(row, "arm_ref", None),
            strata=dict(getattr(row, "strata", None) or {}),
        )

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

    # ---- decision -------------------------------------------------------
    #
    # `ledger_entries` for the real Due/Payment/Receipt/Contribution/Expense
    # mapping now lives above, next to member_lifecycle (card C.10). Card
    # C.15 closes this section's own TODO: `Decision`/`DecisionOption`/
    # `Ballot` (`app/models/decision.py`) now back `decisions`,
    # `decision_options` and `ballots` below, exactly the reading-once
    # discipline `request_events` and `ledger_entries` already use.
    #
    # `decisions()` alone satisfies the `VerticalAdapter` Protocol;
    # `decision_options()`/`ballots()` are an addition beyond it, because
    # `app/stats/voting.py`/`budgeting.py` take `ballots, options, spec` as
    # three separate arguments rather than through one combined method.

    def decisions(self, rows: Iterable[Any]) -> tuple[DecisionSpec, ...]:
        """
        `Decision` rows to `DecisionSpec` atoms.

        Rule D1 was already enforced before a row could reach here:
        `Decision.declared_rule` is `nullable=False` from its first migration
        (card C.15) and `DecisionService` additionally checks it against the
        six declared rules, so every row this method sees always has one, and
        `DecisionSpec.__post_init__`'s own check is a second line, not the
        only one.
        """
        specs = [self._decision_spec(row) for row in rows]
        specs.sort(key=lambda d: d.opened_at)
        return tuple(specs)

    def _decision_spec(self, decision: Any) -> DecisionSpec:
        kind = decision.kind.value if hasattr(decision.kind, "value") else str(decision.kind)
        ballot_style = (
            decision.ballot_style.value if hasattr(decision.ballot_style, "value")
            else str(decision.ballot_style)
        )
        eligible: dict[tuple[str, ...], int] = {}
        for row in (decision.eligible_strata or ()):
            strata = row.get("strata", {}) or {}
            key = tuple(value for _, value in sorted(strata.items()))
            eligible[key] = row.get("count", 0)
        return DecisionSpec(
            decision_ref=decision_ref(decision.id),
            kind=kind,
            opened_at=utc(decision.opened_at),
            closed_at=utc(decision.closed_at),
            declared_rule=decision.declared_rule,
            seats=decision.seats,
            quorum_rule=decision.quorum_rule,
            budget_minor=decision.budget_minor,
            eligible_strata=eligible,
            ballot_style=ballot_style,
        )

    def decision_options(self, rows: Iterable[Any]) -> tuple[DecisionOption, ...]:
        """`DecisionOption` rows to atoms. `cost_minor` stays null outside participatory budgeting."""
        options = [
            DecisionOption(
                option_ref=option_ref(row.id),
                decision_ref=decision_ref(row.decision_id),
                label=row.label,
                cost_minor=row.cost_minor,
                tags=tuple(row.tags or ()),
                proposer_ref=member_ref(getattr(row, "proposer_id", None)),
            )
            for row in rows
        ]
        options.sort(key=lambda o: (o.decision_ref, o.option_ref))
        return tuple(options)

    def ballots(self, rows: Iterable[Any]) -> tuple[Ballot, ...]:
        """
        `Ballot` rows to atoms. `Ballot.__post_init__` rejects a ranking that
        repeats an option across tiers, so an invalid stored ballot surfaces
        loudly here rather than being silently repaired.
        """
        out = [self._ballot_atom(row) for row in rows]
        out.sort(key=lambda b: (b.decision_ref, b.cast_at))
        return tuple(out)

    @staticmethod
    def _ballot_atom(row: Any) -> Ballot:
        ranking = tuple(
            tuple(option_ref(option_id) for option_id in tier)
            for tier in (row.ranking or ())
        )
        approvals = frozenset(option_ref(option_id) for option_id in (row.approvals or ()))
        scores = {option_ref(int(k)): v for k, v in (row.scores or {}).items()}
        allocation = {option_ref(int(k)): v for k, v in (row.allocation or {}).items()}
        return Ballot(
            ballot_ref="bal_" + str(row.id),
            decision_ref=decision_ref(row.decision_id),
            voter_ref=member_ref(row.voter_id),
            cast_at=utc(row.cast_at),
            ranking=ranking,
            approvals=approvals,
            scores=scores,
            allocation=allocation,
            strata=dict(getattr(row, "strata", None) or {}),
            channel=getattr(row, "channel", None),
        )


__all__ = [
    "OTHER",
    "BaseAdapter",
    "PortedSchemaAdapter",
    "VerticalAdapter",
    "decision_ref",
    "group_ref",
    "member_ref",
    "object_ref",
    "option_ref",
    "request_ref",
    "utc",
]
