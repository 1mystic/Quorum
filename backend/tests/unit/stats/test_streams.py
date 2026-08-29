"""
The six canonical streams, against docs/DATA_SPINE.md.

Most of these assert that a wrong shape cannot be CONSTRUCTED. That is the
spine's method: prevention by type rather than by discipline. A reviewer can
forget a rule; they cannot forget one the shape does not permit breaking.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from app.stats.streams import (
    CENSORING_RULES,
    STREAM_IDS,
    Ballot,
    CountObservation,
    DecisionSpec,
    DueSpell,
    InteractionEdge,
    LedgerEntry,
    OrdinalResponse,
    ParticipationEvent,
    RateObservation,
    RequestEvent,
    RequestSpell,
    StreamWindow,
    TextDoc,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 4, 1, tzinfo=timezone.utc)


def window(**overrides) -> StreamWindow:
    base = dict(start=T0, end=T1, timezone="Asia/Kolkata", complete_through=T1)
    base.update(overrides)
    return StreamWindow(**base)


def spell(**overrides) -> RequestSpell:
    base = dict(
        request_ref="r_1",
        opened_at=T0,
        at_risk_from=T0,
        left_truncated=False,
        duration_hours=48.0,
        duration_active_hours=None,
        event_observed=True,
        outcome="resolved",
        terminal_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        censoring="none",
        interval_lo_hours=None,
        interval_hi_hours=None,
        first_response_hours=2.0,
        paused_hours=0.0,
        reopened_count=0,
        duplicate_count=0,
        category="water_supply",
    )
    base.update(overrides)
    return RequestSpell(**base)


# ---- the window -------------------------------------------------------------


def test_all_six_streams_are_named():
    assert STREAM_IDS == {
        "member_lifecycle",
        "request_flow",
        "ledger",
        "participation",
        "signal",
        "decision",
    }


def test_data_cannot_be_complete_past_the_observation_boundary():
    with pytest.raises(ValueError, match="cannot exceed end"):
        window(complete_through=datetime(2026, 5, 1, tzinfo=timezone.utc))


def test_reporting_lag_is_measurable():
    """
    The gap every periodised service truncates at and discloses. Without it the
    last partial bucket reads as a collapse in collections.
    """
    lagged = window(complete_through=datetime(2026, 3, 25, tzinfo=timezone.utc))
    assert lagged.reporting_lag_days == pytest.approx(7.0)


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        window(start=datetime(2026, 1, 1))


# ---- request_flow and the ten censoring rules ------------------------------


def test_all_ten_censoring_rules_are_carried_in_the_code():
    """
    The rules are normative and services quote them in caveats, so they live
    beside the dataclass rather than only in the document.
    """
    assert sorted(CENSORING_RULES) == ["C1", "C10", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
    assert all(text.strip() for text in CENSORING_RULES.values())


def test_an_open_request_is_censored_not_absent():
    """Rule C1 and C2: it has no terminal event, it counts, and it says how it is censored."""
    open_spell = spell(
        event_observed=False,
        outcome=None,
        terminal_at=None,
        censoring="administrative",
        duration_hours=2160.0,
    )
    assert open_spell.event_observed is False
    assert open_spell.censoring == "administrative"


def test_an_unobserved_event_cannot_claim_to_be_uncensored():
    """Rule C2: censoring='none' is reserved for observed terminals."""
    with pytest.raises(ValueError, match="rules C1, C2"):
        spell(event_observed=False, outcome=None, terminal_at=None, censoring="none")


def test_an_observed_event_cannot_be_missing_its_terminal_timestamp():
    """Rule C10: if it is unknown it is censored. Nothing is inferred."""
    with pytest.raises(ValueError, match="rule C10 forbids inferring one"):
        spell(terminal_at=None)


def test_interval_censoring_must_carry_its_bracket():
    """Rule C4: never impute a midpoint, so the bracket is required to exist."""
    with pytest.raises(ValueError, match="forbids imputing a midpoint"):
        spell(
            event_observed=False,
            outcome=None,
            terminal_at=None,
            censoring="interval",
            interval_lo_hours=None,
            interval_hi_hours=None,
        )


def test_a_bracketed_event_needs_its_upper_bound():
    with pytest.raises(ValueError, match="C4"):
        RequestEvent(
            request_ref="r_1", at=T0, kind="resolved", at_precision="bracketed", at_upper=None
        )


def test_left_truncation_is_carried_not_shifted():
    """Rule C3: the clock is not restarted, the risk set entry moves."""
    truncated = spell(
        opened_at=datetime(2025, 11, 1, tzinfo=timezone.utc),
        at_risk_from=T0,
        left_truncated=True,
    )
    assert truncated.opened_at < truncated.at_risk_from
    assert truncated.left_truncated


def test_the_wall_clock_is_the_default_and_the_active_clock_must_be_asked_for():
    """Rule C8: two legitimate clocks exist and picking one silently is the bug."""
    assert spell().clock_hours == 48.0
    assert spell().duration_active_hours is None


def test_a_spell_is_frozen():
    """A reducer's output cannot be edited downstream into something else."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        spell().duration_hours = 1.0  # type: ignore[misc]


