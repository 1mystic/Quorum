"""
Card C.10. Proves the materializer pipeline - adapter atoms -> reducer ->
pure stats function -> Evidence -> InsightRun row - genuinely computes when
its inputs are present, without a database.

**Why this test monkeypatches `app.stats.streams.reduce.request_spells`
instead of calling the real one.** That reducer is declared in
`app/stats/streams/reduce.py` and is still `NotImplementedError` (card C.7's
follow-up; see CONTEXT.md's statistician "in flight" note). `app/stats/` is
this card's explicit boundary - "you call into app/stats/registry.py, you
don't edit it" - and streams/reduce.py is under app/stats/, so it stays out
of scope here. This test does not touch that file: it swaps in a small,
honestly-labelled reduction written only in this test module, feeds it real
`RequestEvent` atoms with a known, hand-computed answer, and asserts the
worker's own code (`InsightMaterializer._compute` and `materialize_one`)
carries a real number all the way into an `insight_runs`-shaped row. Once the
statistician lands the real `request_spells`, nothing in
`insight_materializer.py` needs to change for this to become the genuine,
unmocked path; `tests/integration/test_insights.py` exercises that same code
against a live database and is the test that proves it end to end once
Postgres is available.

`InsightMaterializer` is built via `object.__new__` with only `.adapter` set,
so this test never opens a database connection or a real repository -
consistent with "no Postgres in this sandbox" (CONTEXT.md's known
constraints).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.insight_materializer import InsightMaterializer, default_window
from app.stats import registry
from app.stats.contracts import InsufficientData
from app.stats.streams import reduce as stream_reduce
from app.stats.streams.request import RequestEvent, RequestSpell
from app.verticals.adapters import RwaSocietyAdapter

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _toy_request_spells(events, window, *, reopen_policy="new_spell"):
    """
    A minimal, honest reduction: one spell per request_ref, terminal if a
    terminal atom exists, censored at window.end otherwise. It does not claim
    to implement rules C3-C10 in full (no interval censoring, no reopen
    handling); it exists only to give this test a real, hand-checkable number
    to assert against.
    """
    by_ref: dict[str, list[RequestEvent]] = defaultdict(list)
    for event in events:
        by_ref[event.request_ref].append(event)

    spells = []
    for ref, group in by_ref.items():
        group.sort(key=lambda e: e.at)
        opened = group[0]
        terminal = next(
            (e for e in group if e.kind in ("resolved", "escalated", "withdrawn", "merged")), None
        )
        if terminal is not None:
            duration_hours = (terminal.at - opened.at).total_seconds() / 3600.0
            spells.append(RequestSpell(
                request_ref=ref, opened_at=opened.at, at_risk_from=opened.at, left_truncated=False,
                duration_hours=duration_hours, duration_active_hours=None, event_observed=True,
                outcome=terminal.kind, terminal_at=terminal.at, censoring="none",
                interval_lo_hours=None, interval_hi_hours=None, first_response_hours=None,
                paused_hours=0.0, reopened_count=0, duplicate_count=0,
                category=opened.category or "other",
            ))
        else:
            duration_hours = (window.end - opened.at).total_seconds() / 3600.0
            spells.append(RequestSpell(
                request_ref=ref, opened_at=opened.at, at_risk_from=opened.at, left_truncated=False,
                duration_hours=duration_hours, duration_active_hours=None, event_observed=False,
                outcome=None, terminal_at=None, censoring="administrative",
                interval_lo_hours=None, interval_hi_hours=None, first_response_hours=None,
                paused_hours=0.0, reopened_count=0, duplicate_count=0,
                category=opened.category or "other",
            ))
    return tuple(spells)


def _bare_materializer() -> InsightMaterializer:
    materializer = object.__new__(InsightMaterializer)
    materializer.adapter = RwaSocietyAdapter()
    return materializer


def _known_answer_events() -> tuple[RequestEvent, ...]:
    """35 requests resolved in exactly 8 days, 5 still open at day 3. Median is exactly 8.0."""
    events: list[RequestEvent] = []
    opened_at = NOW - timedelta(days=100)
    for i in range(35):
        events.append(RequestEvent(request_ref=f"r_{i}", at=opened_at, kind="opened",
                                    category="water_supply"))
        events.append(RequestEvent(request_ref=f"r_{i}", at=opened_at + timedelta(days=8),
                                    kind="resolved", category="water_supply"))
    still_open_opened = NOW - timedelta(days=3)
    for i in range(35, 40):
        events.append(RequestEvent(request_ref=f"r_{i}", at=still_open_opened, kind="opened",
                                    category="water_supply"))
    return tuple(events)


def test_compute_produces_a_real_evidence_once_the_reducer_exists(monkeypatch):
    monkeypatch.setattr(stream_reduce, "request_spells", _toy_request_spells)

    window = default_window(now=NOW, tenant_timezone="Asia/Kolkata", lookback_days=200)
    materializer = _bare_materializer()
    spec = registry.get("survival.median_resolution_days")
    atoms_by_stream = {"request_flow": _known_answer_events(), "ledger": (), "member_lifecycle": ()}

    evidence = materializer._compute(spec, atoms_by_stream, window)

    assert evidence.insufficient_data is False
    assert evidence.n == 40
    assert evidence.n_censored == 5, "the 5 still-open requests must be counted, not dropped (rule C1)"
    assert evidence.value == pytest.approx(8.0, abs=1e-6)
    assert evidence.method == "survival.median_resolution_days"
    assert evidence.params_hash


@pytest.mark.asyncio
async def test_materialize_one_writes_a_real_number_into_the_run_row(monkeypatch):
    """The whole worker, `_compute` through `record_run`, with a fake repository standing in for Postgres."""
    monkeypatch.setattr(stream_reduce, "request_spells", _toy_request_spells)

    window = default_window(now=NOW, tenant_timezone="Asia/Kolkata", lookback_days=200)
    materializer = _bare_materializer()

    written: list[dict] = []

    class _FakeRunRepo:
        async def record_run(self, **kwargs):
            written.append(kwargs)
            return SimpleNamespace(id=len(written), **kwargs)

    materializer.run_repo = _FakeRunRepo()

    spec = registry.get("survival.median_resolution_days")
    atoms_by_stream = {"request_flow": _known_answer_events(), "ledger": (), "member_lifecycle": ()}

    row = await materializer.materialize_one(spec, window, atoms_by_stream)

    assert len(written) == 1
    call = written[0]
    assert call["service"] == "survival.median_resolution_days"
    assert call["pack"] == "reliability_ops"
    assert call["insufficient"] is False
    assert call["n"] == 40
    assert call["n_censored"] == 5
    assert call["payload"]["value"] == pytest.approx(8.0, abs=1e-6)
    assert call["payload"]["method"] == "survival.median_resolution_days"
    assert call["worst_status"] in ("PASS", "WARN", "FAIL")
    assert call["stale_after"] > window.end


@pytest.mark.asyncio
async def test_materialize_one_is_honest_when_the_reducer_is_not_implemented():
    """
    Without the monkeypatch, `streams.reduce.request_spells` genuinely raises
    `NotImplementedError` today. This is `docs/STATS_API.md` section 8's
    documented failure mode: a visible insufficient row with a caveat naming
    the failure, never a fabricated number and never a skipped row.
    """
    window = default_window(now=NOW, tenant_timezone="Asia/Kolkata", lookback_days=200)
    materializer = _bare_materializer()

    written: list[dict] = []

    class _FakeRunRepo:
        async def record_run(self, **kwargs):
            written.append(kwargs)
            return SimpleNamespace(id=1, **kwargs)

    materializer.run_repo = _FakeRunRepo()

    spec = registry.get("survival.median_resolution_days")
    atoms_by_stream = {"request_flow": _known_answer_events(), "ledger": (), "member_lifecycle": ()}

    row = await materializer.materialize_one(spec, window, atoms_by_stream)

    call = written[0]
    assert call["insufficient"] is True
    assert call["payload"]["insufficient_data"] is True
    assert call["payload"]["value"] is None
    assert "streams.reduce.request_spells" in call["payload"]["caveats"][0]


def test_compute_refuses_a_service_it_cannot_wire_yet():
    """
    `queueing.mmc_metrics` needs arrival_rate/service_rate/servers this worker
    does not (yet) supply; it must raise NotImplementedError rather than call
    the function with the wrong shape.
    """
    window = default_window(now=NOW, tenant_timezone="Asia/Kolkata", lookback_days=200)
    materializer = _bare_materializer()
    spec = registry.get("queueing.mmc_metrics")
    with pytest.raises(NotImplementedError):
        materializer._compute(spec, {"request_flow": (), "ledger": (), "member_lifecycle": ()}, window)
