"""
Atoms to units. The pure half of the spine, and where the correctness lives.

Censoring is decided here, in a reducer, and nowhere else. A
`WHERE resolved_at IS NOT NULL` in a repository is invisible to the test suite,
whereas a reducer that mis-censors fails a known-answer test. That is the whole
reason this boundary exists.

Every function here takes atoms plus a `StreamWindow` and returns units. None of
them reads a clock: "now" is `window.end` (spine rule S6).

The ten censoring rules C1 to C10 are reproduced verbatim in
`app.stats.streams.request.CENSORING_RULES`. Each one is implemented in
`request_spells` below and the implementing block names its rule, so a reader
can check the code against the document line by line rather than trusting a
summary of it.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Sequence

from app.stats.streams.decision import Ballot, DecisionSpec
from app.stats.streams.derived import CountObservation, PairwiseResult, RateObservation
from app.stats.streams.ledger import DueSpell, LedgerEntry, LedgerPeriod
from app.stats.streams.member import MemberEvent, MemberSpell, RosterSnapshot
from app.stats.streams.participation import (
    EXPOSURE_KINDS,
    EngagementFeatures,
    InteractionEdge,
    ParticipationEvent,
    ParticipationPeriod,
)
from app.stats.streams.request import TERMINAL_KINDS, FlowPeriod, RequestEvent, RequestSpell
from app.stats.streams.window import StreamWindow

SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86400.0

PERIODS: tuple[str, ...] = ("day", "week", "month", "quarter", "year")

# Same instant, different meanings. A terminal and the "opened" that shares its
# timestamp must not be ordered arbitrarily, or a request opened and resolved in
# the same second would sometimes reduce to a censored spell.
_KIND_ORDER: Mapping[str, int] = MappingProxyType({
    "opened": 0,
    "acknowledged": 1,
    "assigned": 2,
    "reassigned": 2,
    "status_change": 3,
    "comment": 3,
    "paused": 4,
    "resumed": 4,
    "resolved": 5,
    "escalated": 5,
    "withdrawn": 5,
    "merged": 5,
    "closed": 6,
    "reopened": 7,
})

_RESPONSE_KINDS: frozenset[str] = frozenset({"acknowledged", "comment"})


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / SECONDS_PER_HOUR


def _days(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / SECONDS_PER_DAY


def _zone(name: str):
    """
    The IANA zone named by the window, or UTC if this host has no tz database.

    Deterministic and offline: `zoneinfo` reads a static table, it does not read
    a clock and it does not open a socket. Falling back to UTC rather than
    raising keeps a bucketing choice from taking down a whole materialization
    run, and the fallback is visible because every period boundary lands on a
    UTC midnight instead of a local one.
    """
    if not name or name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:      # pragma: no cover - host without a tz database
        return timezone.utc


def _floor_local(local: datetime, period: str) -> datetime:
    """Floor a local wall-clock datetime to the start of its calendar period."""
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "day":
        return midnight
    if period == "week":
        return midnight - timedelta(days=midnight.weekday())
    if period == "month":
        return midnight.replace(day=1)
    if period == "quarter":
        return midnight.replace(month=3 * ((midnight.month - 1) // 3) + 1, day=1)
    if period == "year":
        return midnight.replace(month=1, day=1)
    raise ValueError("period must be one of " + repr(PERIODS) + ", got " + repr(period))


def _advance_local(local: datetime, period: str) -> datetime:
    if period == "day":
        return local + timedelta(days=1)
    if period == "week":
        return local + timedelta(days=7)
    step = {"month": 1, "quarter": 3, "year": 12}[period]
    month = local.month - 1 + step
    return local.replace(year=local.year + month // 12, month=month % 12 + 1)


def period_bounds(window: StreamWindow, period: str = "week") -> tuple[tuple[datetime, datetime], ...]:
    """
    Calendar buckets covering `[window.start, window.end)`, in the window's own
    timezone (spine rule S1: local calendar bucketing uses `StreamWindow.timezone`
    and nothing else).

    Bounds are true calendar bounds, not clipped to the window. A bucket that the
    window only partially covers is emitted with `complete=False` by the callers
    below, because a half-covered first week is the same defect as a half-reported
    last week: it reads as a collapse rather than as an artefact of where the
    window happens to start.
    """
    if period not in PERIODS:
        raise ValueError("period must be one of " + repr(PERIODS) + ", got " + repr(period))
    zone = _zone(window.timezone)
    cursor = _floor_local(window.start.astimezone(zone).replace(tzinfo=None), period)
    out: list[tuple[datetime, datetime]] = []
    guard = 0
    while True:
        guard += 1
        if guard > 100000:      # pragma: no cover - a window of over 270 years of days
            raise ValueError("window spans too many periods to bucket")
        nxt = _advance_local(cursor, period)
        start_utc = cursor.replace(tzinfo=zone).astimezone(timezone.utc)
        end_utc = nxt.replace(tzinfo=zone).astimezone(timezone.utc)
        if start_utc >= window.end:
            break
        if end_utc > window.start:
            out.append((start_utc, end_utc))
        cursor = nxt
    return tuple(out)


def _bucket_meta(
    window: StreamWindow, bounds: tuple[datetime, datetime]
) -> tuple[float, bool]:
    """(observed exposure in days, complete) for one calendar bucket."""
    start, end = bounds
    observed_start = max(start, window.start)
    observed_end = min(end, window.end)
    exposure = max(0.0, _days(observed_start, observed_end))
    covered = start >= window.start and end <= window.end
    complete = covered and end <= window.complete_through
    return exposure, complete


# ---------------------------------------------------------------------------
# request_flow. The function the product's correctness claim rests on.
# ---------------------------------------------------------------------------


def _ordered(events: Iterable[RequestEvent]) -> dict[str, list[RequestEvent]]:
    grouped: dict[str, list[RequestEvent]] = defaultdict(list)
    for event in events:
        grouped[event.request_ref].append(event)
    for group in grouped.values():
        group.sort(key=lambda e: (e.at, _KIND_ORDER.get(e.kind, 9)))
    return grouped


def _episodes(
    events: Sequence[RequestEvent], reopen_policy: str
) -> tuple[list[list[RequestEvent]], int]:
    """
    Rule C6. The reopen policy is a declared parameter, not a convention.

    `new_spell` closes the first spell at its terminal and starts a child whose
    clock restarts at the reopen. `extend` keeps one spell and counts the
    reopens. Returns (episodes, reopened_count); under `new_spell` the count is
    per episode and is always zero.
    """
    if reopen_policy not in ("new_spell", "extend"):
        raise ValueError(
            "reopen_policy must be 'new_spell' or 'extend' (rule C6), got " + repr(reopen_policy)
        )
    if reopen_policy == "extend":
        return [list(events)], sum(1 for e in events if e.kind == "reopened")
    episodes: list[list[RequestEvent]] = []
    current: list[RequestEvent] = []
    for event in events:
        if event.kind == "reopened" and current:
            episodes.append(current)
            current = [event]
            continue
        current.append(event)
    if current:
        episodes.append(current)
    return episodes, 0


def _paused_hours(
    events: Sequence[RequestEvent], start: datetime, end: datetime
) -> float:
    """
    Rule C8. Paired paused/resumed intervals, clipped to the observation span.

    An unpaired `paused` runs to the end of observation, which is what actually
    happened: the request was still on hold when we stopped looking. An unpaired
    `resumed` is ignored rather than treated as a pause from time zero.
    """
    total = 0.0
    pause_start: datetime | None = None
    for event in events:
        if event.at >= end:
            break
        if event.kind == "paused" and pause_start is None:
            pause_start = event.at
        elif event.kind == "resumed" and pause_start is not None:
            lo = max(pause_start, start)
            hi = min(event.at, end)
            if hi > lo:
                total += _hours(lo, hi)
            pause_start = None
    if pause_start is not None:
        lo = max(pause_start, start)
        if end > lo:
            total += _hours(lo, end)
    return total


def request_spells(
    events: tuple[RequestEvent, ...],
    window: StreamWindow,
    *,
    reopen_policy: str = "new_spell",
    sla_clock: str = "wall",
    lost_after_days: float | None = None,
) -> tuple[RequestSpell, ...]:
    """
    The most important function in this package.

    Every request opened before `window.end` comes out of here, censored if it
    has no terminal event (rule C1). There is no argument that filters by
    outcome and there will not be one: the honest signature is the enforcement.

    Rule by rule, as implemented below:

    - **C1** every `opened` atom before `window.end` produces a spell. The only
      rows that do not are those whose whole life ended before `window.start`,
      which is a window filter and not an outcome filter: they contribute no
      exposure and no event inside the observation period.
    - **C2** no terminal by `window.end` gives `event_observed=False`,
      `censoring="administrative"`, `duration_hours = window.end - at_risk_from`.
    - **C3** opened before `window.start` gives `at_risk_from = window.start`,
      `left_truncated=True`, and the clock is measured from `at_risk_from` so the
      estimator's delayed-entry `(entry, exit]` risk set reconstructs the true
      age as `entry = at_risk_from - opened_at`.
    - **C4** a `bracketed` terminal gives `censoring="interval"` with both bracket
      ends filled and `terminal_at=None`. No midpoint is imputed anywhere.
    - **C5** the competing cause is recorded in `outcome` and `censoring` stays
      `"none"`, because the reducer does not know which cause is under analysis.
      Whether escalations are events or competing risks is the estimator's
      decision and `survival._check_competing_risks` reads `outcome` to make it.
    - **C6** `reopen_policy` splits or extends, above.
    - **C7** a merged request is still emitted, with `outcome="merged"`, and the
      survivor's `duplicate_count` increments. The *exclusion* happens in the
      estimator (`survival._request_rows`), which counts it into `n_excluded`
      with `exclusion_reason="merged_duplicate"`. Dropping it here would make the
      exclusion invisible, and an invisible exclusion is indistinguishable from a
      lost row.
    - **C8** `duration_hours` is always wall clock. `duration_active_hours` is
      filled only when the vertical declares `sla_clock="active"`, so a service
      asking for the active clock where the vertical never declared one gets
      `None` and says it fell back, rather than silently reporting a different
      quantity.
    - **C9** `covariates` carries the opened atom's attributes, which is what the
      censoring-informative check compares between censored and observed spells.
    - **C10** nothing is imputed, interpolated or carried forward. An unknown
      terminal is `None` and the spell is censored.

    `lost_after_days` is off by default. When set, a spell with no activity for
    that many days before `window.end` is censored at its last event rather than
    at the boundary, with `censoring="lost"`. It changes the duration, so it is a
    declared parameter that enters `params_hash`, never a heuristic.
    """
    if sla_clock not in ("wall", "active"):
        raise ValueError("sla_clock must be 'wall' or 'active' (rule C8), got " + repr(sla_clock))

    grouped = _ordered(events)

    # Rule C7: which surviving request each merge points at, counted once over
    # the whole atom set before any spell is built.
    merged_into: Counter[str] = Counter()
    merge_times: dict[str, list[datetime]] = defaultdict(list)
    for group in grouped.values():
        for event in group:
            if event.kind == "merged" and event.parent_ref:
                merged_into[event.parent_ref] += 1
                merge_times[event.parent_ref].append(event.at)

    spells: list[RequestSpell] = []
    for ref in sorted(grouped):
        group = grouped[ref]
        if group[0].kind != "opened":
            raise ValueError(
                "request " + ref + " has no 'opened' atom, so its clock has no start. Rule C10 "
                "forbids inventing one; the adapter must emit an 'opened' event for every row it "
                "sees (docs/DATA_SPINE.md section 9, obligation 3)."
            )
        episodes, reopened_count = _episodes(group, reopen_policy)
        pending_merges = list(merge_times.get(ref, ()))
        for index, episode in enumerate(episodes):
            spell = _spell_from_episode(
                base_ref=ref,
                index=index,
                episode=episode,
                window=window,
                reopened_count=reopened_count,
                sla_clock=sla_clock,
                lost_after_days=lost_after_days,
                duplicate_count=sum(
                    1 for at in pending_merges
                    if _in_episode(at, episode, episodes, index, window)
                ),
            )
            if spell is not None:
                spells.append(spell)
    spells.sort(key=lambda s: (s.opened_at, s.request_ref))
    return tuple(spells)


def _in_episode(
    at: datetime,
    episode: Sequence[RequestEvent],
    episodes: Sequence[Sequence[RequestEvent]],
    index: int,
    window: StreamWindow,
) -> bool:
    """Which spell of a reopened request a merge into it belongs to."""
    start = episode[0].at
    end = episodes[index + 1][0].at if index + 1 < len(episodes) else window.end
    return start <= at < end


def _spell_from_episode(
    *,
    base_ref: str,
    index: int,
    episode: Sequence[RequestEvent],
    window: StreamWindow,
    reopened_count: int,
    sla_clock: str,
    lost_after_days: float | None,
    duplicate_count: int,
) -> RequestSpell | None:
    opened = episode[0]
    opened_at = opened.at

    # Rule C1: the boundary is window.end and nothing else. A request opened at
    # or after it has not happened yet as far as this window is concerned.
    if opened_at >= window.end:
        return None

    # The terminal is the last one not undone by a reopen. Under
    # reopen_policy="new_spell" a reopen has already split the episode, so this
    # is simply the one terminal in it; under "extend" it is what stops a
    # request that was resolved, reopened and resolved again from being recorded
    # as having ended the first time (rule C6).
    terminal: RequestEvent | None = None
    for candidate in episode:
        if candidate.kind in TERMINAL_KINDS:
            terminal = candidate
        elif candidate.kind == "reopened":
            terminal = None

    # Ends before the window opened: no exposure and no event inside the
    # observation period. A window filter, not an outcome filter.
    if terminal is not None and terminal.at < window.start:
        upper = terminal.at_upper if terminal.at_precision == "bracketed" else terminal.at
        if upper is None or upper < window.start:
            return None

    at_risk_from = max(opened_at, window.start)
    left_truncated = opened_at < window.start

    terminal_at: datetime | None = None
    outcome = None
    censoring = "administrative"
    event_observed = False
    interval_lo_hours: float | None = None
    interval_hi_hours: float | None = None

    if terminal is not None and terminal.at < window.end:
        outcome = terminal.kind
        if terminal.at_precision == "bracketed":
            # Rule C4. The bracket is carried; no midpoint is invented.
            lo_at = terminal.at
            hi_at = min(terminal.at_upper or terminal.at, window.end)
            event_observed = True
            censoring = "interval"
            interval_lo_hours = max(0.0, _hours(at_risk_from, lo_at))
            interval_hi_hours = max(interval_lo_hours, _hours(at_risk_from, hi_at))
            observation_end = max(at_risk_from, lo_at)
            duration_hours = interval_lo_hours
        else:
            event_observed = True
            censoring = "none"
            terminal_at = terminal.at
            observation_end = max(at_risk_from, terminal.at)
            duration_hours = _hours(at_risk_from, observation_end)
    else:
        # Rule C2. Still open at the boundary, and counted.
        observation_end = window.end
        duration_hours = max(0.0, _hours(at_risk_from, window.end))
        last_seen = max(
            (e.at for e in episode if e.at < window.end), default=at_risk_from
        )
        if lost_after_days is not None and _days(last_seen, window.end) > lost_after_days:
            censoring = "lost"
            observation_end = max(at_risk_from, last_seen)
            duration_hours = _hours(at_risk_from, observation_end)

    observed = [e for e in episode if e.at <= observation_end]

    # Rule C8. Wall clock is the default because the resident lives in wall clock.
    paused = _paused_hours(episode, at_risk_from, observation_end)
    duration_active_hours = (
        max(0.0, duration_hours - paused) if sla_clock == "active" else None
    )

    # Reported from opened_at, which is where the field is defined from. For a
    # left-truncated request answered before the window opened this is smaller
    # than the delayed-entry offset, so the estimator's risk set never contains
    # the row: correct, since that first response was not observed here.
    first_response_hours: float | None = None
    author = opened.actor_ref
    for event in episode:
        if event.at >= window.end:
            break
        if event.kind in _RESPONSE_KINDS and event.actor_ref and event.actor_ref != author:
            first_response_hours = max(0.0, _hours(opened_at, event.at))
            break

    category = opened.category
    for event in observed:
        if event.category:
            category = event.category

    assignee_ref = None
    for event in observed:
        if event.assignee_ref:
            assignee_ref = event.assignee_ref

    def _last(field: str):
        value = getattr(opened, field, None)
        for event in observed:
            candidate = getattr(event, field, None)
            if candidate:
                value = candidate
        return value

    ref = base_ref if index == 0 else base_ref + "#" + str(index + 1)
    return RequestSpell(
        request_ref=ref,
        opened_at=opened_at,
        at_risk_from=at_risk_from,
        left_truncated=left_truncated,
        duration_hours=max(0.0, duration_hours),
        duration_active_hours=duration_active_hours,
        event_observed=event_observed,
        outcome=outcome,
        terminal_at=terminal_at,
        censoring=censoring,
        interval_lo_hours=interval_lo_hours,
        interval_hi_hours=interval_hi_hours,
        first_response_hours=first_response_hours,
        paused_hours=paused,
        reopened_count=reopened_count,
        duplicate_count=duplicate_count,
        category=category or "other",
        subcategory=_last("subcategory"),
        priority=_last("priority"),
        channel=_last("channel"),
        location_ref=_last("location_ref"),
        group_ref=_last("group_ref"),
        assignee_ref=assignee_ref,
        parent_ref=base_ref if index else None,
        n_reassignments=sum(1 for e in observed if e.kind == "reassigned"),
        covariates=dict(opened.attributes),
    )


def flow_periods(
    events: tuple[RequestEvent, ...],
    window: StreamWindow,
    *,
    period: str = "week",
    active_servers_by_period=None,
    reopen_policy: str = "new_spell",
) -> tuple[FlowPeriod, ...]:
    """
    Periodised counts. Periods after `window.complete_through` are emitted with
    `complete=False` rather than dropped, so a forecaster can exclude them and
    say it did rather than reading a partial bucket as a collapse.

    Built from the spells rather than straight from the atoms, so the same
    censoring and merge rules govern both units. A merged duplicate is not
    demand (rule C7), so it is excluded from arrivals, terminals and backlog: it
    is the same request counted twice.

    `active_servers_by_period` may be a mapping keyed by `period_start`, or a
    callable `(period_start, period_end, events_in_period) -> float`. Left as
    `None`, the count is the distinct people who touched a request in that
    period, weighted at one server each. That is the request-side half of the
    quantity only; the roster-crossed, FTE-weighted figure that Erlang-C
    actually wants comes from `streams.capacity.active_servers`, and passing it
    in here is how it gets there.
    """
    spells = request_spells(events, window, reopen_policy=reopen_policy)
    spells = tuple(s for s in spells if s.outcome != "merged")
    bounds = period_bounds(window, period)
    by_ref = _ordered(events)

    out: list[FlowPeriod] = []
    for start, end in bounds:
        exposure_days, complete = _bucket_meta(window, (start, end))
        arrivals = sum(1 for s in spells if start <= s.opened_at < end)
        terminated = [
            s for s in spells
            if s.event_observed and s.terminal_at is not None and start <= s.terminal_at < end
        ]
        backlog_start = _backlog_at(spells, start)
        backlog_end = _backlog_at(spells, end)
        if active_servers_by_period is None:
            servers = float(len(_touched_by(by_ref, start, end)))
        elif callable(active_servers_by_period):
            in_period = tuple(
                e for group in by_ref.values() for e in group if start <= e.at < end
            )
            servers = float(active_servers_by_period(start, end, in_period))
        else:
            servers = float(active_servers_by_period.get(start, 0.0))
        rate = arrivals / exposure_days if exposure_days > 0.0 else 0.0
        out.append(FlowPeriod(
            period_start=start,
            period_end=end,
            arrivals=arrivals,
            terminals=len(terminated),
            resolutions=sum(1 for s in terminated if s.outcome == "resolved"),
            backlog_end=backlog_end,
            backlog_start=backlog_start,
            active_servers=servers,
            arrival_rate_per_day=rate,
            exposure_days=exposure_days,
            complete=complete,
        ))
    return tuple(out)


def _backlog_at(spells: Sequence[RequestSpell], at: datetime) -> int:
    """Open at `at`: opened at or before it, and not terminated before it."""
    total = 0
    for spell in spells:
        if spell.opened_at > at:
            continue
        if spell.terminal_at is not None and spell.terminal_at <= at:
            continue
        total += 1
    return total


def _touched_by(
    by_ref: Mapping[str, Sequence[RequestEvent]], start: datetime, end: datetime
) -> set[str]:
    people: set[str] = set()
    for group in by_ref.values():
        for event in group:
            if not start <= event.at < end:
                continue
            if event.actor_ref:
                people.add(event.actor_ref)
            if event.assignee_ref:
                people.add(event.assignee_ref)
    return people


# ---------------------------------------------------------------------------
# member_lifecycle
# ---------------------------------------------------------------------------

_ENTRY_KINDS: frozenset[str] = frozenset({"join", "reinstate"})
_EXIT_KINDS: frozenset[str] = frozenset({"lapse", "exit"})


def member_spells(
    events: tuple[MemberEvent, ...], window: StreamWindow
) -> tuple[MemberSpell, ...]:
    """
    One spell per membership episode: join or reinstate, to the lapse or exit
    that ends it, censored at `window.end` when none does.

    Rule C3 applies here exactly as it does to requests: a member who joined
    before the window enters the risk set at `window.start` with
    `left_truncated=True`, and `duration_days` is measured from `at_risk_from`,
    so the estimator recovers the true tenure as `entry + duration`.
    """
    grouped: dict[str, list[MemberEvent]] = defaultdict(list)
    for event in events:
        grouped[event.member_ref].append(event)

    spells: list[MemberSpell] = []
    for ref in sorted(grouped):
        group = sorted(grouped[ref], key=lambda e: e.at)
        strata: dict[str, str] = {}
        role: str | None = None
        entered_at: datetime | None = None
        entry_strata: dict[str, str] = {}
        for event in group:
            if event.strata:
                strata = dict(event.strata)
            if event.role:
                role = event.role
            if event.kind in _ENTRY_KINDS and entered_at is None:
                entered_at = event.at
                entry_strata = dict(strata)
            elif event.kind in _EXIT_KINDS and entered_at is not None:
                spell = _member_spell(
                    ref, entered_at, event.at, event.kind, window, entry_strata, role
                )
                if spell is not None:
                    spells.append(spell)
                entered_at = None
        if entered_at is not None:
            spell = _member_spell(ref, entered_at, None, None, window, entry_strata, role)
            if spell is not None:
                spells.append(spell)
    spells.sort(key=lambda s: (s.entered_at, s.member_ref))
    return tuple(spells)


def _member_spell(
    ref: str,
    entered_at: datetime,
    exited_at: datetime | None,
    exit_kind: str | None,
    window: StreamWindow,
    strata: Mapping[str, str],
    role: str | None,
) -> MemberSpell | None:
    if entered_at >= window.end:
        return None
    if exited_at is not None and exited_at < window.start:
        return None
    at_risk_from = max(entered_at, window.start)
    observed = exited_at is not None and exited_at < window.end
    end = exited_at if observed else window.end
    return MemberSpell(
        member_ref=ref,
        entered_at=entered_at,
        at_risk_from=at_risk_from,
        left_truncated=entered_at < window.start,
        exited_at=exited_at if observed else None,
        exit_kind=exit_kind if observed else None,
        event_observed=bool(observed),
        duration_days=max(0.0, _days(at_risk_from, end)),
        strata_at_entry=dict(strata),
        covariates={"role": role} if role else {},
    )


def roster_snapshot(
    events: tuple[MemberEvent, ...], window: StreamWindow, *, strata_keys: tuple[str, ...] = ()
) -> RosterSnapshot:
    """
    The population frame, at `window.end`, which is every denominator in Pack 4.

    A member is in the frame if they entered before `window.end` and their last
    lifecycle event before it was not an exit or a lapse. `roles` counts every
    member in the frame, defaulting to `"member"` where no role was ever
    declared, so the role counts sum to the total and can be used directly as
    FTE weights by `streams.capacity.active_servers`.
    """
    grouped: dict[str, list[MemberEvent]] = defaultdict(list)
    for event in events:
        if event.at < window.end:
            grouped[event.member_ref].append(event)

    counts: dict[tuple[str, ...], int] = defaultdict(int)
    roles: dict[str, int] = defaultdict(int)
    total = 0
    for ref in sorted(grouped):
        group = sorted(grouped[ref], key=lambda e: e.at)
        present = False
        strata: dict[str, str] = {}
        role = "member"
        for event in group:
            if event.strata:
                strata.update(event.strata)
            if event.role:
                role = event.role
            if event.kind in _ENTRY_KINDS:
                present = True
            elif event.kind in _EXIT_KINDS:
                present = False
        if not present:
            continue
        total += 1
        roles[role] += 1
        if strata_keys:
            counts[tuple(strata.get(key, "unknown") for key in strata_keys)] += 1
    return RosterSnapshot(
        as_of=window.end,
        counts_by_stratum=dict(counts),
        total=total,
        roles=dict(roles),
    )


# ---------------------------------------------------------------------------
# ledger
# ---------------------------------------------------------------------------

_UNPAYABLE: frozenset[str] = frozenset({"written_off", "reversed", "failed"})


def due_spells(entries: tuple[LedgerEntry, ...], window: StreamWindow) -> tuple[DueSpell, ...]:
    """
    An unpaid due is right-censored, exactly like an open request (rule L1).

    The clock runs from `due_at`, so a due settled early has a negative duration
    and that is the truth about it, not an error. A due that has been written off
    or reversed will never be settled, which is a competing risk rather than
    neutral censoring, and it is recorded as `censoring="competing"` so a
    Kaplan-Meier of days-to-pay cannot quietly treat it as "still might pay".

    A reversal entry (rule L3) is a correction, not a receivable, and is not a
    due spell.
    """
    spells: list[DueSpell] = []
    for entry in entries:
        if entry.due_at is None or entry.reversal_of is not None:
            continue
        settled_at = entry.settled_at
        observed = settled_at is not None and settled_at < window.end
        if not observed and entry.due_at >= window.end:
            # Not yet due and not yet paid: no exposure inside this window.
            continue
        if observed and settled_at < window.start:
            continue
        end = settled_at if observed else window.end
        if entry.status in _UNPAYABLE and not observed:
            censoring = "competing"
        elif observed:
            censoring = "none"
        else:
            censoring = "administrative"
        strata = {"category": entry.category, "instrument": entry.instrument}
        if entry.group_ref:
            strata["group"] = entry.group_ref
        reminders = entry.attributes.get("reminders_sent", 0)
        spells.append(DueSpell(
            due_ref=entry.entry_ref,
            member_ref=entry.member_ref or "unassigned",
            issued_at=entry.at,
            due_at=entry.due_at,
            amount_minor=abs(int(entry.amount_minor)),
            at_risk_from=max(entry.due_at, window.start),
            settled_at=settled_at if observed else None,
            duration_days=_days(entry.due_at, end),
            event_observed=bool(observed),
            censoring=censoring,
            partial_paid_minor=int(entry.attributes.get("partial_paid_minor", 0) or 0),
            reminders_sent=int(reminders or 0),
            strata=strata,
        ))
    spells.sort(key=lambda s: (s.due_at, s.due_ref))
    return tuple(spells)


def ledger_periods(
    entries: tuple[LedgerEntry, ...],
    window: StreamWindow,
    *,
    period: str = "month",
    opening_balance_minor: int | None = None,
) -> tuple[LedgerPeriod, ...]:
    """
    Periodised money, bucketed on the value date `at`.

    Rule L2: only `settled` entries are actuals. `expected` and `pending` entries
    are receivables, and they are carried separately under the `by_category` key
    `"expected"`, which is where `montecarlo.runway_shortfall` reads them to
    report what share of a projected inflow has not actually arrived. Adding them
    to `inflow_minor` would make the runway fiction, which is the whole reason
    the status field exists.

    `closing_balance_minor` is `None` unless an `opening_balance_minor` is
    supplied. A running total that started at zero at an arbitrary window start
    is not a balance, and printing one next to a currency symbol would be a
    fabricated number.
    """
    bounds = period_bounds(window, period)
    balance = opening_balance_minor
    out: list[LedgerPeriod] = []
    for start, end in bounds:
        _, complete = _bucket_meta(window, (start, end))
        inflow = 0
        outflow = 0
        by_category: dict[str, int] = defaultdict(int)
        for entry in entries:
            if not start <= entry.at < end:
                continue
            if entry.status in ("expected", "pending"):
                by_category["expected"] += abs(int(entry.amount_minor))
                continue
            if entry.status != "settled":
                continue
            if entry.amount_minor >= 0:
                inflow += entry.amount_minor
            else:
                outflow += entry.amount_minor
            by_category[entry.category] += entry.amount_minor
        net = inflow + outflow
        if balance is not None:
            balance = balance + net
        out.append(LedgerPeriod(
            period_start=start,
            period_end=end,
            inflow_minor=inflow,
            outflow_minor=outflow,
            net_minor=net,
            closing_balance_minor=balance,
            by_category=dict(by_category),
            complete=complete,
        ))
    return tuple(out)


# ---------------------------------------------------------------------------
# participation
# ---------------------------------------------------------------------------


def participation_periods(
    events: tuple[ParticipationEvent, ...], window: StreamWindow, *, period: str = "week"
) -> tuple[ParticipationPeriod, ...]:
    """
    Periodised participation.

    `active_members` counts distinct members who *did* something. A `nudge_sent`
    is a system action against a member, not a member action, so the exposure log
    never inflates the activity count; it is still counted by kind, because an
    experiment needs to see its own exposures.
    """
    bounds = period_bounds(window, period)
    out: list[ParticipationPeriod] = []
    for start, end in bounds:
        _, complete = _bucket_meta(window, (start, end))
        active: set[str] = set()
        by_kind: dict[str, int] = defaultdict(int)
        weight = 0.0
        for event in events:
            if not start <= event.at < end:
                continue
            by_kind[event.kind] += 1
            if event.kind not in EXPOSURE_KINDS:
                active.add(event.member_ref)
                weight += float(event.weight)
        out.append(ParticipationPeriod(
            period_start=start,
            period_end=end,
            active_members=len(active),
            events_by_kind=dict(by_kind),
            total_weight=weight,
            complete=complete,
        ))
    return tuple(out)


def engagement_features(
    events: tuple[ParticipationEvent, ...],
    entries: tuple[LedgerEntry, ...],
    spells: tuple[MemberSpell, ...],
    window: StreamWindow,
) -> tuple[EngagementFeatures, ...]:
    """
    RFM, generalised, as of `window.end`.

    The population is the roster (`spells`), not the set of people who happened
    to do something: a member with no activity at all is the most important row
    in a churn model and dropping them is how an engagement table comes to say
    everyone is engaged. Where no spell is supplied, the observed participants
    are used instead and the caller has a smaller frame than it thinks.

    `recency_days` for a member who has never participated is their tenure, which
    is true and is what a model needs, rather than a sentinel (rule S8).
    """
    horizon_90 = window.end - timedelta(days=90)
    horizon_365 = window.end - timedelta(days=365)

    tenure: dict[str, float] = {}
    strata: dict[str, Mapping[str, str]] = {}
    for spell in spells:
        end = spell.exited_at if spell.exited_at is not None else window.end
        tenure[spell.member_ref] = max(
            tenure.get(spell.member_ref, 0.0), max(0.0, _days(spell.entered_at, end))
        )
        strata.setdefault(spell.member_ref, spell.strata_at_entry)

    members = set(tenure)
    if not members:
        members = {e.member_ref for e in events if e.kind not in EXPOSURE_KINDS}

    last_at: dict[str, datetime] = {}
    frequency: dict[str, int] = defaultdict(int)
    kinds: dict[str, set[str]] = defaultdict(set)
    hours: dict[str, float] = defaultdict(float)
    channels: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if event.kind in EXPOSURE_KINDS or event.at >= window.end:
            continue
        ref = event.member_ref
        if ref not in members:
            continue
        if ref not in last_at or event.at > last_at[ref]:
            last_at[ref] = event.at
        if event.at >= horizon_90:
            frequency[ref] += 1
        kinds[ref].add(event.kind)
        if event.channel:
            channels[ref].add(event.channel)
        if event.kind == "volunteer_hours" and event.at >= horizon_365:
            hours[ref] += float(event.weight)

    contribution: dict[str, int] = defaultdict(int)
    for entry in entries:
        if entry.member_ref in members and entry.status == "settled" and entry.at < window.end:
            contribution[entry.member_ref] += entry.amount_minor

    out: list[EngagementFeatures] = []
    for ref in sorted(members):
        tenure_days = tenure.get(ref, 0.0)
        seen = last_at.get(ref)
        recency = _days(seen, window.end) if seen is not None else tenure_days
        out.append(EngagementFeatures(
            member_ref=ref,
            recency_days=max(0.0, recency),
            frequency_90d=frequency.get(ref, 0),
            breadth=len(kinds.get(ref, ())),
            volunteer_hours_365d=hours.get(ref, 0.0),
            tenure_days=tenure_days,
            contribution_minor=contribution.get(ref, 0),
            channels=frozenset(channels.get(ref, ())),
            strata=dict(strata.get(ref, {})),
        ))
    return tuple(out)


_BASIS_KINDS: Mapping[str, frozenset[str]] = MappingProxyType({
    "co_attendance": frozenset({"attend"}),
    "co_request": frozenset({"comment", "post"}),
    "co_vote": frozenset({"upvote"}),
    "co_group": frozenset({"attend", "post", "comment", "rsvp"}),
})


def interaction_edges(
    events: tuple[ParticipationEvent, ...],
    window: StreamWindow,
    *,
    basis: str = "co_attendance",
    normalisation: str = "one_over_m_minus_one",
) -> tuple[InteractionEdge, ...]:
    """
    Bipartite projection with the declared normalisation. An event with m
    attendees contributes 1/(m-1) to each pair, not 1: without it a 200-person
    annual general meeting makes every member a connector. The normalisation
    constant enters `params_hash`.

    `basis="reply"` is refused rather than approximated: `ParticipationEvent`
    carries the object replied to but not the author replied *to*, so a reply
    graph cannot be built here without inventing the edge that is the whole
    point of the graph.
    """
    if basis == "reply":
        raise ValueError(
            "basis='reply' needs the author of the parent message, which no ParticipationEvent "
            "atom carries. A reply graph inferred from co-commenting is a co-comment graph with "
            "a misleading name; use basis='co_request' and say so."
        )
    if basis not in _BASIS_KINDS:
        raise ValueError("basis must be one of " + repr(tuple(_BASIS_KINDS)) + ", got " + repr(basis))
    if normalisation not in ("one_over_m_minus_one", "none"):
        raise ValueError(
            "normalisation must be 'one_over_m_minus_one' or 'none', got " + repr(normalisation)
        )

    kinds = _BASIS_KINDS[basis]
    groups: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if event.kind not in kinds:
            continue
        if not window.start <= event.at < window.end:
            continue
        key = event.group_ref if basis == "co_group" else event.object_ref
        if key is None:
            continue
        groups[key].add(event.member_ref)

    weights: dict[tuple[str, str], float] = defaultdict(float)
    for members in groups.values():
        m = len(members)
        if m < 2:
            continue
        share = 1.0 / (m - 1) if normalisation == "one_over_m_minus_one" else 1.0
        ordered = sorted(members)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                weights[(a, b)] += share
    return tuple(
        InteractionEdge(a_ref=a, b_ref=b, weight=weights[(a, b)], basis=basis)
        for a, b in sorted(weights)
    )


# ---------------------------------------------------------------------------
# derived units
# ---------------------------------------------------------------------------


def rate_observations(
    spells: tuple[RequestSpell, ...],
    window: StreamWindow,
    *,
    by: str = "assignee_ref",
    success: Callable[[Any], bool | None],
) -> tuple[RateObservation, ...]:
    """
    (group, successes, trials), so one shrinkage implementation serves every source.

    `success` returns True, False, or **None for undetermined**, and an
    undetermined spell is not a trial. That third value is the point of the
    signature: a request that is still open and younger than the SLA horizon has
    not failed the SLA, and counting it as a failure understates every vendor
    exactly as counting it as a success flatters them. A censored, undetermined
    outcome is neither.

    Rule C7: a merged duplicate is excluded, because it is the same request
    counted twice.
    """
    successes: dict[str, int] = defaultdict(int)
    trials: dict[str, int] = defaultdict(int)
    for spell in spells:
        if getattr(spell, "outcome", None) == "merged":
            continue
        group = getattr(spell, by, None)
        if group is None:
            continue
        verdict = success(spell)
        if verdict is None:
            continue
        trials[str(group)] += 1
        if verdict:
            successes[str(group)] += 1
    return tuple(
        RateObservation(
            group_ref=group,
            successes=successes.get(group, 0),
            trials=trials[group],
            window_start=window.start,
            window_end=window.end,
        )
        for group in sorted(trials)
    )


def count_observations(
    spells: tuple[RequestSpell, ...],
    window: StreamWindow,
    *,
    by: str = "category",
    exposure: str = "since_first_seen",
) -> tuple[CountObservation, ...]:
    """
    (group, events, exposure) for the Gamma-Poisson services.

    Exposure is explicit and defaults to the days since the group was first seen
    in this window, not the window length, so a resolver who joined two weeks ago
    is never compared against one who has been here a year. `exposure="window"`
    uses the full window for every group and is the right choice only when the
    groups are known to have been present throughout.
    """
    if exposure not in ("since_first_seen", "window"):
        raise ValueError(
            "exposure must be 'since_first_seen' or 'window', got " + repr(exposure)
        )
    events: dict[str, int] = defaultdict(int)
    first_seen: dict[str, datetime] = {}
    for spell in spells:
        if getattr(spell, "outcome", None) == "merged":
            continue
        group = getattr(spell, by, None)
        if group is None:
            continue
        key = str(group)
        events[key] += 1
        at = max(spell.at_risk_from, window.start)
        if key not in first_seen or at < first_seen[key]:
            first_seen[key] = at
    window_days = _days(window.start, window.end)
    out: list[CountObservation] = []
    for key in sorted(events):
        if exposure == "window":
            days = window_days
        else:
            days = _days(first_seen[key], window.end)
        if days <= 0.0:
            # A group seen only at the boundary has no exposure, and a rate with
            # a zero denominator is not a rate (the dataclass refuses it too).
            continue
        out.append(CountObservation(
            group_ref=key,
            events=events[key],
            exposure=days,
            window_start=window.start,
            window_end=window.end,
        ))
    return tuple(out)


def pairwise_results(
    ballots: tuple[Ballot, ...],
    spec: DecisionSpec,
    *,
    options: tuple[str, ...] | None = None,
    unranked: str = "ignore",
) -> tuple[PairwiseResult, ...]:
    """
    Ballots to head-to-heads, for Bradley-Terry, Elo and the Condorcet matrix.

    Unranked options are the one genuine judgement call and it is a declared
    parameter, never a default: `unranked="ignore"` compares only options the
    voter actually expressed a view on, `unranked="below_ranked"` applies the
    usual truncation convention that anything omitted loses to everything
    listed. The second needs the full option set, which `DecisionSpec` does not
    carry, so it must be passed in rather than guessed from the ballots: an
    option nobody ranked would otherwise vanish from the universe entirely.
    """
    if unranked not in ("ignore", "below_ranked"):
        raise ValueError("unranked must be 'ignore' or 'below_ranked', got " + repr(unranked))
    if unranked == "below_ranked" and options is None:
        raise ValueError(
            "unranked='below_ranked' needs the full option set: an option that no ballot "
            "mentions cannot be recovered from the ballots, and inventing the universe from "
            "what happened to be ranked would silently drop it"
        )

    universe = tuple(options) if options is not None else ()
    out: list[PairwiseResult] = []
    for ballot in sorted(ballots, key=lambda b: (b.cast_at, b.ballot_ref)):
        tiers = _tiers_for(ballot, spec, universe, unranked)
        first_position = tiers[0][0] if tiers and tiers[0] else None
        for i, tier in enumerate(tiers):
            ordered = sorted(tier)
            for a_index, a in enumerate(ordered):
                for b in ordered[a_index + 1:]:
                    out.append(PairwiseResult(
                        winner_ref=a, loser_ref=b, at=ballot.cast_at, drawn=True,
                        first_position_ref=first_position, context_ref=ballot.decision_ref,
                    ))
            for lower in tiers[i + 1:]:
                for a in ordered:
                    for b in sorted(lower):
                        out.append(PairwiseResult(
                            winner_ref=a, loser_ref=b, at=ballot.cast_at, drawn=False,
                            first_position_ref=first_position, context_ref=ballot.decision_ref,
                        ))
    return tuple(out)


def _tiers_for(
    ballot: Ballot, spec: DecisionSpec, universe: tuple[str, ...], unranked: str
) -> list[list[str]]:
    """The ballot as ordered tiers, whatever style it was cast in."""
    style = spec.ballot_style
    if style == "score" or ballot.scores:
        by_score: dict[int, list[str]] = defaultdict(list)
        for option, score in ballot.scores.items():
            by_score[int(score)].append(option)
        tiers = [sorted(by_score[s]) for s in sorted(by_score, reverse=True)]
    elif style == "approval" or (ballot.approvals and not ballot.ranking):
        approved = sorted(ballot.approvals)
        rest = sorted(set(universe) - set(approved))
        tiers = [approved] + ([rest] if rest else [])
    else:
        tiers = [list(tier) for tier in ballot.ranking]
        if unranked == "below_ranked":
            ranked = {option for tier in tiers for option in tier}
            rest = sorted(set(universe) - ranked)
            if rest:
                tiers.append(rest)
    return [tier for tier in tiers if tier]


__all__ = [
    "PERIODS",
    "count_observations",
    "due_spells",
    "engagement_features",
    "flow_periods",
    "interaction_edges",
    "ledger_periods",
    "member_spells",
    "pairwise_results",
    "participation_periods",
    "period_bounds",
    "rate_observations",
    "request_spells",
    "roster_snapshot",
]