# ---- ledger -----------------------------------------------------------------


def entry(**overrides) -> LedgerEntry:
    base = dict(
        entry_ref="l_1",
        at=T0,
        booked_at=T0,
        amount_minor=250000,
        currency="INR",
        category="maintenance_dues",
        direction="inflow",
        instrument="upi",
        status="settled",
    )
    base.update(overrides)
    return LedgerEntry(**base)


def test_money_is_integer_minor_units():
    """Spine rule S4. Never a float, ever, anywhere."""
    with pytest.raises(ValueError, match="int minor units"):
        entry(amount_minor=2500.0)


def test_direction_and_sign_must_agree():
    with pytest.raises(ValueError, match="inflow with a negative amount"):
        entry(amount_minor=-100)


def test_an_unpaid_due_is_censored_exactly_like_an_open_request():
    """Rule L1: the average days to pay of only the paid dues is the same defect as C1."""
    with pytest.raises(ValueError, match="rule L1"):
        DueSpell(
            due_ref="d_1",
            member_ref="m_1",
            issued_at=T0,
            due_at=T0,
            amount_minor=250000,
            at_risk_from=T0,
            settled_at=None,
            duration_days=90.0,
            event_observed=False,
            censoring="none",
        )


# ---- participation and the exposure log ------------------------------------


def test_a_nudge_without_an_arm_is_not_an_experiment():
    with pytest.raises(ValueError, match="self-selection"):
        ParticipationEvent(member_ref="m_1", at=T0, kind="nudge_sent")


def test_an_arm_on_a_member_action_is_rejected():
    """An arm labels an exposure, which is a system action, not a member action."""
    with pytest.raises(ValueError, match="only meaningful on exposure-log kinds"):
        ParticipationEvent(member_ref="m_1", at=T0, kind="attend", arm_ref="a")


def test_the_exposure_log_records_who_was_offered_a_nudge():
    offered = ParticipationEvent(member_ref="m_1", at=T0, kind="nudge_sent", arm_ref="whatsapp_evening")
    assert offered.arm_ref == "whatsapp_evening"


def test_interaction_edges_are_canonically_ordered():
    with pytest.raises(ValueError, match="canonically ordered"):
        InteractionEdge(a_ref="m_9", b_ref="m_1", weight=1.0, basis="co_attendance")


# ---- signal -----------------------------------------------------------------


def test_a_text_doc_has_nowhere_to_put_an_identity():
    """
    Spine section 5. text.near_duplicate_candidates cannot leak an author because
    it was never handed one, and this is the assertion that keeps it that way.
    """
    fields = {f.name for f in dataclasses.fields(TextDoc)}
    assert "member_ref" not in fields
    assert "respondent_ref" not in fields
    assert "voter_ref" not in fields


