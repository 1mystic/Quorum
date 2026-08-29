"""
The Evidence envelope, against docs/EVIDENCE_CONTRACT.md.

The four render states in section 3 are decided by the DATA, never by a
component, so they are tested here rather than in the frontend. The frontend has
its own tests for how each state looks; this file is about which state the data
puts it in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.stats.contracts import (
    CONTRACT_VERSION,
    Check,
    Evidence,
    InsufficientData,
    MethodCard,
    insufficient,
    params_hash,
)

AS_OF = datetime(2026, 8, 29, 4, 15, tzinfo=timezone.utc)


def evidence(**overrides) -> Evidence:
    base = dict(value=4.1, n=187, method="survival.median_resolution_days", as_of=AS_OF)
    base.update(overrides)
    return Evidence(**base)


# ---- the four render states ------------------------------------------------


def test_clean_evidence_renders_as_an_estimate():
    assert evidence().render_state == "estimate"


def test_a_warn_qualifies_the_value_without_hiding_it():
    warned = evidence(
        checks=(
            Check(
                id="censoring-informative",
                label="Open requests are not systematically the hard ones",
                status="WARN",
                statistic=0.31,
                p_value=0.04,
                detail="Requests open past 30 days skew to plumbing. The median may be optimistic.",
            ),
        )
    )
    assert warned.render_state == "qualified"
    assert warned.value == 4.1


def test_a_blocking_fail_makes_the_value_not_interpretable():
    blocked = evidence(
        checks=(
            Check(
                id="proportional-hazards",
                label="Hazards stay proportional over time",
                status="FAIL",
                blocking=True,
                detail="The effect of category reverses around day 14, so one ratio would mislead.",
            ),
        )
    )
    assert blocked.render_state == "not_interpretable"
    assert blocked.blocking_failures


def test_a_non_blocking_fail_is_qualified_not_suppressed():
    """The distinction between read this with care and this is not interpretable."""
    qualified = evidence(
        checks=(Check(id="x", label="x", status="FAIL", blocking=False, detail="read with care"),)
    )
    assert qualified.render_state == "qualified"


def test_not_enough_data_beats_every_other_state():
    """A check on an unestimated value is noise, so the calm empty state wins."""
    empty = insufficient("survival.median_resolution_days", n=11, as_of=AS_OF, unit="days")
    assert empty.render_state == "not_enough_data"
    assert empty.n == 11
    assert empty.value is None


def test_insufficient_data_is_not_an_exception():
    """
    Being below min_n returns an envelope, served as HTTP 200. Honesty must not
    look like an error, or clients learn to treat it as a failure.
    """
    empty = insufficient("survival.km_resolution_curve", n=4, as_of=AS_OF)
    assert isinstance(empty, Evidence)
    assert empty.insufficient_data is True


def test_the_exception_exists_for_the_other_case():
    with pytest.raises(InsufficientData) as raised:
        raise InsufficientData("audit.benford_digits", n=0, min_n=300, reason="no ledger stream")
    assert "no ledger stream" in str(raised.value)
    assert raised.value.min_n == 300


# ---- the guards -------------------------------------------------------------


def test_a_dropped_observation_must_state_why():
    """n_excluded without a reason is exactly the silent drop the contract forbids."""
    with pytest.raises(ValueError, match="must state why"):
        evidence(n_excluded=3)
    ok = evidence(n_excluded=3, exclusion_reason="merged_duplicate")
    assert ok.n_excluded == 3


def test_a_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence(as_of=datetime(2026, 8, 29, 4, 15))


def test_an_interval_without_a_kind_is_rejected():
    with pytest.raises(ValueError, match="interval_kind is 'none'"):
        evidence(interval=(3.2, 5.6))


def test_inverted_interval_bounds_are_rejected():
    with pytest.raises(ValueError, match="inverted"):
        evidence(interval=(5.6, 3.2), interval_kind="greenwood-95")


def test_a_blocking_failure_must_explain_itself():
    """The detail replaces the suppressed value on screen, so it cannot be empty."""
    with pytest.raises(ValueError, match="must say what is shown in its place"):
        Check(id="x", label="x", status="FAIL", blocking=True)


def test_an_unknown_check_status_is_rejected():
    with pytest.raises(ValueError, match="PASS, WARN, FAIL or SKIPPED"):
        Check(id="x", label="x", status="ok")


# ---- n_censored, the field the contract exists for --------------------------


def test_censored_observations_count_in_n_and_are_reported_separately():
    """
    Contract section 6: n counts ALL requests entering the estimate, censored
    ones included, and n_censored says how many. The UI shows it whenever it is
    non-zero, because dropping open requests biases every duration downward.
    """
    censored = evidence(n=187, n_censored=44)
    assert censored.n == 187
    assert censored.n_censored == 44
    assert censored.to_wire()["n_censored"] == 44


# ---- wire format ------------------------------------------------------------


def test_wire_format_drops_nothing():
    wire = evidence(
        interval=(3.2, 5.6),
        interval_kind="greenwood-95",
        unit="days",
        n_censored=44,
        params_hash="e3f1a9c2",
        assumptions=("Censoring is independent of resolution speed",),
    ).to_wire()
    assert set(wire) == {
        "value", "n", "method", "as_of", "interval", "interval_kind", "assumptions",
        "checks", "caveats", "insufficient_data", "n_censored", "n_excluded",
        "exclusion_reason", "unit", "params_hash", "contract_version",
    }
    assert wire["as_of"] == "2026-08-29T04:15:00Z"
    assert wire["interval"] == [3.2, 5.6]
    assert wire["contract_version"] == CONTRACT_VERSION


def test_worst_status_is_the_maximum_over_checks():
    assert evidence().worst_status == "PASS"
    mixed = evidence(
        checks=(
            Check(id="a", label="a", status="PASS"),
            Check(id="b", label="b", status="WARN"),
        )
    )
    assert mixed.worst_status == "WARN"


# ---- params_hash ------------------------------------------------------------


def test_the_same_parameters_hash_identically_regardless_of_key_order():
    a = params_hash("survival.median_resolution_days", 1, {"clock": "wall", "quantile": 0.5})
    b = params_hash("survival.median_resolution_days", 1, {"quantile": 0.5, "clock": "wall"})
    assert a == b


def test_changing_a_parameter_changes_the_hash():
    """The SLA clock changing from wall to active must make two runs incomparable."""
    wall = params_hash("survival.sla_attainment", 1, {"clock": "wall"})
    active = params_hash("survival.sla_attainment", 1, {"clock": "active"})
    assert wall != active


def test_bumping_the_method_version_invalidates_the_cache():
    """
    Contract section 10: when a method's mathematics changes, its version
    changes, which changes params_hash, which invalidates the cache without a
    migration.
    """
    v1 = params_hash("survival.median_resolution_days", 1, {"clock": "wall"})
    v2 = params_hash("survival.median_resolution_days", 2, {"clock": "wall"})
    assert v1 != v2


def test_the_window_is_in_the_hash_but_the_data_is_not():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = params_hash("x.y", 1, {"start": start, "end": start + timedelta(days=90)})
    b = params_hash("x.y", 1, {"start": start, "end": start + timedelta(days=180)})
    assert a != b


def test_the_hash_is_short_and_stable_across_runs():
    first = params_hash("x.y", 1, {"k": 5})
    assert len(first) == 8
    assert first == params_hash("x.y", 1, {"k": 5})


# ---- method cards -----------------------------------------------------------


def test_a_method_card_serializes_its_known_answer():
    card = MethodCard(
        id="x.y",
        name="X",
        one_liner="What it answers.",
        assumes=("a",),
        wrong_when=("b",),
        min_n=10,
        interval_meaning="c",
        references=("d",),
        known_answer="e",
    )
    assert card.to_wire()["known_answer"] == "e"
