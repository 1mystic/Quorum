"""
Card C.15. The `participation` and `decision` stream adapters' conformance,
same discipline as `test_ledger_adapter.py`: plain `SimpleNamespace`
fixtures, no ORM, no database.

Proves the two TODOs `app/verticals/adapters/base.py` named are genuinely
closed: the exposure log (`nudge_sent`/`nudge_delivered`/`nudge_opened`/
`nudge_acted` with `arm_ref`) now has a real row to read, and
`Decision`/`DecisionOption`/`Ballot` now back `decisions`/`decision_options`/
`ballots` instead of the empty tuple the class docstring used to return.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.verticals.adapters import CampusClubAdapter, RwaSocietyAdapter

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

ADAPTER_CLASSES = [RwaSocietyAdapter, CampusClubAdapter]


def participation_row(**overrides):
    base = dict(
        id=1, member_id=7, at=T0, kind=SimpleNamespace(value="attend"),
        object_type="event", object_id=3, group_id=None, weight=1.0,
        channel=None, arm_ref=None, strata={},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def decision_row(**overrides):
    base = dict(
        id=1, group_id=None, kind=SimpleNamespace(value="poll"),
        declared_rule="schulze", seats=1, quorum_rule=None, budget_minor=None,
        ballot_style=SimpleNamespace(value="ranked"),
        opened_at=T0, closed_at=None,
        eligible_strata=[{"strata": {"block": "a"}, "count": 12}],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def option_row(**overrides):
    base = dict(id=1, decision_id=1, label="Repaint lobby", cost_minor=None,
                tags=[], proposer_id=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def ballot_row(**overrides):
    base = dict(
        id=1, decision_id=1, voter_id=7, cast_at=T0 + timedelta(hours=1),
        ranking=[[1, 2]], approvals=[], scores={}, allocation={}, channel="app",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---- participation / exposure log -----------------------------------------

@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_a_nudge_sent_event_carries_its_arm_ref(adapter_class):
    row = participation_row(
        kind=SimpleNamespace(value="nudge_sent"), object_type="campaign", object_id=9,
        channel="whatsapp", arm_ref="reminder_v2",
    )
    events = adapter_class().participation_events([row])
    assert len(events) == 1
    event = events[0]
    assert event.kind == "nudge_sent"
    assert event.arm_ref == "reminder_v2"
    assert event.channel == "whatsapp"
    assert event.member_ref == "m_7"


def test_a_non_exposure_event_never_carries_an_arm_ref():
    row = participation_row(kind=SimpleNamespace(value="attend"))
    events = RwaSocietyAdapter().participation_events([row])
    assert events[0].arm_ref is None


def test_an_exposure_event_with_no_arm_ref_is_rejected_by_the_atom():
    """
    The adapter does not validate this itself (the service layer already
    refused to write such a row); `ParticipationEvent.__post_init__` is the
    second line, not the only one, and this proves it actually fires from the
    adapter's own construction path.
    """
    row = participation_row(kind=SimpleNamespace(value="nudge_acted"), arm_ref=None)
    with pytest.raises(ValueError):
        RwaSocietyAdapter().participation_events([row])


def test_event_registration_and_exposure_log_rows_coexist():
    """The adapter obligation that nothing is filtered: old and new sources both come through."""
    registration = SimpleNamespace(
        id=1, member_id=7, event_id=5, checked_in=True,
        checked_in_at=T0, created_at=T0 - timedelta(hours=1), event=None,
    )
    nudge = participation_row(kind=SimpleNamespace(value="nudge_sent"), arm_ref="a1")
    events = RwaSocietyAdapter().participation_events([registration, nudge])
    kinds = {e.kind for e in events}
    assert "rsvp" in kinds and "attend" in kinds and "nudge_sent" in kinds


def test_object_ref_is_built_from_object_type_and_object_id():
    row = participation_row(object_type="event", object_id=42)
    events = RwaSocietyAdapter().participation_events([row])
    assert events[0].object_ref == "e_42"
    assert events[0].object_kind == "event"


# ---- decision ---------------------------------------------------------

@pytest.mark.parametrize("adapter_class", ADAPTER_CLASSES)
def test_a_decision_spec_carries_its_declared_rule(adapter_class):
    specs = adapter_class().decisions([decision_row()])
    assert len(specs) == 1
    spec = specs[0]
    assert spec.declared_rule == "schulze"
    assert spec.decision_ref == "dec_1"
    assert spec.kind == "poll"
    assert spec.ballot_style == "ranked"


def test_eligible_strata_is_frozen_into_a_stratum_key_tuple():
    specs = RwaSocietyAdapter().decisions([decision_row()])
    assert specs[0].eligible_strata == {("a",): 12}


def test_decision_options_carry_cost_for_budget_allocation():
    options = RwaSocietyAdapter().decision_options([
        option_row(id=1, decision_id=1, label="New pump", cost_minor=500000),
    ])
    assert len(options) == 1
    assert options[0].option_ref == "opt_1"
    assert options[0].decision_ref == "dec_1"
    assert options[0].cost_minor == 500000


def test_a_ranked_ballot_maps_member_ids_to_option_refs():
    ballots = RwaSocietyAdapter().ballots([ballot_row(ranking=[[1, 2], [3]])])
    assert len(ballots) == 1
    ballot = ballots[0]
    assert ballot.decision_ref == "dec_1"
    assert ballot.voter_ref == "m_7"
    assert ballot.ranking == (("opt_1", "opt_2"), ("opt_3",))


def test_a_score_ballot_re_keys_json_string_option_ids_to_option_refs():
    ballots = RwaSocietyAdapter().ballots([
        ballot_row(ranking=[], scores={"1": 5, "2": 3}),
    ])
    assert ballots[0].scores == {"opt_1": 5, "opt_2": 3}


def test_an_allocation_ballot_re_keys_json_string_option_ids_to_minor_units():
    ballots = RwaSocietyAdapter().ballots([
        ballot_row(ranking=[], allocation={"1": 200000, "2": 300000}),
    ])
    assert ballots[0].allocation == {"opt_1": 200000, "opt_2": 300000}


def test_decisions_options_and_ballots_all_come_through_together():
    """The adapter obligation that nothing is filtered, same as the ledger suite's mixed-rows test."""
    specs = RwaSocietyAdapter().decisions([decision_row()])
    options = RwaSocietyAdapter().decision_options([option_row(id=1), option_row(id=2, label="Repave lot")])
    ballots = RwaSocietyAdapter().ballots([ballot_row(ranking=[[1], [2]])])
    assert len(specs) == 1
    assert {o.option_ref for o in options} == {"opt_1", "opt_2"}
    assert ballots[0].ranking == (("opt_1",), ("opt_2",))
