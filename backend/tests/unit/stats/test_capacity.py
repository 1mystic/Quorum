"""
The cross-stream server count, and why its convention is not cosmetic.

`docs/DATA_SPINE.md` section 8 names `FlowPeriod.active_servers` as the one
input Pack 1 needs that no single stream produces, and the module's own
docstring states the convention it exists to enforce: `rwa_society` declares a
committee member to be an 0.2 FTE server, because a volunteer available two
evenings a week is not a full-time agent, and Erlang-C staffing computed as if
they were understates the requirement by a factor of five.

`test_the_convention_moves_the_staffing_answer` measures that factor of five
against the real `queueing.erlang_c_staffing`, so the claim in the docstring is
a number this suite checks rather than a sentence in a comment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.stats import queueing as q
from app.stats.streams import capacity as cap
from app.stats.streams import reduce as R
from app.stats.streams.member import MemberEvent, RosterSnapshot
from app.stats.streams.request import RequestEvent
from app.stats.streams.window import StreamWindow

EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY = timedelta(days=1)
HOUR = timedelta(hours=1)


def week() -> tuple[datetime, datetime]:
    return EPOCH, EPOCH + 7 * DAY


def touch(ref: str, actor: str, at: datetime, kind: str = "comment") -> RequestEvent:
    return RequestEvent(request_ref=ref, at=at, kind=kind, actor_ref=actor)


def roster(**roles) -> RosterSnapshot:
    return RosterSnapshot(
        as_of=EPOCH + 7 * DAY,
        counts_by_stratum={},
        total=sum(roles.values()),
        roles=dict(roles),
    )


def test_four_committee_members_at_a_fifth_of_an_fte_are_zero_point_eight_servers():
    """The example in the module docstring, asserted."""
    events = [touch("r%d" % i, "m_%d" % i, EPOCH + DAY) for i in range(4)]
    value = cap.active_servers(
        roster(committee=4, resident=300), events, week(), fte_per_role={"committee": 0.2}
    )
    assert value == pytest.approx(0.8)
    assert isinstance(value, float), "rounding 0.8 up to 4 is how a diverging queue looks calm"


def test_a_member_to_role_map_is_used_exactly_when_it_is_supplied():
    events = [
        touch("r1", "m_chair", EPOCH + DAY),
        touch("r2", "m_helper", EPOCH + DAY),
        touch("r3", "m_vendor", EPOCH + DAY),
    ]
    value = cap.active_servers(
        roster(committee=2, vendor=1), events, week(),
        fte_per_role={"committee": 0.2, "vendor": 1.0},
        roles_by_member={"m_chair": "committee", "m_helper": "committee", "m_vendor": "vendor"},
    )
    assert value == pytest.approx(0.2 + 0.2 + 1.0)


def test_a_period_nobody_worked_has_no_servers():
    """
    Capacity nobody exercised was not demonstrated. Returning the roster's
    headcount here would hand a queueing model a phantom server and a wait
    nobody experienced.
    """
    assert cap.active_servers(roster(committee=4), (), week()) == 0.0
    assert cap.active_servers(
        roster(committee=4), [touch("r", "m_1", EPOCH + 30 * DAY)], week()
    ) == 0.0


def test_the_count_is_capped_at_the_declared_pool():
    """
    Six people touched a request but the vertical declares four 0.2-FTE
    committee servers. The uncapped figure would be 1.2 FTE from a pool that
    declares 0.8, and overstating servers is the direction that lets Erlang-C
    say a diverging queue is comfortable.
    """
    events = [touch("r%d" % i, "m_%d" % i, EPOCH + DAY) for i in range(6)]
    value = cap.active_servers(
        roster(committee=4, resident=300), events, week(), fte_per_role={"committee": 0.2}
    )
    assert value == pytest.approx(0.8)


def test_without_a_declared_convention_everyone_active_counts_as_one():
    events = [touch("r1", "m_1", EPOCH + DAY), touch("r2", "m_2", EPOCH + 2 * DAY)]
    assert cap.active_servers(roster(member=10), events, week()) == pytest.approx(2.0)


def test_both_the_actor_and_the_assignee_count_as_present():
    events = [
        RequestEvent(request_ref="r", at=EPOCH + DAY, kind="assigned",
                     actor_ref="m_admin", assignee_ref="m_plumber"),
    ]
    assert cap.active_servers(roster(member=5), events, week()) == pytest.approx(2.0)


def test_a_flow_period_is_accepted_as_the_period():
    w = StreamWindow(start=EPOCH, end=EPOCH + 7 * DAY, timezone="UTC",
                     complete_through=EPOCH + 7 * DAY)
    atoms = (
        RequestEvent(request_ref="r", at=EPOCH + DAY, kind="opened",
                     category="water_supply", actor_ref="m_1"),
    )
    period = R.flow_periods(atoms, w, period="week")[0]
    assert cap.active_servers(roster(member=5), atoms, period) == pytest.approx(1.0)


def test_anything_that_is_not_a_period_is_refused():
    with pytest.raises(ValueError, match="FlowPeriod or a"):
        cap.active_servers(roster(member=1), (), "last week")


def test_the_grid_form_feeds_flow_periods_directly():
    """
    `active_servers_by_period` returns the mapping `flow_periods` accepts, so
    the flow series and the staffing model cannot end up applying two different
    availability conventions.
    """
    w = StreamWindow(start=EPOCH, end=EPOCH + 21 * DAY, timezone="UTC",
                     complete_through=EPOCH + 21 * DAY)
    atoms = tuple(
        RequestEvent(request_ref="r%d" % i, at=EPOCH + timedelta(days=i), kind="opened",
                     category="water_supply", actor_ref="m_%d" % (i % 4))
        for i in range(21)
    )
    grid = R.period_bounds(w, "week")
    servers = cap.active_servers_by_period(
        roster(committee=4), atoms, grid, fte_per_role={"committee": 0.2}
    )
    periods = R.flow_periods(atoms, w, period="week", active_servers_by_period=servers)
    assert [p.active_servers for p in periods] == [servers[p.period_start] for p in periods]
    assert max(p.active_servers for p in periods) == pytest.approx(0.8)
    assert all(p.active_servers <= 0.8 for p in periods), "capped at the declared pool"


def test_the_convention_moves_the_staffing_answer():
    """
    The docstring's claim, measured. Feeding Erlang-C the head count instead of
    the FTE-weighted count is not a rounding difference: the same arrivals need
    materially more agents once volunteers are counted as volunteers.
    """
    w = StreamWindow(start=EPOCH, end=EPOCH + 7 * DAY, timezone="UTC",
                     complete_through=EPOCH + 7 * DAY)
    events = [touch("r%d" % i, "m_%d" % i, EPOCH + DAY) for i in range(4)]

    headcount = cap.active_servers(roster(committee=4), events, week())
    weighted = cap.active_servers(
        roster(committee=4), events, week(), fte_per_role={"committee": 0.2}
    )
    assert headcount == pytest.approx(4.0)
    assert weighted == pytest.approx(0.8)
    assert headcount / weighted == pytest.approx(5.0)

    as_headcount = q.erlang_c_staffing(3.0, 1.0, w, current_servers=headcount)
    as_declared = q.erlang_c_staffing(3.0, 1.0, w, current_servers=weighted)
    required = as_headcount.value["required_servers"]
    assert as_declared.value["required_servers"] == required
    assert as_headcount.value["gap"] < as_declared.value["gap"], (
        "the same queue and the same requirement; only the convention changed, and it is the "
        "difference between 'we are staffed' and 'we are short'"
    )
    assert as_declared.value["gap"] == pytest.approx(required - 0.8)


def test_a_declared_server_role_nobody_holds_still_weights_by_the_convention():
    """
    The roster says nobody is on the committee, but somebody did the work. They
    are real and they are counted, at the declared convention rather than at
    1.0, because 1.0 is the assumption this whole function exists to stop being
    made silently.
    """
    events = [touch("r1", "m_1", EPOCH + DAY)]
    value = cap.active_servers(
        roster(resident=100), events, week(), fte_per_role={"committee": 0.2}
    )
    assert value == pytest.approx(0.2)


def test_the_roster_snapshot_from_the_reducer_plugs_straight_in():
    """The two halves of the cross-stream join, actually joined."""
    w = StreamWindow(start=EPOCH, end=EPOCH + 7 * DAY, timezone="UTC",
                     complete_through=EPOCH + 7 * DAY)
    members = tuple(
        MemberEvent(member_ref="m_%d" % i, at=EPOCH - DAY, kind="join",
                    role="committee" if i < 4 else "resident")
        for i in range(10)
    )
    snapshot = R.roster_snapshot(members, w)
    assert snapshot.roles == {"committee": 4, "resident": 6}
    events = [touch("r%d" % i, "m_%d" % i, EPOCH + DAY) for i in range(4)]
    assert cap.active_servers(
        snapshot, events, week(), fte_per_role={"committee": 0.2}
    ) == pytest.approx(0.8)
