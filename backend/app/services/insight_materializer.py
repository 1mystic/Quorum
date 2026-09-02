"""
Card C.10. The worker: `docs/STATS_API.md` section 1's left-hand column.

    scheduler reads pack cadence
    -> repository fetches stream rows
    -> vertical adapter -> canonical atoms
    -> PURE reducer -> stream units
    -> PURE stats function -> Evidence
    -> UPSERT insight_runs (payload = envelope, whole)

Every step after "repository fetches stream rows" is exactly what
`app/stats/registry.py` and `app/stats/streams/reduce.py` already declare;
this module never computes a statistic itself, it calls into them. "You fetch
and cache; they compute" (this card's brief) applies to this file precisely:
`_atoms_for_stream` is the only place that touches a repository, and it stops
at atoms. Everything from there on is a call into `app.stats`.

**Why this honestly cannot finish every service yet.** `app.stats.streams.
reduce` (card C.7's declared, unimplemented reducers - `request_spells`,
`flow_periods`, and friends) is not this card's file to write: it is under
`app/stats/`, which this card's boundary names explicitly as the
statistician's. Calling `spec.fn` for a Pack-1 service therefore still raises
`NotImplementedError` today, and this worker's job is to make that a visible,
correctly-shaped `insight_runs` row rather than a silent skip or a fabricated
number - which is precisely the documented worker failure mode in
`docs/STATS_API.md` section 8 ("A failing job writes an insight_runs row with
insufficient=true and a caveat naming the failure... a missing tile teaches
users the dashboard is unreliable and a tile that says why does not"). Once
`streams/reduce.py` lands, this file changes nothing: the same call produces
a real `Evidence`.
"""
from __future__ import annotations

import inspect
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.repository import RequestRepository, LedgerRepository, InsightRunRepository
from app.repository.member import MemberRepository
from app.stats import registry
from app.stats.contracts import Evidence, InsufficientData, insufficient
from app.stats.streams import reduce as stream_reduce
from app.stats.streams.window import StreamWindow
from app.verticals.adapters import get_adapter

_CADENCE_STALE_AFTER = {
    "hourly": timedelta(hours=1),
    "nightly": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
    "weekly_platform": timedelta(weeks=1),
    "on_demand": timedelta(hours=1),
    "on_write": timedelta(minutes=5),
    "on_submission": timedelta(minutes=5),
    "on_decision_close": timedelta(days=365),
    "on_survey_close": timedelta(days=1),
    "on_dispatch": timedelta(hours=1),
}

# The first-positional-parameter names the pure functions use for their unit
# argument, mapped to the unit name that identifies the right reducer. Read
# off `app/stats/registry.py`'s function signatures directly, not guessed.
_FIRST_ARG_TO_UNIT = {
    "spells": "RequestSpell",
    "periods": "FlowPeriod",
    "series": "FlowPeriod",
}


def default_window(now: datetime | None = None, *, tenant_timezone: str = "UTC",
                    lookback_days: int = 400) -> StreamWindow:
    now = now or datetime.now(timezone.utc)
    return StreamWindow(
        start=now - timedelta(days=lookback_days),
        end=now,
        timezone=tenant_timezone,
        complete_through=now,
    )


