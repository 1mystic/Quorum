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

Status: specified, not yet implemented.
"""
from __future__ import annotations


def active_servers(roster, request_events, period, *, fte_per_role=None, default_fte=1.0) -> float:
    """
    Count the distinct people who could work a request in `period`, weighted by
    the declared availability convention.

    Returns a float, not an int: 4 committee members at 0.2 FTE is 0.8 servers,
    and rounding that up to 4 is how a staffing model comes to say a queue is
    comfortable when it is diverging.
    """
    raise NotImplementedError(
        "streams.capacity.active_servers is specified in docs/DATA_SPINE.md section 7 "
        "but not yet implemented"
    )


__all__ = ["active_servers"]