def test_an_ordinal_response_cannot_hold_a_mean():
    """Spine rule S7: there is no field in which the mean of a Likert item could live."""
    with pytest.raises(ValueError, match="must be an int"):
        OrdinalResponse(
            response_ref="q_1",
            at=T0,
            item_id="satisfaction",
            scale_min=1,
            scale_max=5,
            value=3.8,
            respondent_ref="m_1",
        )


def test_a_response_outside_its_declared_scale_is_rejected():
    with pytest.raises(ValueError, match="outside its declared scale"):
        OrdinalResponse(
            response_ref="q_1",
            at=T0,
            item_id="satisfaction",
            scale_min=1,
            scale_max=5,
            value=7,
            respondent_ref="m_1",
        )


# ---- decision ---------------------------------------------------------------


def test_a_decision_must_declare_its_rule_before_ballots_are_cast():
    """Rule D1: this is what structurally prevents rule-shopping after the fact."""
    with pytest.raises(ValueError, match="before any ballot is cast"):
        DecisionSpec(
            decision_ref="d_1",
            kind="poll",
            opened_at=T0,
            closed_at=None,
            declared_rule="",
        )


def test_a_ballot_ranking_is_tiers_so_ties_are_expressible():
    ballot = Ballot(
        ballot_ref="b_1",
        decision_ref="d_1",
        voter_ref="v_1",
        cast_at=T0,
        ranking=(("nashville",), ("chattanooga", "knoxville"), ("memphis",)),
    )
    assert ballot.ranking[1] == ("chattanooga", "knoxville")


def test_a_ballot_ranking_an_option_twice_is_invalid():
    with pytest.raises(ValueError, match="never silently repaired"):
        Ballot(
            ballot_ref="b_1",
            decision_ref="d_1",
            voter_ref="v_1",
            cast_at=T0,
            ranking=(("a",), ("a", "b")),
        )


# ---- derived units ----------------------------------------------------------


def test_a_rate_cannot_have_more_successes_than_trials():
    with pytest.raises(ValueError, match="more successes than trials"):
        RateObservation(
            group_ref="vendor_3", successes=4, trials=3, window_start=T0, window_end=T1
        )


def test_the_three_of_three_vendor_is_representable_and_is_not_special_cased():
    """
    The shrinkage services must SEE 3-of-3 in order to shrink it. The spine does
    not filter it out; the mathematics is what refuses to rank it first.
    """
    lucky = RateObservation(
        group_ref="vendor_3", successes=3, trials=3, window_start=T0, window_end=T1
    )
    seasoned = RateObservation(
        group_ref="vendor_1", successes=47, trials=52, window_start=T0, window_end=T1
    )
    assert lucky.successes / lucky.trials > seasoned.successes / seasoned.trials


def test_a_count_observation_needs_exposure():
    """
    A resolver active for two weeks must never be compared against one active for
    a year, which is what an implicit exposure of 1 would do.
    """
    with pytest.raises(ValueError, match="not a rate"):
        CountObservation(group_ref="m_1", events=3, exposure=0.0, window_start=T0, window_end=T1)


# ---- rule S2: no stream carries a tenant id ---------------------------------


def test_no_stream_dataclass_carries_a_tenant_id():
    """
    Spine rule S2. Tenant scoping happened upstream, in the repository. A pure
    function that could see a tenant id could leak one.
    """
    import app.stats.streams as streams

    for name in streams.__all__:
        thing = getattr(streams, name)
        if not dataclasses.is_dataclass(thing):
            continue
        fields = {f.name for f in dataclasses.fields(thing)}
        assert "tenant_id" not in fields, name + " carries a tenant id"
        assert "tenant_ref" not in fields, name + " carries a tenant id"
