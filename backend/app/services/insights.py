"""
Card C.10. The read half of `docs/STATS_API.md`.

**The API never computes a statistic.** Every method here reads a cached
`insight_runs` row through `InsightRunRepository` and serializes what it
finds. When nothing has been computed yet it returns the calm, honest
"not enough data" shape rather than a 404 or a 422 (section 5: "not enough
data" is a 200, because if honesty returns an error code every client learns
that honest tools look broken).
"""
from datetime import datetime, timezone

from app.repository import InsightRunRepository
from app.stats import registry
from app.stats.contracts import Evidence, insufficient
from app.exceptions import (
    InsightNotFoundError, PackDisabledError, PackNotFoundError, StreamUnavailableError,
    TenantNotFoundError,
)

# Streams the worker (`app/services/insight_materializer.py`) actually fetches
# rows for today: `request_flow`, `ledger` and `member_lifecycle` each have a
# real repository method, a real vertical adapter mapping and a real reducer
# in `app/stats/streams/reduce.py`. `participation`, `signal` and `decision`
# have adapter methods but are not yet wired into the materializer's atom
# fetch, so a service that needs one of those is always `insufficient_data`,
# never fabricated. Kept here rather than in `app/verticals/` so this file,
# not the adapter, owns the "is this pack worth turning on yet" judgement
# call - and so `InsightsService.set_pack_enabled` and `packs()` can never
# drift on what "available" means.
STREAMS_WITH_DATA = frozenset({"request_flow", "ledger", "member_lifecycle"})


