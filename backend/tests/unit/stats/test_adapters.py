"""
Vertical adapter conformance, from docs/DATA_SPINE.md section 9.

Every vertical passes this suite before it is selectable. The critical case is
the open-request fixture: **an adapter that filters to closed requests fails,
whatever else it does.** That is spine rule C1 enforced at the boundary where it
is most tempting to break, because `WHERE resolved_at IS NOT NULL` looks like a
tidy optimisation right up until it silently understates every duration the
platform reports.

Fixtures here are plain objects, not ORM rows, which is possible because the
adapters dispatch on the attributes a row carries rather than on its class. No
database is involved and none is needed.

These live under tests/unit/stats/ rather than tests/unit/verticals/ because what
they actually assert is the shape of the streams in app/stats/streams/. The
adapter is the thing being measured against that shape.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.stats.streams import ParticipationEvent, RequestEvent
from app.verticals.adapters import ADAPTERS, CampusClubAdapter, RwaSocietyAdapter, get_adapter

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def request_row(**overrides):
    base = dict(
        id=1,
        member_id=7,
        group_id=3,
        category="TECHNICAL",
        status="OPEN",
        title="No water in the tank",
        description="Third day running.",
        responded_by=None,
        responded_at=None,
        resolved_at=None,
        created_at=T0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


ADAPTER_CLASSES = [RwaSocietyAdapter, CampusClubAdapter]


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_the_adapter_never_filters_on_outcome(adapter_class):
    """
    THE conformance test. Three open requests, one resolved, and all four must
    come through. An adapter that drops the open ones is exactly the defect rule
    C1 exists to prevent.
    """
    rows = [
        request_row(id=1),
        request_row(id=2),
        request_row(id=3),
        request_row(id=4, status="RESOLVED", responded_by=9, responded_at=T0 + timedelta(hours=2),
                    resolved_at=T0 + timedelta(days=2)),
    ]
    events = adapter_class().request_events(rows)
    opened = [e for e in events if e.kind == "opened"]
    assert len(opened) == 4, "an open request was dropped at the adapter"
    assert {e.request_ref for e in opened} == {"r_1", "r_2", "r_3", "r_4"}


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_an_open_request_emits_no_terminal_event(adapter_class):
    """It is censored downstream by the reducer, not marked resolved here."""
    events = adapter_class().request_events([request_row()])
    assert [e.kind for e in events] == ["opened"]


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_a_resolved_request_emits_its_lifecycle_in_order(adapter_class):
    row = request_row(
        status="RESOLVED",
        responded_by=9,
        responded_at=T0 + timedelta(hours=2),
        resolved_at=T0 + timedelta(days=2),
    )
    events = adapter_class().request_events([row])
    assert [e.kind for e in events] == ["opened", "acknowledged", "resolved"]
    assert [e.at for e in events] == sorted(e.at for e in events)
    assert events[-1].assignee_ref == "m_9"


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_timestamps_come_out_timezone_aware(adapter_class):
    """
    Spine rule S1. A naive timestamp at the model layer is treated as UTC rather
    than localised to whatever zone the server happens to be in, which would move
    every duration by hours.
    """
    row = request_row(created_at=datetime(2026, 1, 1, 9, 0))
    event = adapter_class().request_events([row])[0]
    assert event.at.tzinfo is not None
    assert event.at == T0


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_no_identifying_field_reaches_a_stream(adapter_class):
    """
    Spine rule S3. The adapter is handed rows that could carry an email or a
    name; what comes out is an opaque pseudonym and nothing else.
    """
    row = request_row(member_id=7)
    row.member = SimpleNamespace(email="resident@example.com", full_name="A Resident")
    event = adapter_class().request_events([row])[0]
    assert event.actor_ref == "m_7"
    for value in vars(event).values():
        assert "@" not in str(value)


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_emitted_categories_are_in_the_declared_vocabulary(adapter_class):
    adapter = adapter_class()
    rows = [request_row(id=i, category=c) for i, c in enumerate(
        ["EVENT", "GROUP", "CERTIFICATE", "TECHNICAL", "GENERAL", "SOMETHING_ELSE"], start=1
    )]
    for event in adapter.request_events(rows):
        assert event.category in adapter.request_categories


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_an_unmapped_value_is_counted_never_silently_dropped(adapter_class):
    """
    Conformance obligation 1. The row survives, its category becomes "other", and
    the counter is what a caller turns into a caveat. A vertical quietly losing a
    fifth of its categories to "other" should be visible.
    """
    adapter = adapter_class()
    events = adapter.request_events([request_row(category="NOT_A_CATEGORY")])
    assert len(events) == 1
    assert events[0].category == "other"
    assert adapter.unmapped_report()


def test_campus_club_maps_the_ported_enum_onto_its_own_vocabulary():
    """The one vertical where the legacy Campus Connect values mean something."""
    adapter = CampusClubAdapter()
    rows = [
        request_row(id=1, category="EVENT"),
        request_row(id=2, category="GROUP"),
        request_row(id=3, category="TECHNICAL"),
    ]
    assert [e.category for e in adapter.request_events(rows)] == [
        "event_logistics",
        "membership_query",
        "equipment",
    ]
    assert adapter.unmapped_report() == {}


def test_rwa_society_cannot_categorise_a_complaint_yet_and_says_so_loudly():
    """
    The honest current state: `Request.category` is still the campus enum and no
    column holds a society complaint category, so everything lands in "other" and
    every row is counted as unmapped. Nothing is invented to paper over it.
    """
    adapter = RwaSocietyAdapter()
    rows = [request_row(id=i, category=c) for i, c in enumerate(["EVENT", "TECHNICAL"], start=1)]
    events = adapter.request_events(rows)
    assert {e.category for e in events} == {"other"}
    assert sum(adapter.unmapped_report().values()) == 2


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_strata_stay_low_cardinality_and_declared(adapter_class):
    """
    Conformance obligation 2. An undeclared stratum value cannot get through: it
    becomes "other" and is counted. A stratum with as many values as members is a
    re-identifier.
    """
    adapter = adapter_class()
    member = SimpleNamespace(id=7, created_at=T0, year=99, branch="astrology")
    event = adapter.member_events([member])[0]
    for name, value in event.strata.items():
        assert value in tuple(adapter.strata_schema[name]) + ("other",)
    if event.strata:
        assert adapter.unmapped_report(), "an undeclared stratum value went through uncounted"


def test_campus_club_reads_the_strata_the_port_actually_carries():
    adapter = CampusClubAdapter()
    member = SimpleNamespace(id=7, created_at=T0, year=2, branch="CSE")
    event = adapter.member_events([member])[0]
    assert event.strata == {"year": "2", "department": "cse"}


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_registrations_become_rsvp_and_attendance(adapter_class):
    rows = [
        SimpleNamespace(member_id=1, event_id=5, created_at=T0, checked_in=True,
                        checked_in_at=T0 + timedelta(days=3), event=None),
        SimpleNamespace(member_id=2, event_id=5, created_at=T0, checked_in=False,
                        checked_in_at=None,
                        event=SimpleNamespace(ends_at=T0 + timedelta(days=3, hours=2))),
    ]
    kinds = [e.kind for e in adapter_class().participation_events(rows)]
    assert kinds.count("rsvp") == 2
    assert "attend" in kinds and "no_show" in kinds


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_a_no_show_is_not_invented_before_the_event_has_ended(adapter_class):
    """
    Rule C10's principle outside request_flow: before the event ends, the absence
    of a check-in means nothing, and recording it as a no-show invents an outcome.
    """
    row = SimpleNamespace(
        member_id=2, event_id=5, created_at=T0, checked_in=False, checked_in_at=None, event=None
    )
    kinds = [e.kind for e in adapter_class().participation_events([row])]
    assert kinds == ["rsvp"]


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_text_docs_cannot_carry_the_author_forward(adapter_class):
    """
    The identity drop is structural: `TextDoc` has no field a member_ref could go
    in, so this conversion cannot leak an author even by accident.
    """
    adapter = adapter_class()
    signals = adapter.signals([request_row()])
    assert signals[0].member_ref == "m_7"
    docs = adapter.text_docs(signals)
    assert not hasattr(docs[0], "member_ref")
    assert "m_7" not in str(vars(docs[0]))


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_absent_streams_are_declared_empty_not_faked(adapter_class):
    """
    A vertical that supports only some streams declares the rest empty. The
    services that need them then return InsufficientData, which the registry
    turns into "this pack needs the ledger switched on", not an error and not a
    fabricated number.
    """
    adapter = adapter_class()
    assert adapter.ledger_entries([]) == ()
    assert adapter.decisions([]) == ()


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_the_k_anonymity_floor_is_never_below_five(adapter_class):
    """docs/VERTICALS.md rule V1: a manifest may raise it, never lower it."""
    assert adapter_class.k_anonymity_threshold >= 5


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_the_declared_policies_are_the_ones_the_catalog_expects(adapter_class):
    assert adapter_class.reopen_policy in ("new_spell", "extend")
    assert adapter_class.sla_clock in ("wall", "active")


def test_the_two_verticals_declare_the_policies_docs_verticals_specifies():
    # A recurring water complaint is a new event; a resident waiting for water
    # does not care that the vendor was on hold.
    assert RwaSocietyAdapter.reopen_policy == "new_spell"
    assert RwaSocietyAdapter.sla_clock == "wall"
    # An unresolved venue booking is one ongoing problem; a request blocked on
    # the college administration is genuinely paused.
    assert CampusClubAdapter.reopen_policy == "extend"
    assert CampusClubAdapter.sla_clock == "active"


def test_adapters_are_looked_up_by_vertical_id_and_are_not_shared():
    """
    A fresh adapter per call. The unmapped-value counters are per run: two
    tenants computed in the same worker process must not accumulate each other's
    counts into one caveat.
    """
    assert set(ADAPTERS) == {"rwa_society", "campus_club"}
    first = get_adapter("rwa_society")
    first.request_events([request_row(category="NOPE")])
    second = get_adapter("rwa_society")
    assert second.unmapped_report() == {}


@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES, ids=lambda c: c.vertical_id)
def test_the_adapter_emits_the_canonical_types(adapter_class):
    adapter = adapter_class()
    assert all(isinstance(e, RequestEvent) for e in adapter.request_events([request_row()]))
    row = SimpleNamespace(member_id=1, event_id=5, created_at=T0, checked_in=True,
                          checked_in_at=T0, event=None)
    assert all(
        isinstance(e, ParticipationEvent) for e in adapter.participation_events([row])
    )
