"""
The reducer, checked against the rules it implements and against the pure
functions it feeds.

Two of these tests matter more than the rest.

`test_the_censoring_regression_survives_the_reducer` rebuilds the exact fixture
`tests/unit/stats/test_survival.py::test_the_censoring_regression` uses, but
from raw `RequestEvent` atoms rather than from hand-written `RequestSpell`s, and
asserts the same three numbers come out: n=100, n_censored=49, and a
Kaplan-Meier median of 8.0 days against a naive mean-of-closed of 3.1. A
survival function that censors correctly is worth nothing if the reducer feeding
it has already dropped the open rows, so the seam is what is being tested, not
either half.

`test_the_materializer_known_answer_needs_no_monkeypatch` reproduces the fixture
`tests/unit/services/test_insight_materializer.py` had to monkeypatch a toy
reducer to obtain (35 requests resolved at exactly 8 days, 5 still open),
against the real reducer, and asserts the same n=40 / n_censored=5 / value=8.0.

Every other test names the rule from `docs/DATA_SPINE.md` section 2 that it
covers, C1 to C10, so the file can be read against the document.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.stats import survival as sv
from app.stats.streams import reduce as R
from app.stats.streams.decision import Ballot, DecisionSpec
from app.stats.streams.ledger import LedgerEntry
from app.stats.streams.member import MemberEvent
from app.stats.streams.participation import ParticipationEvent
from app.stats.streams.request import RequestEvent
from app.stats.streams.window import StreamWindow
from tests.unit.stats import datasets as ds
from app.verticals.adapters import RwaSocietyAdapter

EPOCH = ds.EPOCH
DAY = timedelta(days=1)
HOUR = timedelta(hours=1)


def window(days: float = 60.0, *, lag_days: float = 0.0, tz: str = "UTC") -> StreamWindow:
    end = EPOCH + timedelta(days=days)
    return StreamWindow(
        start=EPOCH, end=end, timezone=tz, complete_through=end - timedelta(days=lag_days)
    )


def opened(ref: str, at: datetime, **kw) -> RequestEvent:
    kw.setdefault("category", "water_supply")
    kw.setdefault("actor_ref", "m_resident")
    return RequestEvent(request_ref=ref, at=at, kind="opened", **kw)


def event(ref: str, at: datetime, kind: str, **kw) -> RequestEvent:
    return RequestEvent(request_ref=ref, at=at, kind=kind, **kw)


# ---------------------------------------------------------------------------
# The censoring regression, through the reducer this time.
# ---------------------------------------------------------------------------


def censoring_atoms() -> tuple[tuple[RequestEvent, ...], StreamWindow]:
    """
    The `test_survival.py::censoring_fixture` population, expressed as atoms.

    51 closed requests whose durations average to exactly 3.1 days, and 49 still
    open with ages 9.0 to 33.0 days, which is what makes the two figures
    disagree: nothing is censored before day 8, so the Kaplan-Meier curve
    telescopes and S(8) = 49/100.

    The open ones are opened at `window.end - age` so that their censoring time
    is their age, exactly as the hand-written fixture asserts.
    """
    w = window(60.0)
    closed = [1.0] * 17 + [1.1] + [2.0] * 10 + [3.0] * 8 + [5.0] * 8 + [8.0] * 7
    atoms: list[RequestEvent] = []
    for i, days in enumerate(closed):
        ref = "closed-" + str(i)
        atoms.append(opened(ref, EPOCH))
        atoms.append(event(ref, EPOCH + timedelta(days=days), "resolved", actor_ref="m_plumber"))
    for i in range(49):
        age = 9.0 + 0.5 * i
        atoms.append(opened("open-" + str(i), w.end - timedelta(days=age)))
    return tuple(atoms), w


def test_the_censoring_regression_survives_the_reducer():
    """
    The seam. Atoms in, spells out, and the published-answer figures unchanged.

    If `request_spells` filtered on a terminal timestamp anywhere, or measured an
    open request's clock to its last event instead of to the boundary, this test
    would report 3.1 days like every other community dashboard does.
    """
    atoms, w = censoring_atoms()
    spells = R.request_spells(atoms, w)

    assert len(spells) == 100
    assert sum(1 for s in spells if s.event_observed) == 51
    assert sum(1 for s in spells if not s.event_observed) == 49
    assert {s.censoring for s in spells} == {"none", "administrative"}

    gap = sv.naive_vs_km_gap(list(spells), w)
    assert gap.value["naive_mean_closed_days"] == pytest.approx(3.1, abs=1e-9)
    assert gap.value["km_median_days"] == pytest.approx(8.0, abs=1e-9)
    assert gap.value["gap_days"] == pytest.approx(4.9, abs=1e-9)
    assert gap.n == 100
    assert gap.n_censored == 49

    median = sv.median_resolution_days(list(spells), w)
    assert median.value == pytest.approx(8.0, abs=1e-9)
    assert median.n == 100 and median.n_censored == 49

    curve = sv.km_resolution_curve(list(spells), w)
    assert sv._curve_value_at(curve.value, "survival", 8.0) == pytest.approx(0.49, abs=1e-9)


def test_the_reduced_spells_match_the_hand_written_fixture_field_for_field():
    """
    The reducer and `datasets.spell` must agree, or the known-answer suite is
    testing a shape the reducer never produces.
    """
    atoms, w = censoring_atoms()
    reduced = {s.request_ref: s for s in R.request_spells(atoms, w)}

    closed = [1.0] * 17 + [1.1] + [2.0] * 10 + [3.0] * 8 + [5.0] * 8 + [8.0] * 7
    expected = [ds.spell("closed-" + str(i), days=d, observed=True) for i, d in enumerate(closed)]
    expected += [
        ds.spell("open-" + str(i), days=9.0 + 0.5 * i, observed=False) for i in range(49)
    ]
    for want in expected:
        got = reduced[want.request_ref]
        assert got.duration_hours == pytest.approx(want.duration_hours, abs=1e-6)
        assert got.event_observed is want.event_observed
        assert got.censoring == want.censoring
        assert got.outcome == want.outcome
        assert got.left_truncated is want.left_truncated
        assert (got.terminal_at is None) is (want.terminal_at is None)


def test_the_materializer_known_answer_needs_no_monkeypatch():
    """
    `tests/unit/services/test_insight_materializer.py` had to substitute a toy
    reducer to get a real number out of the worker, because this function
    raised. Its hand-checked answer was n=40, n_censored=5, median 8.0 days.
    The real reducer produces the same three numbers on the same atoms, so the
    substitution is no longer load-bearing.
    """
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    w = StreamWindow(
        start=now - timedelta(days=200), end=now, timezone="Asia/Kolkata", complete_through=now
    )
    atoms: list[RequestEvent] = []
    at = now - timedelta(days=100)
    for i in range(35):
        atoms.append(opened("r_" + str(i), at))
        atoms.append(event("r_" + str(i), at + timedelta(days=8), "resolved"))
    for i in range(35, 40):
        atoms.append(opened("r_" + str(i), now - timedelta(days=3)))

    spells = R.request_spells(tuple(atoms), w, reopen_policy="new_spell")
    evidence = sv.median_resolution_days(list(spells), w)

    assert evidence.insufficient_data is False
    assert evidence.n == 40
    assert evidence.n_censored == 5
    assert evidence.value == pytest.approx(8.0, abs=1e-6)


# ---------------------------------------------------------------------------
# The rules, one at a time. docs/DATA_SPINE.md section 2, C1 to C10.
# ---------------------------------------------------------------------------


def test_c1_every_request_opened_before_the_boundary_enters_the_risk_set():
    w = window(10.0)
    atoms = (
        opened("a", EPOCH),
        event("a", EPOCH + 2 * DAY, "resolved"),
        opened("b", EPOCH + DAY),
        opened("c", EPOCH + 5 * DAY),
    )
    spells = R.request_spells(atoms, w)
    assert {s.request_ref for s in spells} == {"a", "b", "c"}


def test_c1_a_request_opened_after_the_boundary_is_not_yet_a_spell():
    w = window(10.0)
    spells = R.request_spells((opened("late", EPOCH + 11 * DAY),), w)
    assert spells == ()


def test_c2_an_open_request_is_censored_at_the_boundary_and_counted():
    w = window(10.0)
    spell = R.request_spells((opened("b", EPOCH + DAY), event("b", EPOCH + 2 * DAY, "comment")), w)[0]
    assert spell.event_observed is False
    assert spell.censoring == "administrative"
    assert spell.terminal_at is None
    assert spell.duration_hours == pytest.approx(9 * 24.0)


def test_c3_a_request_older_than_the_window_is_left_truncated_not_shifted():
    """
    The clock runs from `at_risk_from`, and the age it already had is recoverable
    as `at_risk_from - opened_at`, which is exactly what `survival._entry_days`
    reads to build the delayed-entry risk set.
    """
    w = window(10.0)
    atoms = (opened("old", EPOCH - 4 * DAY), event("old", EPOCH + 3 * DAY, "resolved"))
    spell = R.request_spells(atoms, w)[0]
    assert spell.left_truncated is True
    assert spell.at_risk_from == w.start
    assert spell.opened_at == EPOCH - 4 * DAY
    assert spell.duration_hours == pytest.approx(3 * 24.0)
    assert sv._entry_days(spell) == pytest.approx(4.0)
    # entry + duration is the true age at resolution: 7 days, not 3 and not 11.
    assert sv._entry_days(spell) + spell.duration_hours / 24.0 == pytest.approx(7.0)


def test_c3_a_request_that_closed_before_the_window_contributes_nothing():
    w = window(10.0)
    atoms = (opened("gone", EPOCH - 10 * DAY), event("gone", EPOCH - 5 * DAY, "resolved"))
    assert R.request_spells(atoms, w) == ()


def test_c4_a_bracketed_terminal_is_interval_censored_and_no_midpoint_is_invented():
    w = window(30.0)
    atoms = (
        opened("batch", EPOCH),
        RequestEvent(
            request_ref="batch", at=EPOCH + 4 * DAY, kind="resolved",
            at_precision="bracketed", at_upper=EPOCH + 10 * DAY,
        ),
    )
    spell = R.request_spells(atoms, w)[0]
    assert spell.censoring == "interval"
    assert spell.terminal_at is None, "rule C10: an unknown timestamp is not carried forward"
    assert spell.interval_lo_hours == pytest.approx(4 * 24.0)
    assert spell.interval_hi_hours == pytest.approx(10 * 24.0)
    midpoint = 7 * 24.0
    assert spell.duration_hours != pytest.approx(midpoint)
    assert spell.duration_hours == pytest.approx(4 * 24.0)


def test_c5_competing_outcomes_are_recorded_as_causes_not_hidden_as_censoring():
    """
    The reducer does not know which cause is under analysis, so it records the
    cause and leaves `censoring="none"`. `survival._check_competing_risks` reads
    `outcome`, and this is the input that makes it fire.
    """
    w = window(30.0)
    atoms: list[RequestEvent] = []
    for i in range(30):
        atoms += [opened("r%d" % i, EPOCH), event("r%d" % i, EPOCH + 2 * DAY, "resolved")]
    for i in range(30, 40):
        atoms += [opened("r%d" % i, EPOCH), event("r%d" % i, EPOCH + DAY, "withdrawn")]
    spells = R.request_spells(tuple(atoms), w)

    assert sum(1 for s in spells if s.outcome == "withdrawn") == 10
    assert all(s.censoring == "none" for s in spells if s.event_observed)

    rows, _, _ = sv._request_rows(spells)
    check = sv._check_competing_risks(rows)
    assert check.status == "FAIL" and check.blocking is True
    assert check.statistic == pytest.approx(0.25)


def test_c6_reopen_policy_is_a_declared_parameter_and_changes_the_answer():
    w = window(30.0)
    atoms = (
        opened("r", EPOCH),
        event("r", EPOCH + 2 * DAY, "resolved"),
        event("r", EPOCH + 5 * DAY, "reopened"),
        event("r", EPOCH + 9 * DAY, "resolved"),
    )
    split = R.request_spells(atoms, w, reopen_policy="new_spell")
    assert [s.request_ref for s in split] == ["r", "r#2"]
    assert [s.duration_hours for s in split] == [pytest.approx(48.0), pytest.approx(96.0)]
    assert split[1].parent_ref == "r"
    assert all(s.reopened_count == 0 for s in split)

    extended = R.request_spells(atoms, w, reopen_policy="extend")
    assert len(extended) == 1
    assert extended[0].reopened_count == 1
    assert extended[0].duration_hours == pytest.approx(9 * 24.0), (
        "under 'extend' the request did not end when it was first closed, because it was "
        "reopened; the spell runs to the terminal that stuck"
    )
    assert extended[0].terminal_at == EPOCH + 9 * DAY


def test_c6_extend_leaves_a_reopened_request_open_if_it_was_never_closed_again():
    w = window(30.0)
    atoms = (
        opened("r", EPOCH),
        event("r", EPOCH + 2 * DAY, "resolved"),
        event("r", EPOCH + 5 * DAY, "reopened"),
    )
    spell = R.request_spells(atoms, w, reopen_policy="extend")[0]
    assert spell.event_observed is False
    assert spell.terminal_at is None
    assert spell.duration_hours == pytest.approx(30 * 24.0)


def test_c6_an_unknown_reopen_policy_is_refused():
    with pytest.raises(ValueError, match="reopen_policy"):
        R.request_spells((opened("r", EPOCH),), window(10.0), reopen_policy="whatever")


def test_c7_a_merged_duplicate_is_emitted_and_the_survivor_counts_it():
    """
    Emitted, not dropped: the estimator excludes it and reports `n_excluded`.
    Dropping it here would make the exclusion invisible, which is
    indistinguishable from having lost the row.
    """
    w = window(30.0)
    atoms = (
        opened("keep", EPOCH),
        opened("dupe", EPOCH + HOUR),
        event("dupe", EPOCH + 2 * DAY, "merged", parent_ref="keep"),
        event("keep", EPOCH + 4 * DAY, "resolved"),
    )
    spells = {s.request_ref: s for s in R.request_spells(atoms, w)}
    assert spells["dupe"].outcome == "merged"
    assert spells["keep"].duplicate_count == 1
    assert spells["dupe"].duplicate_count == 0

    rows, excluded, _ = sv._request_rows(list(spells.values()))
    assert excluded == 1 and len(rows) == 1


def test_c8_paused_time_is_measured_and_only_the_declared_clock_is_filled():
    w = window(30.0)
    atoms = (
        opened("r", EPOCH),
        event("r", EPOCH + DAY, "paused"),
        event("r", EPOCH + 3 * DAY, "resumed"),
        event("r", EPOCH + 6 * DAY, "resolved"),
    )
    wall = R.request_spells(atoms, w)[0]
    assert wall.duration_hours == pytest.approx(6 * 24.0)
    assert wall.paused_hours == pytest.approx(2 * 24.0)
    assert wall.duration_active_hours is None, (
        "rule C8: the active clock exists only where the vertical declares it"
    )

    active = R.request_spells(atoms, w, sla_clock="active")[0]
    assert active.duration_hours == pytest.approx(6 * 24.0)
    assert active.duration_active_hours == pytest.approx(4 * 24.0)


def test_c8_an_unclosed_pause_runs_to_the_end_of_observation():
    w = window(10.0)
    atoms = (opened("r", EPOCH), event("r", EPOCH + 2 * DAY, "paused"))
    spell = R.request_spells(atoms, w, sla_clock="active")[0]
    assert spell.paused_hours == pytest.approx(8 * 24.0)
    assert spell.duration_active_hours == pytest.approx(2 * 24.0)


def test_c9_covariates_reach_the_censoring_informative_check():
    w = window(30.0)
    atoms = (
        opened("r", EPOCH, attributes={"block": "C"}, priority="high", location_ref="tower_2"),
        event("r", EPOCH + DAY, "resolved"),
    )
    spell = R.request_spells(atoms, w)[0]
    assert spell.covariates == {"block": "C"}
    keys = sv._spell_keys(spell)
    assert keys["block"] == "C" and keys["priority"] == "high"
    assert keys["location_ref"] == "tower_2"


def test_c10_a_terminal_after_the_boundary_is_not_carried_back():
    """
    The request resolved, but after `window.end`. At the boundary it was open,
    and that is what the window says. Nothing is carried forward or backward.
    """
    w = window(10.0)
    atoms = (opened("r", EPOCH), event("r", EPOCH + 20 * DAY, "resolved"))
    spell = R.request_spells(atoms, w)[0]
    assert spell.event_observed is False
    assert spell.terminal_at is None
    assert spell.outcome is None
    assert spell.duration_hours == pytest.approx(10 * 24.0)


def test_a_request_with_no_opened_atom_is_refused_rather_than_guessed():
    w = window(10.0)
    with pytest.raises(ValueError, match="no 'opened' atom"):
        R.request_spells((event("r", EPOCH + DAY, "resolved"),), w)


def test_first_response_is_the_first_reply_by_someone_other_than_the_author():
    w = window(10.0)
    atoms = (
        opened("r", EPOCH, actor_ref="m_1"),
        event("r", EPOCH + HOUR, "comment", actor_ref="m_1"),
        event("r", EPOCH + 5 * HOUR, "comment", actor_ref="m_2"),
        event("r", EPOCH + 2 * DAY, "resolved", actor_ref="m_2"),
    )
    spell = R.request_spells(atoms, w)[0]
    assert spell.first_response_hours == pytest.approx(5.0)


def test_a_request_nobody_answered_has_no_first_response():
    w = window(10.0)
    spell = R.request_spells((opened("r", EPOCH, actor_ref="m_1"),), w)[0]
    assert spell.first_response_hours is None


def test_assignment_history_is_summarised_on_the_spell():
    w = window(10.0)
    atoms = (
        opened("r", EPOCH),
        event("r", EPOCH + HOUR, "assigned", assignee_ref="m_a"),
        event("r", EPOCH + 2 * HOUR, "reassigned", assignee_ref="m_b"),
        event("r", EPOCH + 3 * HOUR, "reassigned", assignee_ref="m_c"),
        event("r", EPOCH + DAY, "resolved", assignee_ref="m_c"),
    )
    spell = R.request_spells(atoms, w)[0]
    assert spell.assignee_ref == "m_c"
    assert spell.n_reassignments == 2


def test_lost_censoring_is_off_unless_declared():
    w = window(100.0)
    atoms = (opened("r", EPOCH), event("r", EPOCH + DAY, "comment", actor_ref="m_2"))
    default = R.request_spells(atoms, w)[0]
    assert default.censoring == "administrative"
    assert default.duration_hours == pytest.approx(100 * 24.0)

    declared = R.request_spells(atoms, w, lost_after_days=30.0)[0]
    assert declared.censoring == "lost"
    assert declared.duration_hours == pytest.approx(24.0)


def test_the_reducer_is_deterministic():
    atoms, w = censoring_atoms()
    first = R.request_spells(atoms, w)
    second = R.request_spells(tuple(reversed(atoms)), w)
    assert first == second


# ---------------------------------------------------------------------------
# The adapter seam: real adapter rows, through the reducer, into a statistic.
# ---------------------------------------------------------------------------


def _row(**overrides):
    base = dict(
        id=1, member_id=7, group_id=3, category="water_supply", priority=None,
        channel=None, location_ref=None, subcategory=None,
        responded_by=None, responded_at=None, resolved_at=None, created_at=EPOCH,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_open_rows_survive_the_adapter_and_the_reducer_together():
    """
    Conformance obligation 7 and rule C1 are the same defect at two layers. This
    checks both at once: three open rows and one resolved, and all four must
    still be there when a statistic is computed.
    """
    adapter = RwaSocietyAdapter()
    rows = [
        _row(id=1), _row(id=2), _row(id=3),
        _row(id=4, resolved_at=EPOCH + 2 * DAY, responded_by=9,
             responded_at=EPOCH + 2 * HOUR),
    ]
    spells = R.request_spells(adapter.request_events(rows), window(30.0))
    assert len(spells) == 4
    assert sum(1 for s in spells if s.event_observed) == 1
    assert sum(1 for s in spells if s.censoring == "administrative") == 3
    resolved = next(s for s in spells if s.event_observed)
    assert resolved.duration_hours == pytest.approx(48.0)
    assert resolved.first_response_hours == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# flow_periods
# ---------------------------------------------------------------------------


def test_flow_periods_count_arrivals_terminals_and_backlog():
    w = StreamWindow(
        start=EPOCH, end=EPOCH + 28 * DAY, timezone="UTC", complete_through=EPOCH + 28 * DAY
    )
    atoms: list[RequestEvent] = []
    for i in range(5):
        atoms.append(opened("w1-%d" % i, EPOCH + timedelta(days=1, hours=i)))
    for i in range(3):
        atoms.append(event("w1-%d" % i, EPOCH + timedelta(days=3), "resolved"))
    for i in range(2):
        atoms.append(opened("w2-%d" % i, EPOCH + timedelta(days=8)))

    periods = R.flow_periods(tuple(atoms), w, period="week")
    assert [p.arrivals for p in periods] == [5, 2, 0, 0]
    assert [p.terminals for p in periods] == [3, 0, 0, 0]
    assert [p.resolutions for p in periods] == [3, 0, 0, 0]
    assert [p.backlog_end for p in periods] == [2, 4, 4, 4]
    assert [p.backlog_start for p in periods] == [0, 2, 4, 4]
    assert all(p.exposure_days == pytest.approx(7.0) for p in periods)
    assert periods[0].arrival_rate_per_day == pytest.approx(5 / 7)


def test_flow_periods_mark_the_incomplete_buckets_rather_than_dropping_them():
    """
    A bucket the window only partly covers, or that reaches past
    `complete_through`, is emitted with `complete=False`. `series.period_series`
    is what excludes it, and it reports how many it excluded.
    """
    w = StreamWindow(
        start=EPOCH + 3 * DAY, end=EPOCH + 25 * DAY, timezone="UTC",
        complete_through=EPOCH + 18 * DAY,
    )
    periods = R.flow_periods((opened("r", EPOCH + 4 * DAY),), w, period="week")
    assert periods[0].complete is False, "the first bucket is only partly inside the window"
    assert periods[-1].complete is False, "the last bucket runs past complete_through"
    assert any(p.complete for p in periods)
    assert periods[0].exposure_days == pytest.approx(4.0)


def test_flow_periods_do_not_count_a_merged_duplicate_as_demand():
    w = StreamWindow(
        start=EPOCH, end=EPOCH + 7 * DAY, timezone="UTC", complete_through=EPOCH + 7 * DAY
    )
    atoms = (
        opened("keep", EPOCH + DAY),
        opened("dupe", EPOCH + DAY),
        event("dupe", EPOCH + 2 * DAY, "merged", parent_ref="keep"),
    )
    period = R.flow_periods(atoms, w, period="week")[0]
    assert period.arrivals == 1
    assert period.terminals == 0


def test_flow_periods_take_the_declared_server_count():
    w = StreamWindow(
        start=EPOCH, end=EPOCH + 7 * DAY, timezone="UTC", complete_through=EPOCH + 7 * DAY
    )
    atoms = (
        opened("r", EPOCH + DAY, actor_ref="m_1"),
        event("r", EPOCH + 2 * DAY, "assigned", actor_ref="m_2", assignee_ref="m_3"),
    )
    default = R.flow_periods(atoms, w, period="week")[0]
    assert default.active_servers == pytest.approx(3.0)

    declared = R.flow_periods(
        atoms, w, period="week", active_servers_by_period={EPOCH: 0.6}
    )[0]
    assert declared.active_servers == pytest.approx(0.6)


def test_period_bounds_bucket_in_the_windows_own_timezone():
    """
    Spine rule S1: local calendar bucketing uses `StreamWindow.timezone` and
    nothing else. Asia/Kolkata is UTC+5:30, so a local day starts at 18:30 UTC
    the evening before.
    """
    w = StreamWindow(
        start=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end=datetime(2026, 3, 5, tzinfo=timezone.utc),
        timezone="Asia/Kolkata",
        complete_through=datetime(2026, 3, 5, tzinfo=timezone.utc),
    )
    bounds = R.period_bounds(w, "day")
    assert bounds[0][0] == datetime(2026, 2, 28, 18, 30, tzinfo=timezone.utc)
    assert all((b - a) == DAY for a, b in bounds)

    utc_window = StreamWindow(
        start=w.start, end=w.end, timezone="UTC", complete_through=w.end
    )
    assert R.period_bounds(utc_window, "day")[0][0] == datetime(2026, 3, 1, tzinfo=timezone.utc)


def test_month_buckets_are_calendar_months_not_thirty_day_blocks():
    w = StreamWindow(
        start=datetime(2026, 1, 15, tzinfo=timezone.utc),
        end=datetime(2026, 4, 2, tzinfo=timezone.utc),
        timezone="UTC",
        complete_through=datetime(2026, 4, 2, tzinfo=timezone.utc),
    )
    starts = [start for start, _ in R.period_bounds(w, "month")]
    assert starts == [
        datetime(2026, m, 1, tzinfo=timezone.utc) for m in (1, 2, 3, 4)
    ]


def test_an_unknown_period_is_refused():
    with pytest.raises(ValueError, match="period must be one of"):
        R.period_bounds(window(10.0), "fortnight")


# ---------------------------------------------------------------------------
# ledger
# ---------------------------------------------------------------------------


def due(ref: str, *, due_at: datetime, settled_at=None, status="expected", amount=500000, **kw):
    return LedgerEntry(
        entry_ref=ref, at=due_at - 10 * DAY, booked_at=due_at - 10 * DAY,
        amount_minor=amount, currency="INR", category="maintenance_dues",
        direction="inflow", instrument="adjustment", status=status,
        member_ref="m_1", due_at=due_at, settled_at=settled_at, **kw
    )


def test_l1_an_unpaid_due_is_right_censored_exactly_like_an_open_request():
    w = window(60.0)
    entries = (
        due("d1", due_at=EPOCH + 10 * DAY, settled_at=EPOCH + 14 * DAY, status="settled"),
        due("d2", due_at=EPOCH + 10 * DAY),
    )
    spells = {s.due_ref: s for s in R.due_spells(entries, w)}
    assert spells["d1"].event_observed is True
    assert spells["d1"].censoring == "none"
    assert spells["d1"].duration_days == pytest.approx(4.0)
    assert spells["d2"].event_observed is False
    assert spells["d2"].censoring == "administrative"
    assert spells["d2"].duration_days == pytest.approx(50.0)


def test_a_due_paid_early_has_a_negative_duration_and_that_is_the_truth():
    w = window(60.0)
    entry = due("d", due_at=EPOCH + 20 * DAY, settled_at=EPOCH + 17 * DAY, status="settled")
    assert R.due_spells((entry,), w)[0].duration_days == pytest.approx(-3.0)


def test_a_written_off_due_is_a_competing_risk_not_neutral_censoring():
    w = window(60.0)
    entry = due("d", due_at=EPOCH + 10 * DAY, status="written_off")
    spell = R.due_spells((entry,), w)[0]
    assert spell.event_observed is False
    assert spell.censoring == "competing", (
        "a written-off due will never be settled; censoring it neutrally says it still might"
    )


def test_a_due_that_has_not_come_due_yet_has_no_exposure():
    w = window(10.0)
    assert R.due_spells((due("d", due_at=EPOCH + 30 * DAY),), w) == ()


def test_l2_expected_entries_are_receivables_not_inflow():
    w = StreamWindow(
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 3, 1, tzinfo=timezone.utc),
        timezone="UTC", complete_through=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    jan = datetime(2026, 1, 10, tzinfo=timezone.utc)
    entries = (
        LedgerEntry(entry_ref="p1", at=jan, booked_at=jan, amount_minor=300000, currency="INR",
                    category="maintenance_dues", direction="inflow", instrument="upi",
                    status="settled"),
        LedgerEntry(entry_ref="d1", at=jan, booked_at=jan, amount_minor=500000, currency="INR",
                    category="maintenance_dues", direction="inflow", instrument="adjustment",
                    status="expected", due_at=jan + 20 * DAY),
        LedgerEntry(entry_ref="e1", at=jan, booked_at=jan, amount_minor=-120000, currency="INR",
                    category="stp_maintenance", direction="outflow", instrument="bank_transfer",
                    status="settled"),
    )
    periods = R.ledger_periods(entries, w, period="month")
    assert len(periods) == 2
    assert periods[0].inflow_minor == 300000
    assert periods[0].outflow_minor == -120000
    assert periods[0].net_minor == 180000
    assert periods[0].by_category["expected"] == 500000, (
        "the receivable is carried separately, which is where montecarlo reads it"
    )
    assert periods[0].closing_balance_minor is None


def test_a_closing_balance_appears_only_when_an_opening_balance_is_supplied():
    w = StreamWindow(
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 3, 1, tzinfo=timezone.utc),
        timezone="UTC", complete_through=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    jan = datetime(2026, 1, 10, tzinfo=timezone.utc)
    entries = (
        LedgerEntry(entry_ref="p1", at=jan, booked_at=jan, amount_minor=300000, currency="INR",
                    category="maintenance_dues", direction="inflow", instrument="upi",
                    status="settled"),
    )
    periods = R.ledger_periods(entries, w, period="month", opening_balance_minor=1000000)
    assert periods[0].closing_balance_minor == 1300000
    assert periods[1].closing_balance_minor == 1300000


# ---------------------------------------------------------------------------
# member_lifecycle
# ---------------------------------------------------------------------------


def member(ref: str, at: datetime, kind: str, **kw) -> MemberEvent:
    return MemberEvent(member_ref=ref, at=at, kind=kind, **kw)


def test_member_spells_censor_the_people_who_have_not_left():
    w = window(100.0)
    events = (
        member("m1", EPOCH, "join"),
        member("m1", EPOCH + 30 * DAY, "exit", reason="moved_out"),
        member("m2", EPOCH + 10 * DAY, "join"),
    )
    spells = {s.member_ref: s for s in R.member_spells(events, w)}
    assert spells["m1"].event_observed is True
    assert spells["m1"].exit_kind == "exit"
    assert spells["m1"].duration_days == pytest.approx(30.0)
    assert spells["m2"].event_observed is False
    assert spells["m2"].exited_at is None
    assert spells["m2"].duration_days == pytest.approx(90.0)


def test_a_reinstatement_starts_a_second_spell():
    w = window(100.0)
    events = (
        member("m1", EPOCH, "join"),
        member("m1", EPOCH + 20 * DAY, "lapse"),
        member("m1", EPOCH + 50 * DAY, "reinstate"),
    )
    spells = R.member_spells(events, w)
    assert len(spells) == 2
    assert spells[0].event_observed is True and spells[0].exit_kind == "lapse"
    assert spells[1].event_observed is False
    assert spells[1].duration_days == pytest.approx(50.0)


def test_a_member_who_joined_before_the_window_is_left_truncated():
    w = window(100.0)
    spell = R.member_spells((member("m1", EPOCH - 200 * DAY, "join"),), w)[0]
    assert spell.left_truncated is True
    assert spell.at_risk_from == w.start
    assert spell.duration_days == pytest.approx(100.0)


def test_the_roster_snapshot_is_a_frame_at_the_boundary():
    w = window(100.0)
    events = (
        member("m1", EPOCH, "join", strata={"block": "A"}, role="committee"),
        member("m2", EPOCH, "join", strata={"block": "B"}),
        member("m3", EPOCH, "join", strata={"block": "A"}),
        member("m3", EPOCH + 10 * DAY, "exit"),
        member("m4", EPOCH + 200 * DAY, "join", strata={"block": "A"}),
    )
    roster = R.roster_snapshot(events, w, strata_keys=("block",))
    assert roster.total == 2, "the member who left is out, the one who joins later is not in yet"
    assert roster.as_of == w.end
    assert roster.counts_by_stratum == {("A",): 1, ("B",): 1}
    assert roster.roles == {"committee": 1, "member": 1}
    assert sum(roster.roles.values()) == roster.total


# ---------------------------------------------------------------------------
# participation and the derived units
# ---------------------------------------------------------------------------


def participation(ref: str, at: datetime, kind: str, **kw) -> ParticipationEvent:
    return ParticipationEvent(member_ref=ref, at=at, kind=kind, **kw)


def test_a_nudge_is_not_a_member_action():
    w = StreamWindow(
        start=EPOCH, end=EPOCH + 7 * DAY, timezone="UTC", complete_through=EPOCH + 7 * DAY
    )
    events = (
        participation("m1", EPOCH + DAY, "attend", object_ref="e_1", object_kind="event"),
        participation("m2", EPOCH + DAY, "nudge_sent", arm_ref="a"),
    )
    period = R.participation_periods(events, w, period="week")[0]
    assert period.active_members == 1, "an exposure is a system action, not participation"
    assert period.events_by_kind == {"attend": 1, "nudge_sent": 1}


def test_engagement_features_keep_the_member_who_did_nothing():
    w = window(100.0)
    spells = R.member_spells(
        (member("m1", EPOCH, "join"), member("m2", EPOCH, "join")), w
    )
    events = (participation("m1", EPOCH + 80 * DAY, "attend", object_ref="e_1"),)
    entries = (
        LedgerEntry(entry_ref="p", at=EPOCH + 5 * DAY, booked_at=EPOCH + 5 * DAY,
                    amount_minor=250000, currency="INR", category="maintenance_dues",
                    direction="inflow", instrument="upi", status="settled", member_ref="m1"),
    )
    features = {f.member_ref: f for f in R.engagement_features(events, entries, spells, w)}
    assert set(features) == {"m1", "m2"}
    assert features["m1"].recency_days == pytest.approx(20.0)
    assert features["m1"].frequency_90d == 1
    assert features["m1"].contribution_minor == 250000
    assert features["m2"].frequency_90d == 0
    assert features["m2"].recency_days == pytest.approx(100.0)
    assert features["m2"].contribution_minor == 0


def test_the_bipartite_projection_is_normalised_so_a_general_meeting_is_not_a_clique():
    """
    Three co-attendees each get 1/(3-1) = 0.5; a 200-person meeting gives each
    pair 1/199, so attending it is worth a two hundredth of a small meeting
    rather than the same as one.
    """
    w = window(30.0)
    small = tuple(
        participation("m%d" % i, EPOCH + DAY, "attend", object_ref="e_small")
        for i in range(1, 4)
    )
    edges = R.interaction_edges(small, w)
    assert len(edges) == 3
    assert all(e.weight == pytest.approx(0.5) for e in edges)

    agm = tuple(
        participation("p%03d" % i, EPOCH + 2 * DAY, "attend", object_ref="e_agm")
        for i in range(200)
    )
    agm_edges = R.interaction_edges(agm, w)
    assert all(e.weight == pytest.approx(1 / 199) for e in agm_edges)

    unnormalised = R.interaction_edges(small, w, normalisation="none")
    assert all(e.weight == pytest.approx(1.0) for e in unnormalised)


def test_a_reply_graph_is_refused_rather_than_approximated():
    with pytest.raises(ValueError, match="author of the parent message"):
        R.interaction_edges((), window(30.0), basis="reply")


def test_an_undetermined_outcome_is_not_a_trial():
    """
    Two vendors, and a request that is still open and younger than the SLA
    horizon has neither met the SLA nor missed it. Counting it either way is a
    number about our impatience, not about the vendor.
    """
    w = window(30.0)
    atoms: list[RequestEvent] = []
    for i in range(3):
        atoms += [
            opened("a%d" % i, EPOCH, assignee_ref="v_a"),
            event("a%d" % i, EPOCH + DAY, "resolved", assignee_ref="v_a"),
        ]
    atoms.append(opened("a-open", w.end - 2 * HOUR, assignee_ref="v_a"))
    for i in range(2):
        atoms += [
            opened("b%d" % i, EPOCH, assignee_ref="v_b"),
            event("b%d" % i, EPOCH + 10 * DAY, "resolved", assignee_ref="v_b"),
        ]

    def within_two_days(spell):
        if spell.event_observed:
            return spell.duration_hours <= 48.0
        return False if spell.duration_hours > 48.0 else None

    rates = {r.group_ref: r for r in R.rate_observations(
        R.request_spells(tuple(atoms), w), w, by="assignee_ref", success=within_two_days
    )}
    assert rates["v_a"].trials == 3 and rates["v_a"].successes == 3
    assert rates["v_b"].trials == 2 and rates["v_b"].successes == 0


def test_count_exposure_defaults_to_time_since_the_group_was_first_seen():
    w = window(100.0)
    atoms = (
        opened("old", EPOCH, category="water_supply"),
        opened("new", EPOCH + 86 * DAY, category="sewage_stp"),
    )
    counts = {c.group_ref: c for c in R.count_observations(R.request_spells(atoms, w), w)}
    assert counts["water_supply"].exposure == pytest.approx(100.0)
    assert counts["sewage_stp"].exposure == pytest.approx(14.0), (
        "a category first seen two weeks ago is not compared against one seen all year"
    )
    whole = {c.group_ref: c for c in R.count_observations(
        R.request_spells(atoms, w), w, exposure="window"
    )}
    assert whole["sewage_stp"].exposure == pytest.approx(100.0)


def test_pairwise_results_reproduce_a_condorcet_cycle():
    """
    The textbook cycle: A>B>C, B>C>A, C>A>B. Every pair is 2-1, so there is no
    Condorcet winner, and the reducer must produce the matrix that says so
    rather than one that resolves it.
    """
    spec = DecisionSpec(
        decision_ref="d1", kind="poll", opened_at=EPOCH, closed_at=None,
        declared_rule="schulze", ballot_style="ranked",
    )
    orders = (("A", "B", "C"), ("B", "C", "A"), ("C", "A", "B"))
    ballots = tuple(
        Ballot(
            ballot_ref="b%d" % i, decision_ref="d1", voter_ref="v%d" % i,
            cast_at=EPOCH + timedelta(hours=i),
            ranking=tuple((option,) for option in order),
        )
        for i, order in enumerate(orders)
    )
    results = R.pairwise_results(ballots, spec)
    wins: dict[tuple[str, str], int] = {}
    for r in results:
        assert r.drawn is False
        wins[(r.winner_ref, r.loser_ref)] = wins.get((r.winner_ref, r.loser_ref), 0) + 1
    assert wins[("A", "B")] == 2 and wins[("B", "A")] == 1
    assert wins[("B", "C")] == 2 and wins[("C", "B")] == 1
    assert wins[("C", "A")] == 2 and wins[("A", "C")] == 1


def test_tied_options_produce_drawn_comparisons():
    spec = DecisionSpec(decision_ref="d", kind="poll", opened_at=EPOCH, closed_at=None,
                        declared_rule="schulze")
    ballot = Ballot(ballot_ref="b", decision_ref="d", voter_ref="v", cast_at=EPOCH,
                    ranking=(("A", "B"), ("C",)))
    results = R.pairwise_results((ballot,), spec)
    drawn = [r for r in results if r.drawn]
    assert len(drawn) == 1 and {drawn[0].winner_ref, drawn[0].loser_ref} == {"A", "B"}
    assert len([r for r in results if not r.drawn]) == 2


def test_truncated_ballots_need_the_option_set_declared_not_guessed():
    spec = DecisionSpec(decision_ref="d", kind="poll", opened_at=EPOCH, closed_at=None,
                        declared_rule="schulze")
    ballot = Ballot(ballot_ref="b", decision_ref="d", voter_ref="v", cast_at=EPOCH,
                    ranking=(("A",), ("B",)))
    assert len(R.pairwise_results((ballot,), spec)) == 1

    with pytest.raises(ValueError, match="full option set"):
        R.pairwise_results((ballot,), spec, unranked="below_ranked")

    with_universe = R.pairwise_results(
        (ballot,), spec, options=("A", "B", "C"), unranked="below_ranked"
    )
    assert len(with_universe) == 3
    assert ("A", "C") in {(r.winner_ref, r.loser_ref) for r in with_universe}