class InsightMaterializer:
    """One tenant, one run. `materialize_all` is the whole of card C.10's worker."""

    def __init__(self, db: AsyncSession, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.adapter = get_adapter(tenant.vertical)
        self.request_repo = RequestRepository(db, tenant.id)
        self.ledger_repo = LedgerRepository(db, tenant.id)
        self.member_repo = MemberRepository(db)
        self.run_repo = InsightRunRepository(db, tenant.id)

    async def materialize_all(self, window: StreamWindow | None = None) -> list:
        window = window or default_window(tenant_timezone=self.tenant.timezone)
        atoms_by_stream = await self._atoms(window)
        runs = []
        for service_id in registry.implemented_ids():
            spec = registry.get(service_id)
            runs.append(await self.materialize_one(spec, window, atoms_by_stream))
        return runs

    async def materialize_pack(self, pack_id: str, window: StreamWindow | None = None) -> list:
        """
        Same call chain as `materialize_all`, restricted to one pack's
        implemented services. What `InsightsService.set_pack_enabled` runs
        inline as the "enqueue a backfill" step (`docs/STATS_API.md` section
        4's `PUT .../insights/packs/{pack_id}`) so a newly enabled pack does
        not sit empty until the next scheduled worker pass.
        """
        window = window or default_window(tenant_timezone=self.tenant.timezone)
        atoms_by_stream = await self._atoms(window)
        implemented = set(registry.implemented_ids())
        runs = []
        for spec in registry.for_pack(pack_id):
            if spec.id not in implemented:
                continue
            runs.append(await self.materialize_one(spec, window, atoms_by_stream))
        return runs

    async def _atoms(self, window: StreamWindow) -> dict:
        return {
            "request_flow": await self._request_flow_atoms(window),
            "ledger": await self._ledger_atoms(window),
            "member_lifecycle": await self._member_lifecycle_atoms(window),
        }

    async def materialize_one(self, spec, window: StreamWindow, atoms_by_stream: dict):
        started = time.monotonic()
        try:
            evidence = self._compute(spec, atoms_by_stream, window)
        except NotImplementedError as exc:
            evidence = insufficient(
                spec.id, n=0, as_of=window.end,
                caveats=("Not yet computable: " + str(exc),),
            )
        except InsufficientData as exc:
            evidence = insufficient(
                spec.id, n=exc.n, as_of=window.end, caveats=(str(exc),),
            )
        duration_ms = int((time.monotonic() - started) * 1000)
        stale_after = window.end + _CADENCE_STALE_AFTER.get(spec.default_cadence, timedelta(days=1))
        return await self.run_repo.record_run(
            pack=spec.pack, service=spec.id, scope_key="",
            params_hash=evidence.params_hash or "",
            window_start=window.start, window_end=window.end,
            payload=evidence.to_wire(), n=evidence.n, n_censored=evidence.n_censored,
            insufficient=evidence.insufficient_data, worst_status=evidence.worst_status,
            blocking=bool(evidence.blocking_failures), contract_version=evidence.contract_version,
            duration_ms=duration_ms, stale_after=stale_after,
        )

    # ---- pure call, no I/O below this line -----------------------------

    def _compute(self, spec, atoms_by_stream: dict, window: StreamWindow) -> Evidence:
        params = inspect.signature(spec.fn).parameters
        names = list(params)
        if len(names) < 2 or names[0] not in _FIRST_ARG_TO_UNIT or names[1] != "window":
            raise NotImplementedError(
                spec.id + " does not take the (units, window, ...) shape this worker builds"
            )
        unit_name = _FIRST_ARG_TO_UNIT[names[0]]
        if unit_name not in spec.required_units:
            raise NotImplementedError(
                spec.id + " declares required_units " + repr(sorted(spec.required_units))
                + " but its first argument implies " + unit_name
            )

        extra_required = [
            name for name, p in list(params.items())[2:]
            if p.default is inspect.Parameter.empty
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if extra_required:
            raise NotImplementedError(
                spec.id + " needs parameters this worker does not supply yet: "
                + ", ".join(extra_required)
            )

        units = self._units_for(unit_name, atoms_by_stream, window)
        return spec.fn(units, window)

    def _units_for(self, unit_name: str, atoms_by_stream: dict, window: StreamWindow):
        if unit_name == "RequestSpell":
            return stream_reduce.request_spells(
                atoms_by_stream["request_flow"], window, reopen_policy=self.adapter.reopen_policy
            )
        if unit_name == "FlowPeriod":
            return stream_reduce.flow_periods(atoms_by_stream["request_flow"], window)
        if unit_name == "MemberSpell":
            return stream_reduce.member_spells(atoms_by_stream["member_lifecycle"], window)
        raise NotImplementedError("no reduction path wired for unit " + unit_name)

    # ---- fetch, the impure edge -----------------------------------------

    async def _request_flow_atoms(self, window: StreamWindow):
        rows = await self.request_repo.stream_requests(window.end)
        return self.adapter.request_events(rows)

    async def _ledger_atoms(self, window: StreamWindow):
        dues = await self.ledger_repo.stream_dues(window.end)
        payments = await self.ledger_repo.stream_payments(window.end)
        contributions = await self.ledger_repo.stream_contributions(window.end)
        expenses = await self.ledger_repo.stream_expenses(window.end)
        return self.adapter.ledger_entries([*dues, *payments, *contributions, *expenses])

    async def _member_lifecycle_atoms(self, window: StreamWindow):
        rows = await self.member_repo.stream_members(self.tenant.id, window.end)
        return self.adapter.member_events(rows)


async def run_for_tenant(db: AsyncSession, tenant: Tenant, *, window: StreamWindow | None = None):
    """The entrypoint a scheduler/CLI calls. See `backend/scripts/materialize_insights.py`."""
    materializer = InsightMaterializer(db, tenant)
    return await materializer.materialize_all(window)