class InsightsService:
    def __init__(self, run_repo: InsightRunRepository, tenant_repo, db=None):
        self.run_repo = run_repo
        self.tenant_repo = tenant_repo
        # Only needed by `set_pack_enabled`'s inline backfill, which builds
        # its own `InsightMaterializer` against the same session. Optional so
        # tests that only exercise the read surface need not supply one.
        self.db = db

    async def packs(self, tenant_id: int) -> dict:
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        enabled = set(tenant.enabled_packs or [])
        out = [await self._pack_entry(pack, enabled) for pack in registry.packs()]
        return {"vertical": tenant.vertical, "packs": out}

    async def set_pack_enabled(self, tenant_id: int, pack_id: str, enabled: bool) -> dict:
        """
        `docs/STATS_API.md` section 4's `PUT .../insights/packs/{pack_id}`.
        Writes `Tenant.enabled_packs`, never `insight_runs`: disabling a pack
        does not delete its history, it just stops it being served (`packs()`
        and `pack_insights()` both gate on `enabled_packs`, not on whether a
        row exists).
        """
        if pack_id not in registry.PACKS:
            raise PackNotFoundError()
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()

        pack = registry.PACKS[pack_id]
        enabled_packs = list(tenant.enabled_packs or [])
        already_enabled = pack_id in enabled_packs
        first_result_at = None

        if enabled:
            streams_available = pack.required_streams & STREAMS_WITH_DATA
            if streams_available != pack.required_streams:
                missing = sorted(pack.required_streams - streams_available)
                raise StreamUnavailableError(", ".join(missing))
            if not already_enabled:
                enabled_packs.append(pack_id)
                tenant.enabled_packs = enabled_packs
                await self.tenant_repo.db.flush()
                runs = await self._backfill(tenant, pack_id)
                first_result_at = max(
                    (run.computed_at for run in runs), default=datetime.now(timezone.utc)
                )
        else:
            if already_enabled:
                enabled_packs = [p for p in enabled_packs if p != pack_id]
                tenant.enabled_packs = enabled_packs
                await self.tenant_repo.db.flush()

        entry = await self._pack_entry(pack, set(enabled_packs))
        entry["estimated_first_result_at"] = first_result_at
        return entry

    async def _backfill(self, tenant, pack_id: str) -> list:
        """
        "Enqueues a backfill" per the endpoint's own docstring in
        `TenantSettingsView.vue`. There is no job queue in this codebase
        (`scripts/materialize_insights.py` is a bare polling loop over every
        tenant, nothing that accepts a single job), so the fallback the card
        names explicitly is used: run the materializer inline, synchronously,
        scoped to this one pack, so the newly enabled pack has real rows
        immediately rather than sitting empty until the next hourly pass.
        """
        from app.services.insight_materializer import InsightMaterializer

        if self.db is None:
            return []
        materializer = InsightMaterializer(self.db, tenant)
        return await materializer.materialize_pack(pack_id)

    async def _pack_entry(self, pack, enabled: set[str]) -> dict:
        streams_available = pack.required_streams & STREAMS_WITH_DATA
        available = streams_available == pack.required_streams
        specs = registry.for_pack(pack.id)
        rows = await self.run_repo.latest_for_pack(pack.id)
        by_service = {row.service: row for row in rows}
        ready = sum(1 for s in specs if s.implemented and s.id in by_service
                    and not by_service[s.id].insufficient)
        insuff = sum(1 for s in specs if s.implemented and s.id in by_service
                     and by_service[s.id].insufficient)
        blocked = sum(1 for s in specs if not s.implemented)
        last_computed = max((row.computed_at for row in rows), default=None)
        entry = {
            "id": pack.id, "name": pack.name,
            "enabled": pack.id in enabled,
            "available": available,
            "required_streams": sorted(pack.required_streams),
            "streams_available": sorted(streams_available),
            "cadence": pack.default_cadence,
            "services_ready": ready,
            "services_insufficient": insuff,
            "services_blocked": blocked,
            "last_computed_at": last_computed,
        }
        if not available:
            missing = sorted(pack.required_streams - streams_available)
            entry["reason"] = "needs the " + ", ".join(missing) + " stream" + (
                "s" if len(missing) > 1 else ""
            )
        return entry

    async def pack_insights(self, tenant_id: int, pack_id: str) -> list[dict]:
        await self._require_pack_enabled(tenant_id, pack_id)
        rows = await self.run_repo.latest_for_pack(pack_id)
        return [self._envelope_response(row) for row in rows]

    async def one_insight(self, tenant_id: int, pack_id: str, service_id: str,
                           scope: str = "") -> dict:
        await self._require_pack_enabled(tenant_id, pack_id)
        try:
            spec = registry.get(service_id)
        except KeyError:
            raise InsightNotFoundError()
        if spec.pack != pack_id:
            raise InsightNotFoundError()

        row = await self.run_repo.latest(service_id, scope)
        if row is None:
            envelope = insufficient(
                service_id, n=0, as_of=datetime.now(timezone.utc),
                caveats=("First run has not landed yet.",),
            )
            return {
                "service": service_id, "pack": pack_id, "scope": scope,
                "evidence": envelope.to_wire(), "computed_at": None, "stale_after": None,
                "is_stale": False, "method_url": "/api/methods/" + service_id,
            }
        return self._envelope_response(row)

    async def history(self, tenant_id: int, service_id: str, scope: str = "") -> list[dict]:
        rows = await self.run_repo.history(service_id, scope)
        return [self._envelope_response(row) for row in rows]

    async def health(self, tenant_id: int) -> dict:
        return await self.run_repo.health()

    # ---- helpers ----------------------------------------------------------

    async def _require_pack_enabled(self, tenant_id: int, pack_id: str) -> None:
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        if pack_id not in (tenant.enabled_packs or []):
            raise PackDisabledError(pack_id)

    @staticmethod
    def _envelope_response(row) -> dict:
        now = datetime.now(timezone.utc)
        stale_after = row.stale_after
        is_stale = stale_after is not None and now > (
            stale_after if stale_after.tzinfo else stale_after.replace(tzinfo=timezone.utc)
        )
        return {
            "service": row.service, "pack": row.pack, "scope": row.scope_key,
            "evidence": row.payload, "computed_at": row.computed_at,
            "stale_after": row.stale_after, "is_stale": is_stale,
            "method_url": "/api/methods/" + row.service,
        }
