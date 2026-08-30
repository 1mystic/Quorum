"""
The one declared cross-stream reducer. docs/DATA_SPINE.md sections 2 and 8.

`FlowPeriod.active_servers` is the input Pack 1 needs that no single stream
produces: it is a `member_lifecycle` role fact crossed with `request_flow`
assignment activity. It lives here, named and importable, rather than hidden
inside app/stats/queueing.py, because "how many resolvers do you actually have"
is the least well-defined input in the pack and its convention materially moves
every Erlang-C answer.

The availability convention is a declared parameter and enters `params_hash`:
`rwa_society` declares that a committee member is an 0.2 FTE server, because a
volunteer available two evenings a week is not a full-time agent, and an
Erlang-C staffing number computed as if they were will understate the
requirement by a factor of five.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

__all__ = ["active_servers", "active_servers_by_period"]


def _bounds(period: Any) -> tuple[datetime, datetime]:
    """A FlowPeriod, or any (start, end) pair. Nothing else is guessed at."""
    start = getattr(period, "period_start", None)
    end = getattr(period, "period_end", None)
    if start is not None and end is not None:
        return start, end
    try:
        start, end = period
    except (TypeError, ValueError):
        raise ValueError(
            "period must be a FlowPeriod or a (start, end) pair; got " + type(period).__name__
        ) from None
    return start, end


def _people_active(request_events: Iterable[Any], start: datetime, end: datetime) -> set[str]:
    """
    Who touched a request inside the period.

    Both `actor_ref` and `assignee_ref` count. A request assigned to somebody who
    never touched it is still work sitting on that person's desk, and a resolver
    who commented without ever being formally assigned did the work whatever the
    assignment field says.
    """
    people: set[str] = set()
    for event in request_events:
        at = getattr(event, "at", None)
        if at is None or not start <= at < end:
            continue
        actor = getattr(event, "actor_ref", None)
        assignee = getattr(event, "assignee_ref", None)
        if actor:
            people.add(actor)
        if assignee:
            people.add(assignee)
    return people


def active_servers(
    roster,
    request_events,
    period,
    *,
    fte_per_role=None,
    default_fte=1.0,
    roles_by_member: Mapping[str, str] | None = None,
) -> float:
    """
    Count the distinct people who could work a request in `period`, weighted by
    the declared availability convention.

    Returns a float, not an int: 4 committee members at 0.2 FTE is 0.8 servers,
    and rounding that up to 4 is how a staffing model comes to say a queue is
    comfortable when it is diverging.

    Three cases, in the order they are preferred:

    1. **`roles_by_member` supplied.** Every active person is weighted by their
       own role's FTE. This is the only exact answer and it is what a caller with
       a member-to-role map should always pass.
    2. **`fte_per_role` supplied without the map.** `RosterSnapshot.roles` is
       `role -> headcount`, not `member -> role`, so no individual can be
       attributed. The roles *named in* `fte_per_role` are the declared server
       pool, and each active person is weighted by that pool's headcount-weighted
       mean FTE. With one server role at 0.2 that reduces to 0.2 each, which is
       the `rwa_society` convention in the module docstring: four active
       committee members are 0.8 servers.
    3. **Neither.** Every active person counts as `default_fte`.

    In cases 2 and 3 the result is capped at the declared pool's total FTE, so
    a person outside the pool who helped once cannot inflate the server count.
    The cap is deliberately asymmetric: overstating servers makes Erlang-C
    understate the staffing requirement, which is the direction that lets a
    queue diverge while the dashboard says it is comfortable. Understating them
    only asks for more help than strictly needed, and says so out loud.

    A period in which nobody touched a request has **zero** active servers, not
    the roster's headcount. Capacity nobody exercised is capacity that was not
    demonstrated, and a queueing model fed a phantom server reports a wait that
    nobody experienced.
    """
    start, end = _bounds(period)
    people = _people_active(request_events or (), start, end)
    if not people:
        return 0.0

    if roles_by_member:
        weights = dict(fte_per_role or {})
        return float(sum(
            float(weights.get(roles_by_member.get(ref, ""), default_fte)) for ref in people
        ))

    roles: Mapping[str, int] = dict(getattr(roster, "roles", None) or {})

    if fte_per_role:
        headcount = sum(int(roles.get(role, 0)) for role in fte_per_role)
        pool_fte = sum(
            int(roles.get(role, 0)) * float(weight) for role, weight in fte_per_role.items()
        )
        if headcount <= 0:
            # The vertical declared server roles that nobody on this roster
            # holds. The people who did the work are still real; they are
            # weighted at the mean of the declared convention rather than at
            # 1.0, because 1.0 is the assumption this whole function exists to
            # stop being made silently.
            mean_fte = (
                sum(float(w) for w in fte_per_role.values()) / len(fte_per_role)
            )
            return float(len(people) * mean_fte)
        mean_fte = pool_fte / headcount
        return float(min(len(people) * mean_fte, pool_fte))

    total = int(getattr(roster, "total", 0) or 0)
    value = len(people) * float(default_fte)
    if total > 0:
        value = min(value, total * float(default_fte))
    return float(value)


def active_servers_by_period(
    roster,
    request_events,
    periods,
    *,
    fte_per_role=None,
    default_fte=1.0,
    roles_by_member: Mapping[str, str] | None = None,
) -> dict[datetime, float]:
    """
    The same convention applied across a whole period grid, in the shape
    `streams.reduce.flow_periods(..., active_servers_by_period=...)` accepts:
    a mapping keyed by `period_start`.

    Kept here rather than in `reduce` so that the availability convention lives
    in exactly one module and a caller cannot apply one rule to the staffing
    model and a different one to the flow series.
    """
    events = tuple(request_events or ())
    out: dict[datetime, float] = {}
    for period in periods:
        start, end = _bounds(period)
        out[start] = active_servers(
            roster, events, (start, end),
            fte_per_role=fte_per_role, default_fte=default_fte,
            roles_by_member=roles_by_member,
        )
    return out
